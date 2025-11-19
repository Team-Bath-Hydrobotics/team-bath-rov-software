import socket
import subprocess
import threading
import time
from typing import Dict

import numpy as np
from back_pressure_queue import BackpressureQueue
from data_interface.frame_metadata import FrameMetadata
from data_interface.network_type import NetworkEnum, NetworkHandler
from mpegts.mpegts_base import MPEGTSBase


class MPEGTSClient(MPEGTSBase):
    """MPEGTS client to receive and decode video streams"""

    def __init__(
        self,
        host_ip: str,
        stream_id: int,
        port: int,
        input_config: Dict,
        output_config: Dict,
        network_type: NetworkEnum,
        frame_queue: BackpressureQueue,
    ):
        super().__init__(
            stream_id, port, input_config, output_config, frame_queue, network_type
        )
        self.host_ip = host_ip

    def start(self):
        """Start receiving MPEGTS stream"""
        self.running = True
        thread = threading.Thread(
            target=lambda: self.receive_mpegts_stream(), daemon=True
        )
        thread.start()

    def forward_to_ffmpeg(self, ffmpeg_process, client_socket):
        """Forward data from socket to FFmpeg stdin — robust to races"""
        try:
            while self.running:
                try:
                    data = client_socket.recv(8192)
                except OSError as e:
                    print(f"Socket recv error for stream {self.stream_id}: {e}")
                    break

                if not data:
                    break

                # Acquire lock and check stdin is alive before writing
                with self.lock:
                    proc = self.ffmpeg_process
                    stdin = None
                    if proc:
                        stdin = proc.stdin

                    if not proc or not stdin:
                        # FFmpeg went away while we were receiving data -> stop forwarding
                        print(
                            f"FFmpeg not available for stream {self.stream_id}, stopping forward thread."
                        )
                        break

                    try:
                        stdin.write(data)
                        stdin.flush()
                    except ValueError:
                        # broken pipe / closed file
                        print(
                            f"Broken pipe to FFmpeg stdin for stream {self.stream_id}"
                        )
                        break
                    except Exception as e:
                        print(
                            f"Error writing to FFmpeg stdin for stream {self.stream_id}: {e}"
                        )
                        break
        except Exception as e:
            print(f"Error forwarding data to FFmpeg for stream {self.stream_id}: {e}")
        finally:
            with self.lock:
                proc = getattr(self, "ffmpeg_process", None)
                if proc and proc.stdin:
                    try:
                        proc.stdin.close()
                    except Exception:
                        pass

    def start_ffmpeg(self):
        """Start a fresh FFmpeg process for decoding (thread-safe)"""
        with self.lock:
            print(f"Stream {self.stream_id}: Acquired lock in start_ffmpeg()")

            try:
                print(f"Stream {self.stream_id}: Starting cleanup_ffmpeg()")
                self.cleanup_ffmpeg()
                print(f"Stream {self.stream_id}: Cleanup completed")
            except Exception as e:
                print(f"Stream {self.stream_id}: Cleanup exception: {e}")

            ffmpeg_cmd = self.get_ffmpeg_decode_cmd()
            print(f"Stream {self.stream_id}: FFmpeg command: {' '.join(ffmpeg_cmd)}")

            try:
                self.ffmpeg_process = subprocess.Popen(
                    ffmpeg_cmd,
                    stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    bufsize=0,  # unbuffered for pipes
                )
                print(f"Stream {self.stream_id}: FFmpeg PID: {self.ffmpeg_process.pid}")

                self.ffmpeg_alive = True

            except Exception as e:
                print(f"Stream {self.stream_id}: Exception in subprocess.Popen: {e}")
                self.ffmpeg_process = None
                self.ffmpeg_alive = False
                raise

    def decode_frames(self, frame_size):
        frames_processed = 0
        last_status_time = time.time()
        print(f"Starting frame decode loop for stream {self.stream_id}")
        while (
            self.running and self.ffmpeg_process and self.ffmpeg_process.poll() is None
        ):
            remaining = frame_size
            chunks = []
            while remaining > 0:
                chunk = self.ffmpeg_process.stdout.read(remaining)
                if not chunk:
                    break
                chunks.append(chunk)
                remaining -= len(chunk)

            frame_data = b"".join(chunks)
            if len(frame_data) != frame_size:
                if len(frame_data) == 0:
                    print(f"No more data from FFmpeg for stream {self.stream_id}")
                else:
                    print(
                        f"Incomplete frame data for stream {self.stream_id}: {len(frame_data)}/{frame_size}"
                    )
                break

            if len(frame_data) != frame_size:
                if len(frame_data) == 0:
                    print(f"No more data from FFmpeg for stream {self.stream_id}")
                else:
                    print(f"Incomplete frame data: {len(frame_data)}/{frame_size}")
                break

            try:
                frame = np.frombuffer(frame_data, dtype=np.uint8)
                frame = frame.reshape(
                    (self.input_height, self.input_width, 3)
                )  # Default use BGR

            except Exception as e:
                print(f"Failed to parse frame for stream {self.stream_id}: {e}")
                break
            self.frame_counters[self.stream_id] += 1
            frames_processed += 1

            metadata = FrameMetadata(
                frame_id=self.frame_counters[self.stream_id],
                timestamp_received=time.time(),
                camera_type=self.input_format,
                stream_id=self.stream_id,
                original_fps=self.input_fps,
                target_fps=self.output_fps,
                input_width=self.input_width,
                input_height=self.input_height,
                output_width=self.output_width,
                output_height=self.output_height,
            )

            self.frame_queue.put((frame, metadata))
            last_status_time = self.log_status(frames_processed, last_status_time)

    def receive_mpegts_stream(self):
        """Main loop: connect, forward, decode, and reconnect if needed"""
        print(
            f"Starting MPEGTS receiver for stream {self.stream_id} on port {self.port}"
        )

        while self.running:
            print("Trying to receive MPEGTS stream...")
            client_socket = None
            try:
                network_handler = NetworkHandler(self.network_type, NetworkEnum.NONE)
                client_socket = network_handler.get_input_network_socket()

                if client_socket is None:
                    raise RuntimeError("NetworkHandler returned no socket")
                try:
                    client_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                except Exception:
                    print(
                        f"Could not set SO_REUSEADDR on socket for stream {self.stream_id}"
                    )
                    pass

                if self.network_type == NetworkEnum.UDP:
                    # Bind UDP listener to receive MPEGTS
                    client_socket.bind((self.host_ip, self.port))
                    print(
                        f"UDP listener bound for stream {self.stream_id} on port {self.port}"
                    )
                else:
                    # Wait until simulator accepts tcp connection
                    connected = False
                    while self.running and not connected:
                        try:
                            client_socket.connect((self.host_ip, self.port))
                            connected = True
                            print(
                                f"Connected to stream {self.stream_id} on port {self.port}"
                            )
                        except (ConnectionRefusedError, OSError):
                            print(
                                f"TCP: stream {self.stream_id} waiting for simulator on port {self.port}..."
                            )
                            time.sleep(1)

                if not self.running:
                    break
                print(
                    f"Stream {self.stream_id}: Connection established, starting FFmpeg..."
                )

                # Start fresh FFmpeg process
                self.start_ffmpeg()
                print(f"Stream {self.stream_id}: FFmpeg started, checking process...")
                if self.ffmpeg_process:
                    print(
                        f"Stream {self.stream_id}: FFmpeg process PID: {self.ffmpeg_process.pid}"
                    )
                    print(
                        f"Stream {self.stream_id}: FFmpeg poll status: {self.ffmpeg_process.poll()}"
                    )
                else:
                    print(f"Stream {self.stream_id}: ERROR - FFmpeg process is None!")
                    break

                # Start forwarding thread
                forward_thread = threading.Thread(
                    target=self.forward_to_ffmpeg,
                    args=(self.ffmpeg_process, client_socket),
                    daemon=True,
                )
                forward_thread.start()

                frame_size = self.get_frame_size(is_input=True)
                print(f"Stream {self.stream_id}: Calculating frame size: {frame_size}")
                if frame_size <= 0:
                    print(
                        f"Invalid frame size {frame_size} for stream {self.stream_id}; aborting decode."
                    )
                    break
                print(
                    f"Stream {self.stream_id}: About to call decode_frames({frame_size})"
                )
                self.decode_frames(frame_size)

            except Exception as e:
                print(f"Error in MPEGTS receiver for stream {self.stream_id}: {e}")
                time.sleep(2)
            finally:
                if client_socket:
                    try:
                        client_socket.close()
                    except Exception as e:
                        print(f"Error closing socket for stream {self.stream_id}: {e}")
                        pass
                with self.lock:
                    self.cleanup_ffmpeg()
                if self.running:
                    print(
                        f"Stream {self.stream_id}: Attempting to reconnect in 2 seconds..."
                    )
                    time.sleep(2)
