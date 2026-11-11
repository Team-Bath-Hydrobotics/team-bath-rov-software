"""Unit tests for the time-window aggregator."""

import pytest
from aggregation.aggregator import TimeWindowAggregator

from common.data_interface import TelemetryData


def make_data(value, ts, sensor="gyro", unit="deg"):
    return TelemetryData(timestamp=ts, sensor_name=sensor, value=value, unit=unit)


@pytest.fixture
def results():
    return []


@pytest.fixture
def agg(results):
    """1000 ms window; every emitted AggregationResult is appended to `results`."""
    return TimeWindowAggregator(window_duration_ms=1000, emit_callback=results.append)


class TestWindowing:
    def test_no_emit_before_window_elapses(self, agg, results):
        agg.add(make_data(1, 0.0))
        agg.add(make_data(2, 0.999))
        assert results == []

    def test_emits_exactly_at_window_boundary(self, agg, results):
        agg.add(make_data(1, 0.0))
        agg.add(make_data(3, 1.0))  # elapsed == 1000 ms and the check is >=
        assert len(results) == 1

    def test_first_sample_cannot_emit_on_its_own(self, agg, results):
        agg.add(make_data(5, 1000.0))
        assert results == []


class TestResultContents:
    def test_mean_includes_triggering_sample(self, agg, results):
        for value, ts in [(1, 0.0), (2, 0.4), (3, 1.0)]:
            agg.add(make_data(value, ts))
        assert results[0].mean == 2.0

    def test_result_metadata(self, agg, results):
        agg.add(make_data(1, 0.0, unit="deg"))
        agg.add(make_data(3, 1.0, unit="rad"))
        result = results[0]
        assert result.sensor_name == "gyro"
        assert result.timestamp == 1.0  # timestamp of the triggering sample
        assert result.unit == "deg"  # unit of the first buffered sample

    def test_none_unit_passes_through(self, agg, results):
        agg.add(make_data(1, 0.0, unit=None))
        agg.add(make_data(3, 1.0, unit=None))
        assert results[0].unit is None


class TestWindowReset:
    def test_buffer_cleared_and_window_restarts(self, agg, results):
        agg.add(make_data(1, 0.0))
        agg.add(make_data(3, 1.0))  # emit #1, new window starts at 1.0
        agg.add(make_data(10, 1.5))  # only 500 ms into the new window
        assert len(results) == 1
        agg.add(make_data(20, 2.0))  # 1000 ms in, emit #2
        assert results[1].mean == 15.0  # (10 + 20) / 2, nothing left from window 1


class TestMultipleSensors:
    def test_sensors_have_independent_windows(self, agg, results):
        agg.add(make_data(1, 0.0, sensor="a"))
        agg.add(make_data(100, 0.9, sensor="b"))
        agg.add(make_data(3, 1.0, sensor="a"))  # a's window elapsed, b's has not
        assert [r.sensor_name for r in results] == ["a"]

    def test_sensors_do_not_mix_values(self, agg, results):
        agg.add(make_data(1, 0.0, sensor="a"))
        agg.add(make_data(1000, 0.0, sensor="b"))
        agg.add(make_data(3, 1.0, sensor="a"))
        assert results[0].mean == 2.0


class TestFlush:
    def test_flush_one_sensor_emits_partial_buffer(self, agg, results):
        agg.add(make_data(2, 0.0))
        agg.add(make_data(4, 0.3))
        agg.flush("gyro")
        assert results[0].mean == 3.0
        assert results[0].timestamp == 0.3  # last sample's timestamp

    def test_flush_all_sensors(self, agg, results):
        agg.add(make_data(1, 0.0, sensor="a"))
        agg.add(make_data(2, 0.0, sensor="b"))
        agg.flush()
        assert {r.sensor_name for r in results} == {"a", "b"}

    def test_flush_unknown_sensor_is_noop(self, agg, results):
        agg.flush("nope")
        agg.flush()
        assert results == []

    def test_double_flush_does_not_re_emit(self, agg, results):
        agg.add(make_data(1, 0.0))
        agg.flush()
        agg.flush()
        assert len(results) == 1

    def test_partial_window_only_emitted_by_flush(self, agg, results):
        """The window is only checked when a sample arrives, so flush is needed."""
        agg.add(make_data(1, 0.0))
        agg.add(make_data(3, 0.5))
        assert results == []
        agg.flush()
        assert results[0].mean == 2.0


class TestEdgeCases:
    def test_works_without_callback(self):
        agg = TimeWindowAggregator(window_duration_ms=1000)
        agg.add(make_data(1, 0.0))
        agg.add(make_data(2, 1.0))  # must not raise

    def test_zero_window_emits_on_every_sample_after_first(self):
        results = []
        agg = TimeWindowAggregator(window_duration_ms=0, emit_callback=results.append)
        agg.add(make_data(1, 0.0))  # elapsed 0 >= 0, so this emits too
        agg.add(make_data(2, 0.5))
        assert [r.mean for r in results] == [1.0, 2.0]
