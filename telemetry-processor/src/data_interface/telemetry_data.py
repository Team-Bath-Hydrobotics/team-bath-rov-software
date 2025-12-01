"""Telemetry data types."""

from dataclasses import dataclass
from typing import Optional


@dataclass
class TelemetryData:
    """Represents a single telemetry data point."""

    timestamp: float
    sensor_id: str
    value: float
    unit: Optional[str] = None
    metadata: Optional[dict] = None

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "timestamp": self.timestamp,
            "sensor_id": self.sensor_id,
            "value": self.value,
            "unit": self.unit,
            "metadata": self.metadata,
        }
