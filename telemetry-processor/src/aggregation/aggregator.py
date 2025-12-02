"""Aggregator for combining telemetry data over time windows."""

from collections import deque
from dataclasses import dataclass
from typing import Callable, Optional

from data_interface.telemetry_data import TelemetryData


@dataclass
class AggregationResult:
    """Result of an aggregation operation."""

    sensor_id: str
    timestamp: float
    count: int
    mean: float
    min_value: float
    max_value: float
    unit: Optional[str] = None


class TimeWindowAggregator:
    """Aggregates telemetry data over a sliding time window."""

    def __init__(
        self,
        window_duration_ms: float = 50.0,
        emit_callback: Optional[Callable[[AggregationResult], None]] = None,
    ):
        """Initialize aggregator.

        Args:
            window_duration_ms: Duration of the aggregation window in milliseconds.
            emit_callback: Callback to invoke when aggregation is ready.
        """
        self.window_duration_ms = window_duration_ms
        self.emit_callback = emit_callback

        # Store data per sensor_id
        self._buffers: dict[str, deque] = {}
        self._last_emit: dict[str, float] = {}

    def add(self, data: TelemetryData):
        """Add telemetry data point to aggregation buffer."""
        sensor_id = data.sensor_id

        if sensor_id not in self._buffers:
            self._buffers[sensor_id] = deque()
            self._last_emit[sensor_id] = data.timestamp

        self._buffers[sensor_id].append(data)

        # Check if window has elapsed
        elapsed = (data.timestamp - self._last_emit[sensor_id]) * 1000
        if elapsed >= self.window_duration_ms:
            self._emit_aggregation(sensor_id, data.timestamp)

    def _emit_aggregation(self, sensor_id: str, current_time: float):
        """Compute and emit aggregation for a sensor."""
        buffer = self._buffers[sensor_id]
        if not buffer:
            return

        values = [d.value for d in buffer]
        unit = buffer[0].unit if buffer else None

        result = AggregationResult(
            sensor_id=sensor_id,
            timestamp=current_time,
            count=len(values),
            mean=sum(values) / len(values),
            min_value=min(values),
            max_value=max(values),
            unit=unit,
        )

        if self.emit_callback:
            self.emit_callback(result)

        # Clear buffer and update last emit time
        self._buffers[sensor_id].clear()
        self._last_emit[sensor_id] = current_time

    def flush(self, sensor_id: Optional[str] = None):
        """Flush aggregation buffers."""
        if sensor_id:
            if sensor_id in self._buffers and self._buffers[sensor_id]:
                last_time = self._buffers[sensor_id][-1].timestamp
                self._emit_aggregation(sensor_id, last_time)
        else:
            for sid in list(self._buffers.keys()):
                self.flush(sid)
