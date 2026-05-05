import threading
import time
from typing import Dict

import av
import numpy as np
from back_pressure_queue import BackpressureQueue
from data_interface.frame_metadata import FrameMetadata
from filters.basic_filters import Filter
from streaming.video_stream_base import VideoStreamBase

from common.network.network_type import NetworkEnum


class RTPClient(VideoStreamBase):
    """Robust RTSP client using PyAV with reconnect + backpressure-safe decode"""

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
        self.stream_name = input_config.get("stream_name", "")
        self.filter = filter
        self.frame_queue = frame_queue

        self.max_consecutive_failures = resilience_config.get(
            "max_consecutive_failures", 10
        )
        self.extended_cooldown_s = (
            resilience_config.get("extended_cooldown_ms", 60000) / 1000.0
        )

    def start(self):
        self.running = True
        threading.Thread(target=self.receive_rtp_stream, daemon=True).start()

    # -------------------------
    # Decode loop (single connection lifecycle)
    # -------------------------
    def decode_frames(self):
        rtsp_url = f"rtsp://{self.host_ip}:{self.port}/{self.stream_name}"

        container = None
        try:
            print(f"[RTP] Opening stream: {rtsp_url}")

            container = av.open(
                rtsp_url,
                options={
                    "rtsp_flags": "prefer_tcp",
                    "stimeout": "15000000",
                    "buffer_size": "2097152",
                    "allowed_media_types": "video",
                },
            )

            frames_processed = 0
            last_log = time.time()

            # Correct PyAV API (avoids demux/decode misuse)
            for frame in container.decode(video=0):
                if not self.running:
                    break

                if frame is None:
                    continue

                img = frame.to_ndarray(format="bgr24")
                img = np.ascontiguousarray(img)
                img = self.filter.apply(img)

                self.frame_counter += 1
                frames_processed += 1

                metadata = self._create_frame_metadata()

                # Backpressure-safe enqueue (never block decode thread)
                self.frame_queue.put((img, metadata))

                if time.time() - last_log > 2:
                    print(
                        f"[RTP] stream={self.stream_id} "
                        f"frames={frames_processed} "
                        f"queue={self.frame_queue.qsize()}"
                    )
                    last_log = time.time()

        finally:
            if container:
                container.close()

    # -------------------------
    # Supervisor loop
    # -------------------------
    def receive_rtp_stream(self):
        print(f"[RTP] Receiver started stream={self.stream_id} port={self.port}")

        failures = 0

        while self.running:
            try:
                self.decode_frames()
                failures = 0

            except Exception as e:
                print(f"[RTP] Unexpected error: {e}")
                failures += 1

            if failures >= self.max_consecutive_failures:
                print(f"[RTP] Cooldown {self.extended_cooldown_s}s")
                time.sleep(self.extended_cooldown_s)
                failures = 0
            else:
                time.sleep(0.5)

    # -------------------------
    # metadata
    # -------------------------
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
