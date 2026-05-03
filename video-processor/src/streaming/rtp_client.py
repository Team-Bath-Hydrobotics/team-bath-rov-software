import sys
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
        self.stream_name = input_config.get("stream_name", "")
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

    def decode_frames(self):
        rtsp_url = f"rtsp://{self.host_ip}:{self.port}/{self.stream_name}"

        while self.running:
            container = None
            try:
                print(f"Opening PyAV stream: {rtsp_url}")

                container = av.open(
                    rtsp_url,
                    options={
                        "rtsp_transport": "udp",
                        "fflags": "nobuffer",
                        "flags": "low_delay",
                        "probesize": "32",
                        "analyzeduration": "0",
                        "max_delay": "0",
                        "stimeout": "5000000",
                    },
                )

                stream = container.streams.video[0]
                stream.thread_type = "AUTO"

                frames_processed = 0
                last_status = time.time()

                last_frame_time = time.time()
                for frame in container.decode(stream):
                    if not self.running:
                        break
                    if time.time() - last_frame_time > 5:
                        print(f"Stream {self.stream_id}: decode stall detected")
                        break
                    last_frame_time = time.time()
                    try:
                        if self.frame_queue.qsize() > 50:
                            continue
                        img = frame.to_ndarray(format="bgr24")
                        img = np.ascontiguousarray(img)
                        img = self.filter.apply(img)

                        self.frame_counter += 1
                        frames_processed += 1

                        metadata = self._create_frame_metadata()
                        self.frame_queue.put((img, metadata))

                        last_status = self.log_status(frames_processed, last_status)

                    except Exception as e:
                        print(f"Frame error: {e}")

            except Exception as e:
                print(f"PyAV stream error: {e}")
                time.sleep(1)

            finally:
                if container is not None:
                    container.close()

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
        consecutive_failures = 0
        extended_cooldown = self.extended_cooldown_ms / 1000.0

        while self.running:
            try:
                self.decode_frames()

                consecutive_failures = 0

            except Exception as e:
                print(f"Stream {self.stream_id} error: {e}")
                consecutive_failures += 1

                if consecutive_failures >= self.max_consecutive_failures:
                    print("Extended cooldown")
                    time.sleep(extended_cooldown)
                    consecutive_failures = 0
                else:
                    time.sleep(1)
