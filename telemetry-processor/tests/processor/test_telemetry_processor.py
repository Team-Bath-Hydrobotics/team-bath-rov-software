"""Unit tests for TelemetryProcessor."""

import json
import locale
import os

import jsonschema
import pytest
import telemetry_processor as tp_module
from aggregation.aggregator import AggregationResult
from filters.base_filter import BaseFilter
from filters.kalman_filter import KalmanFilter
from telemetry_processor import TelemetryProcessor, parse_config_and_env

from common.data_interface import ROVData, TelemetryData, Vector3

TOPIC = "hydrobotics/rov/x/telemetry"

VECTOR_FIELDS = [
    "attitude",
    "angular_velocity",
    "angular_acceleration",
    "acceleration",
    "velocity",
]

# Kalman with no process noise and unit measurement noise: after a first sample of
# 10 and a second of 12, the gain is 0.5 and the estimate is exactly 11.
KALMAN_CONFIG = {"type": "kalman", "process_variance": 0, "measurement_variance": 1}

ENV_VARS = [
    "MQTT_BROKER_HOST",
    "MQTT_BROKER_PORT",
    "MQTT_USE_TLS",
    "MQTT_TLS_CA_CERTS",
]


class FakePublisher:
    """Stands in for MQTTPublisher and records what would have been published."""

    def __init__(self, **kwargs):
        self.kwargs = kwargs
        self.published = []
        self.connected = True
        self.disconnected = False

    def connect(self):
        pass

    def disconnect(self):
        self.disconnected = True

    def publish(self, message):
        self.published.append(message)


class FakeClock:
    """Replaces the `time` module inside telemetry_processor.

    sleep() never blocks. It records the requested duration and then calls
    `on_sleep` (if set), which lets a test stop a loop after a few iterations.
    """

    def __init__(self):
        self.now = 1000.0
        self.sleeps = []
        self.on_sleep = None

    def time(self):
        return self.now

    def sleep(self, seconds):
        self.sleeps.append(seconds)
        if self.on_sleep:
            self.on_sleep()


class PlusOne(BaseFilter):
    def apply(self, data):
        data.value += 1
        return data

    def reset(self):
        pass


class Double(BaseFilter):
    def apply(self, data):
        data.value *= 2
        return data

    def reset(self):
        pass


def build_config(processing=None, mqtt=None):
    return {
        "input": {"host": "127.0.0.1", "port": 1, "network_type": "tcp"},
        "output": {"mqtt": {"base_topic": TOPIC, **(mqtt or {})}},
        "processing": processing or {},
    }


def make_data(value=3.0, sensor="depth"):
    return TelemetryData(timestamp=1000.0, sensor_name=sensor, value=value, unit="m")


@pytest.fixture
def clock(monkeypatch):
    fake = FakeClock()
    monkeypatch.setattr(tp_module, "time", fake)
    return fake


@pytest.fixture
def make_processor(clock):
    """Build a TelemetryProcessor with a fake publisher.

    Construction does no network I/O; only start() connects, so the real receiver
    and schemas are used.
    """

    def _make(processing=None, mqtt=None, env=None):
        env = {"mqtt_broker_host": "localhost"} if env is None else env
        processor = TelemetryProcessor(build_config(processing, mqtt), env)
        processor.publisher = FakePublisher()
        return processor

    return _make


@pytest.fixture
def publisher_calls(monkeypatch):
    """Replace MQTTPublisher with a recorder and return its constructor kwargs."""
    calls = []

    class RecordingPublisher(FakePublisher):
        def __init__(self, **kwargs):
            super().__init__(**kwargs)
            calls.append(kwargs)

    monkeypatch.setattr(tp_module, "MQTTPublisher", RecordingPublisher)
    return calls


@pytest.fixture
def clean_environ(monkeypatch):
    """Isolate os.environ so load_dotenv can't leak into other tests."""
    environ = {k: v for k, v in os.environ.items() if k not in ENV_VARS}
    monkeypatch.setattr(os, "environ", environ)
    return environ


def receive(processor, clock, at, **fields):
    """Feed one ROVData to the processor at a given (fake) time."""
    clock.now = at
    processor._on_telemetry_received(ROVData(**fields))


class TestIngestMapping:
    @pytest.mark.parametrize("field", VECTOR_FIELDS)
    def test_vector_components_map_to_schema_names(self, make_processor, clock, field):
        processor = make_processor()
        receive(processor, clock, 1000.0, **{field: Vector3(1.0, 2.0, 3.0)})
        state = processor.telemetry_state
        assert state[f"{field}_x"]["value"] == 1.0
        assert state[f"{field}_y"]["value"] == 2.0
        assert state[f"{field}_z"]["value"] == 3.0

    @pytest.mark.parametrize(
        "name, value, unit",
        [
            ("depth", 5.5, "m"),
            ("ambient_temperature", 12.5, "C"),
            ("internal_temperature", 33.0, "C"),
            ("ambient_pressure", 200.0, "Pa"),
            ("actuator_1", 40.0, "%"),
            ("actuator_6", 60.0, "%"),
            ("grove_water_sensor", 1, "?"),
        ],
    )
    def test_direct_fields_are_stored_with_schema_unit(
        self, make_processor, clock, name, value, unit
    ):
        processor = make_processor()
        receive(processor, clock, 1000.0, **{name: value})
        assert processor.telemetry_state[name]["value"] == value
        assert processor.telemetry_state[name]["unit"] == unit

    @pytest.mark.parametrize(
        "field, unit",
        [("attitude", "deg"), ("angular_velocity", "rad/s"), ("velocity", "m/s")],
    )
    def test_vector_units_come_from_schema(self, make_processor, clock, field, unit):
        processor = make_processor()
        receive(processor, clock, 1000.0, **{field: Vector3(1.0, 2.0, 3.0)})
        assert processor.telemetry_state[f"{field}_x"]["unit"] == unit

    def test_every_object_property_in_the_schema_is_stored(self, make_processor, clock):
        processor = make_processor()
        receive(processor, clock, 1000.0)
        object_props = {
            name
            for name, schema in processor.schema["properties"].items()
            if schema.get("type") == "object"
        }
        assert object_props <= set(processor.telemetry_state)

    def test_cardinal_direction_is_never_stored(self, make_processor, clock):
        """The schema types it as a string, so the processor skips it."""
        processor = make_processor()
        receive(processor, clock, 1000.0, cardinal_direction=90.0)
        assert "cardinal_direction" not in processor.telemetry_state

    def test_state_timestamp_is_receive_time(self, make_processor, clock):
        processor = make_processor()
        receive(processor, clock, 1234.5, depth=1.0)
        assert processor.telemetry_state["depth"]["timestamp"] == 1234.5

    def test_latest_value_overwrites_previous(self, make_processor, clock):
        processor = make_processor()
        receive(processor, clock, 1000.0, depth=1.0)
        receive(processor, clock, 1001.0, depth=2.0)
        assert processor.telemetry_state["depth"]["value"] == 2.0
        assert processor.telemetry_state["depth"]["timestamp"] == 1001.0

    def test_updates_last_received_time(self, make_processor, clock):
        processor = make_processor()
        receive(processor, clock, 5000.0, depth=1.0)
        assert processor.last_received_time == 5000.0


class TestFilteringOnIngest:
    def test_configured_sensor_is_filtered(self, make_processor, clock):
        processor = make_processor(processing={"filters": {"depth": [KALMAN_CONFIG]}})
        receive(processor, clock, 1000.0, depth=10.0)
        receive(processor, clock, 1001.0, depth=12.0)
        assert processor.telemetry_state["depth"]["value"] == pytest.approx(11.0)

    def test_unconfigured_sensor_is_not_filtered(self, make_processor, clock):
        processor = make_processor(processing={"filters": {"depth": [KALMAN_CONFIG]}})
        receive(processor, clock, 1000.0, actuator_1=10.0)
        receive(processor, clock, 1001.0, actuator_1=12.0)
        assert processor.telemetry_state["actuator_1"]["value"] == 12.0

    def test_each_sensor_has_its_own_filter_state(self, make_processor, clock):
        processor = make_processor(
            processing={
                "filters": {
                    "depth": [KALMAN_CONFIG],
                    "ambient_temperature": [KALMAN_CONFIG],
                }
            }
        )
        receive(processor, clock, 1000.0, depth=10.0, ambient_temperature=100.0)
        receive(processor, clock, 1001.0, depth=12.0, ambient_temperature=100.0)
        assert processor.telemetry_state["depth"]["value"] == pytest.approx(11.0)
        assert processor.telemetry_state["ambient_temperature"]["value"] == 100.0

    def test_unknown_filter_type_is_ignored(self, make_processor, clock):
        processor = make_processor(
            processing={"filters": {"depth": [{"type": "median"}]}}
        )
        receive(processor, clock, 1000.0, depth=10.0)
        receive(processor, clock, 1001.0, depth=12.0)
        assert processor.telemetry_state["depth"]["value"] == 12.0


class TestHighFrequencySensors:
    PROCESSING = {"high_freq_sensors": ["velocity_x"], "window_ms": 1000}

    def test_sample_is_buffered_and_not_written_to_state(self, make_processor, clock):
        processor = make_processor(processing=self.PROCESSING)
        receive(processor, clock, 1000.0, velocity=Vector3(1.0, 2.0, 3.0))
        assert "velocity_x" not in processor.telemetry_state

    def test_other_sensors_are_written_immediately(self, make_processor, clock):
        processor = make_processor(processing=self.PROCESSING)
        receive(processor, clock, 1000.0, velocity=Vector3(1.0, 2.0, 3.0))
        assert processor.telemetry_state["velocity_y"]["value"] == 2.0

    def test_window_mean_is_written_when_window_elapses(self, make_processor, clock):
        processor = make_processor(processing=self.PROCESSING)
        for at, x in [(1000.0, 1.0), (1000.5, 3.0), (1001.0, 5.0)]:
            receive(processor, clock, at, velocity=Vector3(x, 0.0, 0.0))
        entry = processor.telemetry_state["velocity_x"]
        assert entry["value"] == pytest.approx(3.0)  # (1 + 3 + 5) / 3
        assert entry["unit"] == "m/s"
        assert entry["timestamp"] == 1001.0

    def test_samples_are_filtered_before_aggregation(self, make_processor, clock):
        processor = make_processor(
            processing={
                **self.PROCESSING,
                "filters": {"velocity_x": [KALMAN_CONFIG]},
            }
        )
        for at, x in [(1000.0, 10.0), (1000.5, 12.0), (1001.0, 12.0)]:
            receive(processor, clock, at, velocity=Vector3(x, 0.0, 0.0))
        # Filtered values are 10, 11 and 11.333..., so their mean is 10.777...
        expected = (10.0 + 11.0 + (11.0 + 1.0 / 3.0)) / 3
        assert processor.telemetry_state["velocity_x"]["value"] == pytest.approx(
            expected
        )


class TestApplyFilters:
    def test_sensor_without_filters_is_returned_unchanged(self, make_processor):
        processor = make_processor()
        data = make_data()
        assert processor.apply_filters("depth", data) is data

    def test_filters_are_applied_in_order(self, make_processor):
        processor = make_processor()
        processor.filters["depth"] = [PlusOne(), Double()]
        assert processor.apply_filters("depth", make_data(3.0)).value == 8.0  # (3+1)*2

    def test_order_matters(self, make_processor):
        processor = make_processor()
        processor.filters["depth"] = [Double(), PlusOne()]
        assert processor.apply_filters("depth", make_data(3.0)).value == 7.0  # 3*2+1

    def test_filters_only_apply_to_their_own_sensor(self, make_processor):
        processor = make_processor()
        processor.filters["depth"] = [Double()]
        assert processor.apply_filters("other", make_data(3.0, "other")).value == 3.0


class TestAggregationCallback:
    def test_result_is_written_to_state(self, make_processor):
        processor = make_processor()
        processor._on_aggregation_ready(
            AggregationResult(
                sensor_name="velocity_x", timestamp=42.0, mean=2.5, unit="m/s"
            )
        )
        assert processor.telemetry_state["velocity_x"] == {
            "value": 2.5,
            "unit": "m/s",
            "timestamp": 42.0,
        }


class TestAssemblePacket:
    def test_empty_state_gives_defaults(self, make_processor, clock):
        processor = make_processor()
        clock.now = 2000.0
        packet = processor._assemble_packet()
        assert packet["id"] == "rov"
        assert packet["timestamp"] == 2000.0
        assert packet["depth"] == {"value": 0, "unit": "m", "timestamp": 0}
        assert packet["actuator_1"] == {"value": 0, "unit": "%", "timestamp": 0}
        assert packet["cardinal_direction"] == ""

    def test_state_values_flow_into_packet(self, make_processor):
        processor = make_processor()
        entry = {"value": 7.5, "unit": "m", "timestamp": 999.0}
        processor.telemetry_state["depth"] = entry
        assert processor._assemble_packet()["depth"] == entry

    def test_sensors_without_state_keep_defaults(self, make_processor):
        processor = make_processor()
        processor.telemetry_state["depth"] = {"value": 7.5, "unit": "m", "timestamp": 1}
        assert processor._assemble_packet()["actuator_2"]["value"] == 0

    def test_packet_has_exactly_the_schema_properties(self, make_processor):
        processor = make_processor()
        packet = processor._assemble_packet()
        assert set(packet) == set(processor.schema["properties"])

    @pytest.mark.xfail(
        locale.getpreferredencoding(False).lower().replace("-", "") != "utf8",
        reason="load_schemas() opens schema files without encoding='utf-8', so on "
        "non-UTF-8 locales (e.g. Windows cp1252) the '²' units are mis-decoded",
    )
    def test_default_packet_is_valid_against_schema(self, make_processor):
        processor = make_processor()
        packet = processor._assemble_packet()
        jsonschema.validate(instance=packet, schema=processor.schema)

    def test_invalid_packet_is_reported_but_still_returned(
        self, make_processor, capsys
    ):
        processor = make_processor()
        processor.telemetry_state["depth"] = {
            "value": "not a number",
            "unit": "m",
            "timestamp": 1,
        }
        packet = processor._assemble_packet()
        assert packet["depth"]["value"] == "not a number"
        assert "Schema validation error" in capsys.readouterr().out


class TestConstruction:
    def test_requires_env(self):
        with pytest.raises(ValueError, match="Environment variables"):
            TelemetryProcessor(build_config(), None)
        with pytest.raises(ValueError, match="Environment variables"):
            TelemetryProcessor(build_config(), {})

    def test_topic_without_schema_is_rejected(self, make_processor):
        with pytest.raises(ValueError, match="No schema defined"):
            make_processor(mqtt={"base_topic": "foo/bar"})

    def test_schema_load_failure_is_rejected(self, make_processor, monkeypatch):
        monkeypatch.setattr(tp_module, "load_schemas", lambda: None)
        with pytest.raises(ValueError, match="Could not load schemas"):
            make_processor()

    def test_invalid_network_type_is_rejected(self):
        config = build_config()
        config["input"]["network_type"] = "carrier-pigeon"
        with pytest.raises(ValueError):
            TelemetryProcessor(config, {"mqtt_broker_host": "localhost"})

    def test_telemetry_schema_is_selected_for_topic(self, make_processor):
        assert "depth" in make_processor().schema["properties"]

    def test_kalman_filters_are_built_from_config(self, make_processor):
        processor = make_processor(
            processing={
                "filters": {
                    "depth": [
                        {
                            "type": "kalman",
                            "process_variance": 0.5,
                            "measurement_variance": 0.25,
                        }
                    ]
                }
            }
        )
        built = processor.filters["depth"][0]
        assert isinstance(built, KalmanFilter)
        assert (built.q, built.r) == (0.5, 0.25)

    def test_kalman_variances_have_defaults(self, make_processor):
        processor = make_processor(
            processing={"filters": {"depth": [{"type": "kalman"}]}}
        )
        built = processor.filters["depth"][0]
        assert (built.q, built.r) == (1e-5, 1e-2)

    def test_high_freq_sensors_from_config(self, make_processor):
        processor = make_processor(processing={"high_freq_sensors": ["velocity_x"]})
        assert processor.high_freq_sensors == {"velocity_x"}

    def test_high_freq_sensors_default_to_empty(self, make_processor):
        assert make_processor().high_freq_sensors == set()

    def test_publish_interval_comes_from_window_ms(self, make_processor):
        assert make_processor(processing={"window_ms": 200}).publish_interval == 0.2

    def test_window_defaults_disagree(self, make_processor):
        """Documents a quirk: both read window_ms but default to different values."""
        processor = make_processor()
        assert processor.aggregator.window_duration_ms == 1000
        assert processor.publish_interval == 0.05


class TestPublisherSettings:
    def test_env_overrides_config_for_host_and_port(
        self, make_processor, publisher_calls
    ):
        make_processor(
            mqtt={"broker_host": "cfg-host", "broker_port": 1111},
            env={"mqtt_broker_host": "env-host", "mqtt_broker_port": "9999"},
        )
        assert publisher_calls[0]["broker_host"] == "env-host"
        assert publisher_calls[0]["broker_port"] == 9999

    def test_config_is_used_when_env_is_unset(self, make_processor, publisher_calls):
        make_processor(
            mqtt={"broker_host": "cfg-host", "broker_port": 1111},
            env={"mqtt_broker_host": None, "mqtt_broker_port": None},
        )
        assert publisher_calls[0]["broker_host"] == "cfg-host"
        assert publisher_calls[0]["broker_port"] == 1111

    def test_host_and_port_defaults(self, make_processor, publisher_calls):
        make_processor(env={"mqtt_broker_host": None})
        assert publisher_calls[0]["broker_host"] == "localhost"
        assert publisher_calls[0]["broker_port"] == 1883

    @pytest.mark.parametrize("value", ["true", "TRUE", "1", "yes", "on"])
    def test_env_tls_truthy_values(self, make_processor, publisher_calls, value):
        make_processor(env={"mqtt_use_tls": value})
        assert publisher_calls[0]["use_tls"] is True

    @pytest.mark.parametrize("value", ["false", "0", "no", "off", "", "maybe"])
    def test_env_tls_other_values_are_false(
        self, make_processor, publisher_calls, value
    ):
        make_processor(mqtt={"use_tls": True}, env={"mqtt_use_tls": value})
        assert publisher_calls[0]["use_tls"] is False

    def test_tls_falls_back_to_config(self, make_processor, publisher_calls):
        make_processor(mqtt={"use_tls": True}, env={"mqtt_use_tls": None})
        assert publisher_calls[0]["use_tls"] is True

    def test_ca_certs_env_overrides_config(self, make_processor, publisher_calls):
        make_processor(
            mqtt={"tls_ca_certs": "cfg.pem"}, env={"mqtt_tls_ca_certs": "env.pem"}
        )
        assert publisher_calls[0]["tls_ca_certs"] == "env.pem"

    def test_client_id_topic_and_insecure_flag(self, make_processor, publisher_calls):
        make_processor(mqtt={"client_id": "abc", "tls_insecure": True})
        assert publisher_calls[0]["client_id"] == "abc"
        assert publisher_calls[0]["base_topic"] == TOPIC
        assert publisher_calls[0]["tls_insecure"] is True

    def test_client_id_default(self, make_processor, publisher_calls):
        make_processor()
        assert publisher_calls[0]["client_id"] == "telemetry-processor"


class TestParseConfigAndEnv:
    def test_loads_config_and_dotenv_next_to_it(self, tmp_path, clean_environ):
        config = {"input": {"port": 1}}
        (tmp_path / "config.json").write_text(json.dumps(config))
        (tmp_path / ".env").write_text(
            "MQTT_BROKER_HOST=dotenv-host\nMQTT_BROKER_PORT=1884\nMQTT_USE_TLS=true\n"
        )
        loaded, env = parse_config_and_env(str(tmp_path / "config.json"))
        assert loaded == config
        assert env == {
            "mqtt_broker_host": "dotenv-host",
            "mqtt_broker_port": "1884",
            "mqtt_use_tls": "true",
            "mqtt_tls_ca_certs": None,
        }

    def test_missing_variables_are_none(self, tmp_path, clean_environ):
        (tmp_path / "config.json").write_text("{}")
        _, env = parse_config_and_env(str(tmp_path / "config.json"))
        assert set(env.values()) == {None}

    def test_real_environment_beats_dotenv(self, tmp_path, clean_environ):
        clean_environ["MQTT_BROKER_HOST"] = "real-host"
        (tmp_path / "config.json").write_text("{}")
        (tmp_path / ".env").write_text("MQTT_BROKER_HOST=dotenv-host\n")
        _, env = parse_config_and_env(str(tmp_path / "config.json"))
        assert env["mqtt_broker_host"] == "real-host"

    def test_missing_config_file_raises(self, tmp_path, clean_environ):
        with pytest.raises(FileNotFoundError):
            parse_config_and_env(str(tmp_path / "nope.json"))


class TestPublishLoop:
    @staticmethod
    def stop_after(processor, clock, iterations):
        def on_sleep():
            if len(clock.sleeps) >= iterations:
                processor.running = False

        clock.on_sleep = on_sleep

    def test_publishes_every_interval_while_data_is_fresh(self, make_processor, clock):
        processor = make_processor()
        processor.running = True
        processor.last_received_time = clock.now
        self.stop_after(processor, clock, 3)
        processor._publish_loop()
        assert len(processor.publisher.published) == 3
        assert all(p["id"] == "rov" for p in processor.publisher.published)
        assert clock.sleeps == [processor.publish_interval] * 3

    def test_stale_data_is_not_published(self, make_processor, clock):
        processor = make_processor()
        processor.running = True
        processor.last_received_time = clock.now - 3.5
        self.stop_after(processor, clock, 2)
        processor._publish_loop()
        assert processor.publisher.published == []
        assert len(clock.sleeps) == 2  # still sleeps and keeps checking

    def test_data_exactly_three_seconds_old_is_still_published(
        self, make_processor, clock
    ):
        processor = make_processor()
        processor.running = True
        processor.last_received_time = clock.now - 3.0
        self.stop_after(processor, clock, 1)
        processor._publish_loop()
        assert len(processor.publisher.published) == 1

    def test_loop_exits_immediately_when_not_running(self, make_processor, clock):
        processor = make_processor()
        processor.running = False
        processor._publish_loop()
        assert processor.publisher.published == []
        assert clock.sleeps == []

    def test_published_packet_reflects_latest_state(self, make_processor, clock):
        processor = make_processor()
        receive(processor, clock, clock.now, depth=4.5)
        processor.running = True
        self.stop_after(processor, clock, 1)
        processor._publish_loop()
        assert processor.publisher.published[0]["depth"]["value"] == 4.5


class TestLifecycle:
    def test_stop_clears_running_flag(self, make_processor):
        processor = make_processor()
        processor.running = True
        processor.stop()
        assert processor.running is False

    def test_signal_handler_stops_processor(self, make_processor):
        processor = make_processor()
        processor.running = True
        processor._signal_handler(2, None)
        assert processor.running is False

    def test_start_exits_if_broker_is_not_connected(self, make_processor):
        processor = make_processor()
        processor.publisher.connected = False
        processor.start()
        assert processor.running is False
        assert processor.receiver.running is False  # receiver never started

    def test_cleanup_flushes_aggregator_and_disconnects(self, make_processor, clock):
        processor = make_processor(processing={"high_freq_sensors": ["velocity_x"]})
        processor.publish_thread = None  # normally set by start()
        receive(processor, clock, 1000.0, velocity=Vector3(4.0, 0.0, 0.0))
        assert "velocity_x" not in processor.telemetry_state
        processor._cleanup()
        assert processor.telemetry_state["velocity_x"]["value"] == 4.0
        assert processor.publisher.disconnected is True

    @pytest.mark.xfail(
        raises=AttributeError,
        strict=True,
        reason="publish_thread is only set in start(), not __init__",
    )
    def test_cleanup_without_start_does_not_crash(self, make_processor):
        make_processor()._cleanup()
