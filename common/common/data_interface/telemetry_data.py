"""Telemetry data types."""

from dataclasses import dataclass
from typing import Optional


@dataclass
class TelemetryData:
    """Represents a single telemetry data point."""

    timestamp: float
    sensor_name: str
    value: float
    unit: Optional[str] = None

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "timestamp": self.timestamp,
            "sensor_name": self.sensor_name,
            "value": self.value,
            "unit": self.unit,
        }
