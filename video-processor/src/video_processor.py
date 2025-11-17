import queue
import random
import select
import signal
import socket
import subprocess
import sys
import threading
import time
from dataclasses import dataclass
from typing import Dict

import numpy as np


@dataclass
class FrameMetadata:
    frame_id: int
    timestamp_received: float
    camera_type: str
    stream_id: int
    original_fps: int
    processed_fps: int = 30
    width: int = 0
    height: int = 0


class BackpressureQueue:
    """A queue that drops old frames if they're not consumed within the timeout"""

    def __init__(self, maxsize: int = 10000, timeout_ms: int = 500):
        self.queue = queue.Queue(maxsize=maxsize)
        self.timeout_s = timeout_ms / 1000.0
        self.dropped_frames = 0

    def put(self, item, timeout=None):
        """Put item in queue, dropping old items if queue is full"""
        try:
            # Try to put without blocking
            self.queue.put_nowait(item)
        except queue.Full:
            # Queue is full, drop oldest items until we can add new one
            dropped_count = 0
            while not self.queue.empty():
                try:
                    self.queue.get_nowait()
                    dropped_count += 1
                except queue.Empty:
                    break

            self.dropped_frames += dropped_count
            if dropped_count % 1000 == 0:
                print(
                    f"Dropped {dropped_count} frames due to backpressure "
                    f"(total: {self.dropped_frames})"
                )

            # Now add the new item
            try:
                self.queue.put_nowait(item)
            except queue.Full:
                self.dropped_frames += 1

    def get(self, timeout=None):
        """Get item from queue with timeout"""
        timeout = timeout or self.timeout_s
        return self.queue.get(timeout=timeout)

    def empty(self):
        return self.queue.empty()


class UDPMPEGTSServer:
    """UDP MPEGTS server using FFmpeg"""

    def __init__(
        self, stream_id: int, port: int, config: Dict, frame_queue: BackpressureQueue
    ):
        self.stream_id = stream_id
        self.port = port
        self.config = config
        self.frame_queue = frame_queue
        self.running = False
        self.ffmpeg_process = None
        self.target_fps = 60
        self.frame_interval = 1.0 / self.target_fps
        self.clients = set()  # Track connected clients

    def start_server(self):
        """Start the UDP MPEGTS server using FFmpeg"""
        print(
            f"Starting UDP MPEGTS server for stream {self.stream_id} "
            f"on port {self.port}"
        )

        # FFmpeg command to output MPEGTS over UDP
        ffmpeg_cmd = [
            "ffmpeg",
            "-f",
            "rawvideo",
            "-vcodec",
            "rawvideo",
            "-pix_fmt",
            "bgr24",
            "-s",
            f"{self.config['width']}x{self.config['height']}",
            "-r",
            str(self.target_fps),
            "-i",
            "pipe:0",
            "-c:v",
            "libx264",
            "-preset",
            "ultrafast",
            "-tune",
            "zerolatency",
            "-crf",
            "23",
            "-g",
            str(self.target_fps),
            "-f",
            "mpegts",
            # UDP output with optimal packet size
            f"udp://127.0.0.1:{self.port}?pkt_size=1316",
        ]

        try:
            # Start FFmpeg process
            self.ffmpeg_process = subprocess.Popen(
                ffmpeg_cmd, stdin=subprocess.PIPE, stderr=subprocess.PIPE
            )

            self.running = True
            frames_sent = 0
            last_status_time = time.time()
            last_frame_time = time.time()

            print(
                f"UDP MPEGTS stream {self.stream_id} started - connect with: ffplay udp://127.0.0.1:{self.port}"
            )

            while self.running and self.ffmpeg_process.poll() is None:
                try:
                    # Get frame from queue
                    frame_data, metadata = self.frame_queue.get(timeout=1.0)

                    # Throttle to target FPS
                    current_time = time.time()
                    time_since_last = current_time - last_frame_time

                    if time_since_last < self.frame_interval:
                        time.sleep(self.frame_interval - time_since_last)

                    # Check if FFmpeg stdin is ready for writing
                    if (
                        self.ffmpeg_process.stdin
                        and not self.ffmpeg_process.stdin.closed
                    ):
                        try:
                            # Use select to check if we can write without blocking
                            ready = select.select(
                                [], [self.ffmpeg_process.stdin], [], 0.01
                            )
                            if ready[1]:  # stdin is ready for writing
                                frame_bytes = frame_data.tobytes()
                                self.ffmpeg_process.stdin.write(frame_bytes)
                                self.ffmpeg_process.stdin.flush()
                                frames_sent += 1
                                last_frame_time = time.time()
                                # send metadata to mqtt broker

                                # Status update every 5 seconds
                                if current_time - last_status_time >= 5.0:
                                    print(
                                        f"Stream {self.stream_id}: Sent {frames_sent} frames via UDP"
                                    )
                                    last_status_time = current_time
                            else:
                                # FFmpeg isn't ready, skip this frame
                                pass
                        except (BrokenPipeError, OSError) as e:
                            print(
                                f"FFmpeg process ended for stream {self.stream_id}: {e}"
                            )
                            break
                    else:
                        print(f"FFmpeg stdin closed for stream {self.stream_id}")
                        break
                except queue.Empty:
                    # No frames available, continue waiting
                    continue
                except Exception as e:
                    print(f"Error in UDP server for stream {self.stream_id}: {e}")
                    break

        except Exception as e:
            print(f"Error starting UDP server for stream {self.stream_id}: {e}")
        finally:
            self.cleanup()

    def cleanup(self):
        """Clean up FFmpeg process"""
        self.running = False
        if self.ffmpeg_process:
            try:
                self.ffmpeg_process.stdin.close()
                self.ffmpeg_process.terminate()
                self.ffmpeg_process.wait(timeout=5)
            except BaseException:
                try:
                    self.ffmpeg_process.kill()
                except BaseException:
                    pass
        print(f"UDP MPEGTS server {self.stream_id} stopped")

    def stop(self):
        """Stop the UDP server"""
        self.cleanup()


class VideoProcessor:
    def __init__(self, input_ports: Dict[int, Dict], output_udp_base_port: int = 8554):
        self.input_ports = input_ports
        self.output_udp_base_port = output_udp_base_port
        self.running = False

        # Frame processing
        self.frame_counters = {}
        self.frame_queues = {}
        self.udp_servers = {}

        # Initialize frame counters and queues for each stream
        for stream_id in input_ports.keys():
            self.frame_counters[stream_id] = 0
            self.frame_queues[stream_id] = BackpressureQueue(
                maxsize=1000, timeout_ms=500
            )

    def forward_to_ffmpeg(self, ffmpeg_decode, client_socket, stream_id):
        try:
            while self.running:
                data = client_socket.recv(8192)
                if not data:
                    break
                ffmpeg_decode.stdin.write(data)
        except Exception as e:
            print(f"Error forwarding data to FFmpeg for stream {stream_id}: {e}")
        finally:
            try:
                ffmpeg_decode.stdin.close()
            except BaseException:
                pass

    def receive_mpegts_stream(self, stream_id: int, port: int, config: Dict):
        """Receive MPEGTS stream and decode frames with disconnect resilience"""
        print(f"Starting MPEGTS receiver for stream {stream_id} on port {port}")

        # Exponential backoff parameters
        base_delay = 0.5  # Initial delay in seconds
        max_delay = 30.0  # Maximum delay between retries
        max_consecutive_failures = 10  # Max failures before extended cooldown
        extended_cooldown = 60.0  # Cooldown period after max failures

        consecutive_failures = 0
        current_delay = base_delay

        while self.running:
            connected = False
            try:
                # Connect to the simulator's video stream
                client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                client_socket.connect(("127.0.0.1", port))
                connected = True
                print(f"Connected to stream {stream_id} on port {port}")

                # Reset failure counters on successful connection
                consecutive_failures = 0
                current_delay = base_delay

                # Create FFmpeg process to decode MPEGTS to raw frames
                ffmpeg_decode = subprocess.Popen(
                    [
                        "ffmpeg",
                        "-i",
                        "pipe:0",  # Read from stdin
                        "-f",
                        "rawvideo",
                        "-pix_fmt",
                        "bgr24",
                        "-an",  # No audio
                        "pipe:1",  # Output to stdout
                    ],
                    stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.DEVNULL,
                )

                forward_thread = threading.Thread(
                    target=self.forward_to_ffmpeg,
                    args=(ffmpeg_decode, client_socket, stream_id),
                )
                forward_thread.daemon = True
                forward_thread.start()

                # Read decoded frames
                frame_size = (
                    config["width"] * config["height"] * 3
                )  # BGR24 = 3 bytes per pixel
                frames_processed = 0
                frame_errors = 0  # Track consecutive frame errors
                max_frame_errors = 50  # Max consecutive frame errors before reconnect

                while self.running:
                    try:
                        # Read one frame worth of data
                        frame_data = ffmpeg_decode.stdout.read(frame_size)
                        if len(frame_data) != frame_size:
                            if len(frame_data) == 0:
                                print(
                                    f"No more data from FFmpeg for stream {stream_id}",
                                    file=sys.stderr
                                )
                            else:
                                print(
                                    f"Incomplete frame data for stream {stream_id}: {len(frame_data)}/{frame_size}",
                                    file=sys.stderr
                                )
                            break

                        # Convert to numpy array
                        frame = np.frombuffer(frame_data, dtype=np.uint8)
                        frame = frame.reshape((config["height"], config["width"], 3))

                        # Create metadata
                        self.frame_counters[stream_id] += 1
                        frames_processed += 1
                        metadata = FrameMetadata(
                            frame_id=self.frame_counters[stream_id],
                            timestamp_received=time.time(),
                            camera_type=config["format"],
                            stream_id=stream_id,
                            original_fps=config["fps"],
                            width=config["width"],
                            height=config["height"],
                        )

                        # Put frame in backpressure-resistant queue
                        self.frame_queues[stream_id].put((frame, metadata))
                        frame_errors = 0  # Reset frame error counter on success

                        if frames_processed % 100 == 0:
                            print(
                                f"Stream {stream_id}: Queued {frames_processed} frames"
                            )

                    except (ValueError, RuntimeError) as e:
                        # Frame-level error recovery: track errors and continue
                        frame_errors += 1
                        print(
                            f"Frame processing error for stream {stream_id} ({frame_errors}/{max_frame_errors}): {e}",
                            file=sys.stderr
                        )

                        if frame_errors >= max_frame_errors:
                            print(
                                f"Too many consecutive frame errors for stream {stream_id}, reconnecting...",
                                file=sys.stderr
                            )
                            break

                        # Continue processing instead of full disconnect
                        continue

                    except Exception as e:
                        print(
                            f"Unexpected frame error for stream {stream_id}: {e}",
                            file=sys.stderr
                        )
                        break

            except (socket.error, ConnectionRefusedError, OSError) as e:
                consecutive_failures += 1
                error_type = type(e).__name__
                print(
                    f"Connection error for stream {stream_id} ({consecutive_failures}/{max_consecutive_failures}) [{error_type}]: {e}",
                    file=sys.stderr
                )

                # Check if we've hit max consecutive failures
                if consecutive_failures >= max_consecutive_failures:
                    print(
                        f"Max consecutive failures reached for stream {stream_id}. Entering extended cooldown ({extended_cooldown}s)...",
                        file=sys.stderr
                    )
                    time.sleep(extended_cooldown)
                    consecutive_failures = 0  # Reset after cooldown
                    current_delay = base_delay
                else:
                    # Exponential backoff with jitter
                    jitter = random.uniform(0, 0.1 * current_delay)
                    delay = min(current_delay + jitter, max_delay)
                    print(
                        f"Reconnecting stream {stream_id} in {delay:.2f}s...",
                        file=sys.stderr
                    )
                    time.sleep(delay)
                    current_delay = min(current_delay * 2, max_delay)

            except Exception as e:
                consecutive_failures += 1
                error_type = type(e).__name__
                print(
                    f"Unexpected error in MPEGTS receiver for stream {stream_id} ({consecutive_failures}/{max_consecutive_failures}) [{error_type}]: {e}",
                    file=sys.stderr
                )
                time.sleep(current_delay)

            finally:
                if connected:
                    print(f"Disconnected from stream {stream_id} on port {port}", file=sys.stderr)
                try:
                    client_socket.close()
                except BaseException:
                    pass
                try:
                    ffmpeg_decode.terminate()
                    ffmpeg_decode.wait()
                except BaseException:
                    pass

    def start(self):
        """Start video processor"""
        print("Starting Video Processor with UDP+MPEGTS...")
        self.running = True

        threads = []

        # Start MPEGTS receivers and UDP servers for each input stream
        for stream_id, config in self.input_ports.items():
            port = config["port"]

            # Start MPEGTS receiver
            receiver_thread = threading.Thread(
                target=self.receive_mpegts_stream, args=(stream_id, port, config)
            )
            receiver_thread.daemon = True
            threads.append(receiver_thread)

            # Start UDP server
            udp_port = self.output_udp_base_port + stream_id
            udp_server = UDPMPEGTSServer(
                stream_id, udp_port, config, self.frame_queues[stream_id]
            )
            self.udp_servers[stream_id] = udp_server

            udp_thread = threading.Thread(target=udp_server.start_server)
            udp_thread.daemon = True
            threads.append(udp_thread)

        # Start all threads
        for thread in threads:
            thread.start()

        print("Video Processor started!")
        print("\nUDP MPEGTS Streams:")
        for stream_id, config in self.input_ports.items():
            udp_port = self.output_udp_base_port + stream_id
            print(f"  Stream {stream_id}: udp://127.0.0.1:{udp_port}")
            print(f"    Play with: ffplay udp://127.0.0.1:{udp_port}")
            print(f"    Or VLC: vlc udp://@:127.0.0.1:{udp_port}")

        def signal_handler(sig, frame):
            print("\nReceived interrupt signal...")
            self.running = False
            for server in self.udp_servers.values():
                server.stop()
            sys.exit(0)

        signal.signal(signal.SIGINT, signal_handler)

        try:
            while self.running:
                time.sleep(5)
                # Print queue status
                for stream_id in self.input_ports.keys():
                    queue_size = self.frame_queues[stream_id].queue.qsize()
                    dropped = self.frame_queues[stream_id].dropped_frames
                    print(
                        f"Stream {stream_id}: Queue size: {queue_size}, Dropped: {dropped}"
                    )
        except KeyboardInterrupt:
            print("\nShutting down Video Processor...")
            self.running = False

            # Cleanup UDP servers
            for server in self.udp_servers.values():
                server.stop()


def main():
    # Configuration matching the simulator's output
    input_config = {
        0: {"port": 52524, "width": 640, "height": 480, "fps": 30, "format": "mono"},
        1: {"port": 52523, "width": 1280, "height": 720, "fps": 60, "format": "stereo"},
    }

    processor = VideoProcessor(input_config, output_udp_base_port=8554)
    processor.start()


if __name__ == "__main__":
    main()
