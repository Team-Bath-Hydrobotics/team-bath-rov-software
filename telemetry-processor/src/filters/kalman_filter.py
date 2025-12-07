"""Kalman filter implementation for telemetry smoothing."""
from filters.base_filter import BaseFilter

from common.data_interface import TelemetryData


class KalmanFilter(BaseFilter):
    """Simple 1D Kalman filter for telemetry data smoothing."""

    def __init__(
        self,
        process_variance: float = 1e-5,
        measurement_variance: float = 1e-2,
        initial_estimate: float = 0.0,
        initial_error: float = 1.0,
    ):
        """Initialize Kalman filter.

        Args:
            process_variance: Q - process noise covariance.
            measurement_variance: R - measurement noise covariance.
            initial_estimate: Initial state estimate.
            initial_error: Initial estimation error covariance.
        """
        self.q = process_variance
        self.r = measurement_variance

        self.x = initial_estimate  # State estimate
        self.p = initial_error  # Estimation error covariance

        self._initial_estimate = initial_estimate
        self._initial_error = initial_error
        self._initialized = False

    def apply(self, data: TelemetryData) -> TelemetryData:
        """Apply Kalman filter to telemetry data.

        Args:
            data: Input telemetry data point.

        Returns:
            Filtered telemetry data point.
        """
        measurement = data.value

        # Initialize with first measurement
        if not self._initialized:
            self.x = measurement
            self._initialized = True
            return data

        # Prediction step
        x_pred = self.x
        p_pred = self.p + self.q

        # Update step
        k = p_pred / (p_pred + self.r)  # Kalman gain
        self.x = x_pred + k * (measurement - x_pred)
        self.p = (1 - k) * p_pred

        # Return filtered data
        return TelemetryData(
            timestamp=data.timestamp,
            sensor_id=data.sensor_id,
            value=float(self.x),
            unit=data.unit,
            metadata=data.metadata,
        )

    def reset(self):
        """Reset filter to initial state."""
        self.x = self._initial_estimate
        self.p = self._initial_error
        self._initialized = False
