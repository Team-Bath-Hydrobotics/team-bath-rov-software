"""Unit tests for filters.kalman_filter."""

import numpy as np
import pytest
from filters.base_filter import BaseFilter
from filters.kalman_filter import KalmanFilter
from common.data_interface import TelemetryData


def reading(value, ts=1.0, sensor="depth", unit="m"):
    return TelemetryData(timestamp=ts, sensor_name=sensor, value=value, unit=unit)


class TestInit:
    def test_is_a_base_filter(self):
        assert isinstance(KalmanFilter(), BaseFilter)
    #Ensures KalmanFilter object is built correctly according to interface

    def test_default_parameters(self):
        kf = KalmanFilter()
        assert kf.q == 1e-5
        assert kf.r == 1e-2
        assert kf.x == 0.0
        assert kf.p == 1.0
        assert kf._initialized is False
    #Does what it says on the tin

    def test_custom_parameters(self):
        kf = KalmanFilter(
            process_variance=0.1,
            measurement_variance=0.2,
            initial_estimate=3.0,
            initial_error=4.0,
        )
        assert (kf.q, kf.r, kf.x, kf.p) == (0.1, 0.2, 3.0, 4.0)
    #Constructor arguments are stored


class TestFirstMeasurement:
    def test_returned_unchanged(self):
        kf = KalmanFilter()
        data = reading(42.0)
        assert kf.apply(data) is data
    #This proves that the first argumentis passed straight through because filteringhas nothing to compare it wiht

    def test_seeds_state_with_measurement(self):
        kf = KalmanFilter(initial_estimate=0.0, initial_error=1.0)
        kf.apply(reading(42.0))
        assert kf.x == 42.0
        assert kf.p == 1.0  
        assert kf._initialized is True
    #The estimate x is set to the first reading and p is left alone

class TestUpdateStep:
    def test_matches_hand_calculated_kalman_update(self):
        q, r = 1e-3, 1e-1
        kf = KalmanFilter(process_variance=q, measurement_variance=r)
        kf.apply(reading(10.0))  #x=10, p=1

        p_pred = 1.0 + q
        gain = p_pred / (p_pred + r)
        expected_x = 10.0 + gain * (12.0 - 10.0)
        expected_p = (1 - gain) * p_pred

        out = kf.apply(reading(12.0))

        assert out.value == pytest.approx(expected_x)
        assert kf.x == pytest.approx(expected_x)
        assert kf.p == pytest.approx(expected_p)
    #

    def test_output_preserves_metadata_and_is_a_new_object(self):
        kf = KalmanFilter()
        kf.apply(reading(1.0))
        data = reading(2.0, ts=99.5, sensor="pressure", unit="Pa")
        out = kf.apply(data)

        assert out is not data
        assert (out.timestamp, out.sensor_name, out.unit) == (99.5, "pressure", "Pa")
    #Verifies that apply creates a brand new object while maintaining all original background details

    def test_input_is_not_mutated(self):
        kf = KalmanFilter()
        kf.apply(reading(1.0))
        data = reading(50.0)
        kf.apply(data)
        assert data.value == 50.0
    #verifies that passing a data object into the KalmanFilter does not accidentally alter the original input data

    def test_output_value_is_python_float(self):
        kf = KalmanFilter()
        kf.apply(reading(1))
        out = kf.apply(reading(2))  # int measurement
        assert isinstance(out.value, float)

    def test_estimate_never_overshoots_the_measurement(self):
        kf = KalmanFilter()
        kf.apply(reading(0.0))
        out = kf.apply(reading(10.0))
        assert 0.0 < out.value <= 10.0

    def test_converges_to_a_new_constant_level(self):
        kf = KalmanFilter()
        kf.apply(reading(0.0))
        values = [kf.apply(reading(10.0)).value for _ in range(100)]

        assert values == sorted(values)  # monotonic approach, no overshoot
        assert values[-1] == pytest.approx(10.0, abs=0.1)

    def test_error_covariance_shrinks_with_consistent_data(self):
        kf = KalmanFilter()
        kf.apply(reading(5.0))
        p_values = []
        for _ in range(20):
            kf.apply(reading(5.0))
            p_values.append(kf.p)
        assert p_values[-1] < p_values[0] < 1.0

    def test_smooths_noisy_signal(self):
        rng = np.random.default_rng(42)
        noise_sd = 0.5
        raw = 20.0 + rng.normal(0, noise_sd, 500)

        kf = KalmanFilter(process_variance=1e-5, measurement_variance=noise_sd**2)
        filtered = np.array([kf.apply(reading(float(v))).value for v in raw])

        assert np.var(filtered[50:]) < np.var(raw[50:])
        assert np.mean(filtered[50:]) == pytest.approx(20.0, abs=0.2)

    def test_higher_measurement_variance_trusts_new_data_less(self):
        trusting, sceptical = KalmanFilter(measurement_variance=1e-3), KalmanFilter(
            measurement_variance=10.0
        )
        for kf in (trusting, sceptical):
            kf.apply(reading(0.0))

        assert (
            trusting.apply(reading(10.0)).value > sceptical.apply(reading(10.0)).value
        )

    def test_handles_negative_and_zero_values(self):
        kf = KalmanFilter()
        kf.apply(reading(-5.0))
        assert kf.apply(reading(-5.0)).value == pytest.approx(-5.0)
        assert kf.apply(reading(0.0)).value > -5.0

    def test_instances_do_not_share_state(self):
        a, b = KalmanFilter(), KalmanFilter()
        a.apply(reading(100.0))
        assert b._initialized is False
        assert b.x == 0.0


class TestReset:
    def test_restores_initial_state(self):
        kf = KalmanFilter(initial_estimate=2.0, initial_error=3.0)
        kf.apply(reading(10.0))
        kf.apply(reading(11.0))
        kf.reset()

        assert kf.x == 2.0
        assert kf.p == 3.0
        assert kf._initialized is False

    def test_behaves_like_new_filter_after_reset(self):
        kf = KalmanFilter()
        kf.apply(reading(10.0))
        kf.apply(reading(12.0))
        kf.reset()

        data = reading(500.0)
        assert kf.apply(data) is data  # first-measurement path again
        assert kf.x == 500.0

    def test_reset_on_fresh_filter_is_harmless(self):
        kf = KalmanFilter()
        kf.reset()
        assert (kf.x, kf.p, kf._initialized) == (0.0, 1.0, False)

    def test_reset_then_same_inputs_reproduce_same_outputs(self):
        kf = KalmanFilter()
        inputs = [1.0, 2.0, 3.0, 2.5, 2.0]
        first = [kf.apply(reading(v)).value for v in inputs]
        kf.reset()
        second = [kf.apply(reading(v)).value for v in inputs]
        assert second == pytest.approx(first)

#All above functions test Kalman filter 
#Two seperate types
#1 type is testing the mathematical behaviour of Kalmane
#2 type is checking that the filtercleans up after it is used and doesn't hold on to useless memory