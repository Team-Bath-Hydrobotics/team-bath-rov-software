import queue
import select
import subprocess
import time
from typing import Dict
import threading
from back_pressure_queue import BackpressureQueue
from mpegts.mpegts_base import MPEGTSBase

from common.network.network_type import NetworkEnum
from .websocket_broadcaster import WebSocketBroadcaster

class MPEGTSServer(MPEGTSBase):
    """MPEGTS server using FFmpeg"""

    def __init__(
        self,
        target_ip: str,
        stream_id: int,
        port: int,
        input_config: Dict,
        output_config: Dict,
        frame_queue: BackpressureQueue,
        network_type: NetworkEnum,
        ws_relay_enabled: bool = False,
        ws_relay_base_port: int = None,
    ):
        super().__init__(
            stream_id, port, input_config, output_config, frame_queue, network_type
        )
        self.target_ip = target_ip
        self.ws_broadcaster = None
        if ws_relay_enabled and ws_relay_base_port:
            self.ws_broadcaster = WebSocketBroadcaster(stream_id, ws_relay_base_port)
            self.ws_broadcaster.start()
            if not self.ws_broadcaster._loop_ready.wait(timeout=5):
                raise RuntimeError("WebSocketBroadcaster failed to start")

    def start(self):
        """Start the MPEGTS server"""
        self.running = True
        self.ffmpeg_thread = threading.Thread(target=self._run_ffmpeg)
        self.ffmpeg_thread.start()

    def _run_ffmpeg(self):
        """Start the MPEGTS server using FFmpeg"""
        print(f"Starting MPEGTS server for stream {self.stream_id} on port {self.port}")

        print(f"Target IP: {self.target_ip}, Network Type: {self.network_type.name}")
        # Get FFmpeg encode command and add UDP output
        outputs = []
        if self.target_ip:
            outputs.append(f"[f=mpegts]udp://{self.target_ip}:{self.port}")
        if self.ws_broadcaster:
            outputs.append("[f=mpegts]pipe:1")

        tee = "|".join(outputs)
        print(f"Stream {self.stream_id}, expected width height fps: {self.output_width}x{self.output_height} @ {self.output_fps}fps")
        cmd = [
            "ffmpeg",
            "-loglevel", "error",

            "-f", "rawvideo",
            "-pix_fmt", "bgr24",
            "-s", f"{self.input_width}x{self.input_height}",
            "-r", str(self.input_fps),
            "-i", "pipe:0",

            "-map", "0:v:0",              # <-- REQUIRED
            "-c:v", "mpeg1video",
            "-b:v", "1000k",

            "-f", "tee",
            tee,                           # <-- NO quotes
        ]
        
        try:
            # Start FFmpeg process
            assert "-f" in cmd and "tee" in cmd, "Encoder FFmpeg command corrupted"
            print(f"Stream {self.stream_id} ENCODER CMD:", " ".join(cmd))
            self.encoder_ffmpeg_process = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE if self.ws_broadcaster else None,
            )

            print(f"MPEGTS stream {self.stream_id} started")

            self.writer_thread = threading.Thread(target=self._write_frames)
            self.writer_thread.start()
            if self.ws_broadcaster:
                self.std_out_thread = threading.Thread(target=self._read_stdout)
                self.std_out_thread.start()
        except Exception as e:
            print(f"Failed to start MPEGTS server for stream {self.stream_id}: {e}")
            self.running = False

    def _write_frames(self):
        """Write frames from backpressure queue to FFmpeg stdin at target FPS"""
        frames_sent = 0
        last_status_time = time.time()
        last_frame_time = time.time()

        while self.running and self.encoder_ffmpeg_process and self.encoder_ffmpeg_process.stdin:
            try:
                try:
                    # Get frame and metadata from queue
                    frame_data, metadata = self.frame_queue.get(timeout=1.0)
                    if frame_data is None:
                        continue

                    # Throttle to target FPS
                    last_frame_time = self.throttle_fps(last_frame_time)
                    # Check if FFmpeg stdin is ready for writing
                    if self.encoder_ffmpeg_process.stdin and not self.encoder_ffmpeg_process.stdin.closed:
                        try:
                            ready = select.select([], [self.encoder_ffmpeg_process.stdin], [], 0.01)
                            if ready[1]:  # stdin is ready
                                self.encoder_ffmpeg_process.stdin.write(frame_data.tobytes())
                                self.encoder_ffmpeg_process.stdin.flush()
                                frames_sent += 1
                                last_status_time = self.log_status(frames_sent, last_status_time)
                            else:
                                # stdin not ready, skip frame
                                pass
                        except (BrokenPipeError, OSError) as e:
                            print(f"FFmpeg process ended for stream {self.stream_id}: {e}")
                            break
                    else:
                        print(f"FFmpeg stdin closed for stream {self.stream_id}")
                        break

                except queue.Empty:
                    continue
                except Exception as e:
                    print(f"Error in server for stream {self.stream_id}: {e}")
                    break
            except Exception as e:
                print(f"Unexpected error writing to FFmpeg stdin: {e}")

    def _read_stdout(self):
        """Read FFmpeg stdout and broadcast over WebSocket"""
        while self.running and self.encoder_ffmpeg_process and self.encoder_ffmpeg_process.stdout:
            try:
                chunk = self.encoder_ffmpeg_process.stdout.read(1316)
                if not chunk:
                    break
                #print(f"Stream {self.stream_id} read {len(chunk)} bytes from stdout")
                self.ws_broadcaster.broadcast(chunk)
            except Exception as e:
                print(f"Error broadcasting stdout: {e}")
                break

    def throttle_fps(self, last_frame_time):
        """Throttle frame processing to target FPS"""
        current_time = time.time()
        time_since_last = current_time - last_frame_time

        if time_since_last < self.frame_interval:
            time.sleep(self.frame_interval - time_since_last)

        return time.time()
    
