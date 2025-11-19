from dataclasses import dataclass


@dataclass
class FrameMetadata:
    frame_id: int
    timestamp_received: float
    camera_type: str
    stream_id: int
    original_fps: int
    target_fps: int
    input_width: int
    input_height: int
    output_width: int
    output_height: int
