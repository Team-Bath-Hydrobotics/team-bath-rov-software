import queue
import select
import subprocess
import time
from typing import Dict

from back_pressure_queue import BackpressureQueue
from mpegts.mpegts_base import MPEGTSBase

from common.common.network.network_type import NetworkEnum


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
    ):
        super().__init__(
            stream_id, port, input_config, output_config, frame_queue, network_type
        )
        self.target_ip = target_ip

    def start(self):
        """Start the MPEGTS server"""
        self.running = True
        self.start_server()

    def start_server(self):
        """Start the MPEGTS server using FFmpeg"""
        print(f"Starting MPEGTS server for stream {self.stream_id} on port {self.port}")

        print(f"Target IP: {self.target_ip}, Network Type: {self.network_type.name}")
        # Get FFmpeg encode command and add UDP output
        ffmpeg_cmd = self.get_ffmpeg_encode_cmd() + [
            f"{self.network_type.value}://{self.target_ip}:{self.port}"
        ]

        try:
            # Start FFmpeg process
            self.ffmpeg_process = subprocess.Popen(
                ffmpeg_cmd, stdin=subprocess.PIPE, stderr=subprocess.PIPE
            )

            frames_sent = 0
            last_status_time = time.time()
            last_frame_time = time.time()

            print(f"MPEGTS stream {self.stream_id} started")

            while self.running and self.ffmpeg_process.poll() is None:
                try:
                    # Get frame and metadata from queue
                    frame_data, metadata = self.frame_queue.get(timeout=1.0)

                    # Throttle to target FPS
                    last_frame_time = self.throttle_fps(last_frame_time)

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

                                # Log status periodically
                                last_status_time = self.log_status(
                                    frames_sent, last_status_time
                                )
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
                    print(f"Error in server for stream {self.stream_id}: {e}")
                    break

        except Exception as e:
            print(f"Error starting server for stream {self.stream_id}: {e}")
        finally:
            self.cleanup_ffmpeg()

    def throttle_fps(self, last_frame_time):
        """Throttle frame processing to target FPS"""
        current_time = time.time()
        time_since_last = current_time - last_frame_time

        if time_since_last < self.frame_interval:
            time.sleep(self.frame_interval - time_since_last)

        return time.time()
