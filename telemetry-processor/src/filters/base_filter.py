"""Base filter interface for telemetry filtering."""

from abc import ABC, abstractmethod

from data_interface.telemetry_data import TelemetryData


class BaseFilter(ABC):
    """Abstract base class for telemetry filters."""

    @abstractmethod
    def apply(self, data: TelemetryData) -> TelemetryData:
        """Apply the filter to telemetry data.

        Args:
            data: Input telemetry data point.

        Returns:
            Filtered telemetry data point.
        """
        pass

    @abstractmethod
    def reset(self):
        """Reset filter state."""
        pass
