import threading
import time
from abc import ABC, abstractmethod
from typing import Dict

from back_pressure_queue import BackpressureQueue

from common.common.network.network_type import NetworkEnum


class MPEGTSBase(ABC):
    """Base class for MPEGTS client and server components"""

    def __init__(
        self,
        stream_id: int,
        port: int,
        input_config: Dict,
        output_config: Dict,
        frame_queue: BackpressureQueue,
        network_type: NetworkEnum,
    ):
        self.stream_id = stream_id
        self.port = port
        self.frame_queue = frame_queue
        self.network_type = network_type
        self.running = False
        self.ffmpeg_process = None
        (
            self.input_width,
            self.input_height,
            self.input_fps,
            self.input_format,
        ) = self.extract_feed_settings(input_config)
        (
            self.output_width,
            self.output_height,
            self.output_fps,
            self.output_format,
        ) = self.extract_feed_settings(output_config)
        self.frame_interval = (
            1.0 / self.output_fps if self.output_fps > 0 else 0.033
        )  # Default to ~30 FPS
        self.frame_counters = {}
        self.ffmpeg_alive = False
        self.lock = threading.Lock()

        if stream_id not in self.frame_counters:
            self.frame_counters[stream_id] = 0

    @abstractmethod
    def start(self):
        """Start the MPEGTS component (client or server)"""
        pass

    def stop(self):
        if not self.running:
            return

        print(f"Stopping MPEGTS component for stream {self.stream_id}")
        self.running = False
        self.cleanup_ffmpeg()

    def cleanup_ffmpeg(self):
        """Stop and clean up ffmpeg process safely"""
        proc = getattr(self, "ffmpeg_process", None)
        if proc:
            try:
                if proc.stdin:
                    try:
                        proc.stdin.close()
                    except Exception:
                        pass
                try:
                    proc.terminate()
                except Exception:
                    pass
                try:
                    proc.wait(timeout=0.5)
                except Exception:
                    try:
                        proc.kill()
                    except Exception:
                        pass
            except Exception:
                pass
        self.ffmpeg_process = None
        self.ffmpeg_alive = False

    def get_frame_size(self, is_input=True):
        """Calculate frame size in bytes for BGR24 format"""
        if self.input_format in ("gray"):
            channels = 1
        else:
            channels = 3
        if is_input:
            return self.input_width * self.input_height * channels
        else:
            return self.output_width * self.output_height * channels

    def get_ffmpeg_decode_cmd(self):
        """Get standard FFmpeg decode command for MPEGTS input"""
        return [
            "ffmpeg",
            "-loglevel",
            "error",
            "-i",
            "pipe:0",
            "-f",
            "rawvideo",  # Output raw video
            "-pix_fmt",
            "bgr24",  # BGR24 pixel format
            "-an",  # No audio
            "pipe:1",  # Output to stdout
        ]

    def get_ffmpeg_encode_cmd(self, is_input=True):
        """Get standard FFmpeg encode command for raw video input"""
        if not is_input:
            width = self.output_width
            height = self.output_height
            fps = self.output_fps
        else:
            width = self.input_width
            height = self.input_height
            fps = self.input_fps

        return [
            "ffmpeg",
            "-loglevel",
            "error",
            "-f",
            "rawvideo",
            "-vcodec",
            "rawvideo",
            "-pix_fmt",
            "bgr24",
            "-s",
            f"{width}x{height}",
            "-r",
            str(fps),
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
            str(fps),
            "-f",
            "mpegts",
        ]

    def log_status(self, frames_count, last_status_time, interval=5.0):
        """Log status messages at regular intervals"""
        current_time = time.time()
        if current_time - last_status_time >= interval:
            print(f"Stream {self.stream_id}: Processed {frames_count} frames")
            return current_time
        return last_status_time

    def extract_feed_settings(self, config):
        """Extract feed settings from config"""
        return (
            config.get("width", 640),
            config.get("height", 480),
            config.get("fps", 30),
            config.get("format", "mono"),
        )
