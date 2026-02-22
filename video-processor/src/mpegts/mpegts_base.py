import threading
import subprocess
import time
from abc import ABC, abstractmethod
from typing import Dict, Optional


class MPEGTSBase(ABC):
    """Base class for MPEG-TS streaming components"""

    def __init__(
        self,
        stream_id: int,
        port: int,
        input_config: Dict,
        output_config: Dict,
        frame_queue=None,
        network_type=None,
    ):
        self.stream_id = stream_id
        self.port = port
        self.frame_queue = frame_queue
        self.network_type = network_type

        self.running = False
        self.encoder_ffmpeg_process: Optional[subprocess.Popen] = None
        self.decoder_ffmpeg_process: Optional[subprocess.Popen] = None
        self.encoder_ffmpeg_alive = False
        self.decoder_ffmpeg_alive = False
        self.lock = threading.Lock()

        self.input_width = input_config.get("width", 640)
        self.input_height = input_config.get("height", 480)
        self.input_fps = input_config.get("fps", 30)
        self.input_format = input_config.get("format", "bgr")

        self.output_width = output_config.get("width", self.input_width)
        self.output_height = output_config.get("height", self.input_height)
        self.output_fps = output_config.get("fps", self.input_fps)
        self.output_format = output_config.get("format", self.input_format)

        self.frame_interval = 1.0 / self.output_fps if self.output_fps > 0 else 1.0 / 30
        self.frame_counter = 0

    @abstractmethod
    def start(self):
        raise NotImplementedError

    def stop(self):
        self.running = False
        self.cleanup_encoder_ffmpeg()

    def _graceful_stop_ffmpeg(self, proc: Optional[subprocess.Popen], name: str):
        if not proc:
            return

        try:
            if proc.stdin:
                proc.stdin.close()
        except Exception:
            pass

        try:
            proc.wait(timeout=2.0)
            return
        except subprocess.TimeoutExpired:
            pass

        try:
            proc.terminate()
            proc.wait(timeout=1.0)
        except Exception:
            try:
                proc.kill()
            except Exception:
                pass

    def cleanup_encoder_ffmpeg(self):
        self._graceful_stop_ffmpeg(self.encoder_ffmpeg_process, "encoder")
        self.encoder_ffmpeg_process = None

    def cleanup_decoder_ffmpeg(self):
        self._graceful_stop_ffmpeg(self.decoder_ffmpeg_process, "decoder")
        self.decoder_ffmpeg_process = None

    def log_status(self, last_time: float, interval: float = 5.0):
        now = time.time()
        if now - last_time >= interval:
            #print(f"[Stream {self.stream_id}] Frames processed: {self.frame_counter}")
            return now
        return last_time
    
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
