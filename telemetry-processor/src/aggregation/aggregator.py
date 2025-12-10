"""Aggregator for combining telemetry data over time windows."""

from collections import deque
from dataclasses import dataclass
from typing import Callable, Optional


@dataclass
class AggregationResult:
    """Result of an aggregation operation."""

    sensor_name: str
    timestamp: float
    mean: float
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

        # Store data per sensor_name
        self._buffers: dict[str, deque] = {}
        self._last_emit: dict[str, float] = {}

    def add(self, data):
        """Add telemetry data point to aggregation buffer."""
        sensor_name = data.sensor_name

        if sensor_name not in self._buffers:
            self._buffers[sensor_name] = deque()
            self._last_emit[sensor_name] = data.timestamp
        self._buffers[sensor_name].append(data)

        # Check if window has elapsed
        elapsed = (data.timestamp - self._last_emit[sensor_name]) * 1000
        if elapsed >= self.window_duration_ms:
            self._emit_aggregation(sensor_name, data.timestamp)

    def _emit_aggregation(self, sensor_name: str, current_time: float):
        """Compute and emit aggregation for a sensor."""
        buffer = self._buffers[sensor_name]
        if not buffer:
            return

        values = [d.value for d in buffer]
        unit = buffer[0].unit if buffer else None

        result = AggregationResult(
            sensor_name=sensor_name,
            timestamp=current_time,
            mean=sum(values) / len(values),
            unit=unit,
        )

        if self.emit_callback:
            self.emit_callback(result)

        # Clear buffer and update last emit time
        self._buffers[sensor_name].clear()
        self._last_emit[sensor_name] = current_time

    def flush(self, sensor_name: Optional[str] = None):
        """Flush aggregation buffers."""
        if sensor_name:
            if sensor_name in self._buffers and self._buffers[sensor_name]:
                last_time = self._buffers[sensor_name][-1].timestamp
                self._emit_aggregation(sensor_name, last_time)
        else:
            for s_name in list(self._buffers.keys()):
                self.flush(s_name)
