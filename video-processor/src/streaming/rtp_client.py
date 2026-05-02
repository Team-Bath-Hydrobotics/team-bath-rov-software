import random
import subprocess
import sys
import threading
import time
from typing import Dict

import numpy as np
from back_pressure_queue import BackpressureQueue
from data_interface.frame_metadata import FrameMetadata
from filters.basic_filters import Filter
from streaming.video_stream_base import VideoStreamBase

from common.network.network_type import NetworkEnum


class RTPClient(VideoStreamBase):
    """RTP client to receive and decode video streams"""

    def __init__(
        self,
        host_ip: str,
        stream_id: int,
        port: int,
        input_config: Dict,
        output_config: Dict,
        network_type: NetworkEnum,
        frame_queue: BackpressureQueue,
        resilience_config: Dict,
        filter: Filter,
    ):
        super().__init__(
            stream_id, port, input_config, output_config, frame_queue, network_type
        )
        self.host_ip = host_ip
        self.filter = filter
        print(resilience_config)
        self.max_frame_errors = resilience_config.get("max_frame_errors", 100)
        self.base_delay_ms = resilience_config.get("base_delay_ms", 500)
        self.max_delay_ms = resilience_config.get("max_delay_ms", 30000)
        self.max_consecutive_failures = resilience_config.get(
            "max_consecutive_failures", 10
        )
        self.extended_cooldown_ms = resilience_config.get("extended_cooldown_ms", 60000)
        self.target_ip = output_config.get("target_ip", "")

    def start(self):
        """Start receiving RTP stream"""
        self.running = True
        thread = threading.Thread(target=lambda: self.receive_rtp_stream(), daemon=True)
        thread.start()

    def start_decoder_ffmpeg(self):
        """Start a fresh FFmpeg process for decoding (thread-safe)"""
        with self.lock:
            print(f"Stream {self.stream_id}: Acquired lock in start_decoder_ffmpeg()")

            try:
                print(f"Stream {self.stream_id}: Starting cleanup_decoder_ffmpeg()")
                self.cleanup_decoder_ffmpeg()
                print(f"Stream {self.stream_id}: Cleanup completed")
            except Exception as e:
                print(f"Stream {self.stream_id}: Cleanup exception: {e}")

            # RTP H264 input directly from UDP
            cmd = [
                "ffmpeg",
                "-loglevel",
                "error",
                # RTP jitter handling (important for WiFi / Pi)
                "-fflags",
                "nobuffer",
                "-flags",
                "low_delay",
                "-max_delay",
                "500000",  # allow jitter buffer (important)
                "-probesize",
                "10000",
                "-analyzeduration",
                "100000",
                # INPUT: RTP stream
                "-f",
                "rtp",
                "-i",
                f"rtp://0.0.0.0:{self.port}",
                # OUTPUT: raw frames to python
                "-f",
                "rawvideo",
                "-pix_fmt",
                "bgr24",
                "pipe:1",
            ]
            print(f"Stream {self.stream_id}: FFmpeg command: {' '.join(cmd)}")

            try:
                self.decoder_ffmpeg_process = subprocess.Popen(
                    cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE
                )
                print(
                    f"Stream {self.stream_id}: FFmpeg PID: {self.decoder_ffmpeg_process.pid}"
                )

                self.decoder_ffmpeg_alive = True

            except Exception as e:
                print(f"Stream {self.stream_id}: Exception in subprocess.Popen: {e}")
                self.decoder_ffmpeg_process = None
                self.decoder_ffmpeg_alive = False
                raise

    def decode_frames(self, frame_size):
        frames_processed = 0
        frame_errors = 0
        last_status_time = time.time()
        print(f"Starting frame decode loop for stream {self.stream_id}")
        while (
            self.running
            and self.decoder_ffmpeg_process
            and self.decoder_ffmpeg_process.poll() is None
        ):
            frame_data = self._read_frame_data(frame_size)
            if frame_data is None:
                time.sleep(0.01)
                continue

            frame = self._parse_frame(frame_data)
            if frame is None:
                frame_errors += 1
                if frame_errors >= self.max_frame_errors:
                    self._log_too_many_frame_errors()
                    break
                continue

            self.frame_counter += 1
            frames_processed += 1
            frame_errors = 0  # Reset on success

            metadata = self._create_frame_metadata()
            self.frame_queue.put((frame, metadata))
            last_status_time = self.log_status(frames_processed, last_status_time)

    def _read_frame_data(self, frame_size):
        remaining = frame_size
        chunks = []
        while remaining > 0 and self.running:
            chunk = self.decoder_ffmpeg_process.stdout.read(remaining)
            if not chunk:
                break
            chunks.append(chunk)
            remaining -= len(chunk)
        frame_data = b"".join(chunks)
        if len(frame_data) != frame_size:
            print(
                f"Incomplete frame data for stream {self.stream_id}: "
                f"{len(frame_data)}/{frame_size}"
            )
            return None
        return frame_data

    def _parse_frame(self, frame_data):
        try:
            frame = np.frombuffer(frame_data, dtype=np.uint8)
            frame = frame.reshape((self.input_height, self.input_width, 3))
            frame = self.filter.apply(frame)
            return frame
        except Exception as e:
            print(f"Failed to parse frame for stream {self.stream_id}: {e}")
            return None

    def _log_too_many_frame_errors(self):
        print(
            f"Too many consecutive frame errors for stream {self.stream_id}, reconnecting...",
            file=sys.stderr,
        )

    def _create_frame_metadata(self):
        return FrameMetadata(
            frame_id=self.frame_counter,
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

    def receive_rtp_stream(self):
        """Main loop: connect, forward, decode, and reconnect if needed, with disconnect handling"""
        print(f"Starting RTP receiver for stream {self.stream_id} on port {self.port}")
        extended_cooldown = self.extended_cooldown_ms / 1000.0
        consecutive_failures = 0
        current_delay = self.base_delay_ms / 1000.0

        while self.running:
            try:
                if (
                    self.decoder_ffmpeg_process is None
                    or self.decoder_ffmpeg_process.poll() is not None
                ):
                    self._start_and_check_ffmpeg()

                frame_size = self.get_frame_size(is_input=True)
                if frame_size <= 0:
                    raise RuntimeError("Invalid frame size")

                self.decode_frames(frame_size)

                consecutive_failures = 0
                current_delay = self.base_delay_ms / 1000.0

            except Exception as e:
                print(f"Error in RTP receiver for stream {self.stream_id}: {e}")
                consecutive_failures += 1
                self._handle_failure(
                    consecutive_failures, current_delay, extended_cooldown
                )
                if consecutive_failures >= self.max_consecutive_failures:
                    consecutive_failures = 0
                    current_delay = self.base_delay_ms / 1000.0
                else:
                    current_delay = min(current_delay * 2, self.max_delay_ms / 1000.0)
            finally:
                if not self.running:
                    with self.lock:
                        self.cleanup_decoder_ffmpeg()
                if self.running:
                    print(
                        f"Stream {self.stream_id}: Attempting to reconnect in 1 second..."
                    )
                    time.sleep(1)

    def _start_and_check_ffmpeg(self):
        print(f"Stream {self.stream_id}: Connection established, starting FFmpeg...")
        self.start_decoder_ffmpeg()
        print(f"Stream {self.stream_id}: FFmpeg started, checking process...")
        if self.decoder_ffmpeg_process:
            print(
                f"Stream {self.stream_id}: FFmpeg process PID: {self.decoder_ffmpeg_process.pid}"
            )
            print(
                f"Stream {self.stream_id}: FFmpeg poll status: {self.decoder_ffmpeg_process.poll()}"
            )
        else:
            print(f"Stream {self.stream_id}: ERROR - FFmpeg process is None!")
            raise RuntimeError("FFmpeg process is None")

    def _handle_failure(self, consecutive_failures, current_delay, extended_cooldown):
        if consecutive_failures >= self.max_consecutive_failures:
            print(
                f"Max consecutive failures reached for stream {self.stream_id}. Entering extended cooldown ({extended_cooldown}s)...",
                file=sys.stderr,
            )
            time.sleep(extended_cooldown)
        else:
            jitter = random.uniform(0, 0.1 * current_delay)
            delay = min(current_delay + jitter, self.max_delay_ms / 1000.0)
            print(
                f"Reconnecting stream {self.stream_id} in {delay:.2f}s...",
                file=sys.stderr,
            )
            time.sleep(delay)
