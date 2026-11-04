# TelemetryProcessor tests

Unit tests for `TelemetryProcessor` (`src/telemetry_processor.py`). Everything runs without a broker, sockets or real time.

```bash
cd telemetry-processor
poetry run pytest tests/processor -v
```

## How the tests are set up

| Helper | What it does |
|---|---|
| `make_processor` | Builds a real `TelemetryProcessor` (real schemas and receiver, which do no I/O until `start()`), then swaps in a `FakePublisher`. Accepts `processing`, `mqtt` and `env` overrides. |
| `FakePublisher` | Replaces `MQTTPublisher`. Records `publish()` calls in `.published`, and records `connect`/`disconnect`. |
| `FakeClock` / `clock` | Replaces the `time` name *inside* `telemetry_processor` only. Tests set `clock.now` to control timestamps. `sleep()` never blocks, records the duration in `clock.sleeps`, and calls `on_sleep` so a test can stop a loop. |
| `receive(processor, clock, at, **fields)` | Sets the fake time, then feeds a real `ROVData` to `_on_telemetry_received`. |
| `publisher_calls` | Replaces `MQTTPublisher` with a recorder so a test can inspect the arguments the processor passed to it. |
| `clean_environ` | Gives the test a private copy of `os.environ`, so `load_dotenv` can't leak into other tests. |

Expected values are worked out by hand. For example, the `KALMAN_CONFIG` filter (`q=0, r=1`) turns inputs 10 then 12 into exactly 11.

## What each test group checks

### TestIngestMapping: `_on_telemetry_received`
Feeds a `ROVData` and checks `processor.telemetry_state`.

| Test | What and how |
|---|---|
| vector components map to schema names | For each of the five vector fields, `Vector3(1, 2, 3)` becomes `<field>_x/_y/_z`. |
| direct fields are stored with schema unit | `depth`, temperatures, pressure, actuators and `grove_water_sensor` are stored with the schema's unit. |
| vector units come from schema | `attitude_x` is `deg`, `angular_velocity_x` is `rad/s`, `velocity_x` is `m/s`. |
| every object property is stored | Every `"object"` property in the schema appears in the state, which catches new schema sensors the processor doesn't handle. |
| cardinal direction is never stored | The schema types it as a string, so the processor skips it. This pins down current behaviour. |
| state timestamp is receive time | The timestamp is the fake `now`, not a sensor time. |
| latest value overwrites previous | Two messages leave the second value and timestamp. |
| updates last received time | `last_received_time` follows the clock. |

### TestFilteringOnIngest
Passes real messages through configured Kalman filters.

| Test | What and how |
|---|---|
| configured sensor is filtered | `depth` 10 then 12 gives 11.0. |
| unconfigured sensor is not filtered | `actuator_1` 10 then 12 stays 12. |
| each sensor has its own filter state | Two filtered sensors don't affect each other. |
| unknown filter type is ignored | A `"median"` filter leaves the value raw. |

### TestHighFrequencySensors
Sets `velocity_x` as high frequency with a 1000 ms window and feeds samples at 1000.0, 1000.5 and 1001.0.

| Test | What and how |
|---|---|
| sample is buffered, not written | After one message, `velocity_x` isn't in the state. |
| other sensors are written immediately | `velocity_y` is in the state straight away. |
| window mean is written | Samples 1, 3, 5 give a mean of 3.0, with the unit and the triggering timestamp. |
| samples are filtered before aggregation | Filter then average: 10, 11 and 11.33 average to 10.78. |

### TestApplyFilters, TestAggregationCallback
Call `apply_filters` and `_on_aggregation_ready` directly.
- No filters returns the same object.
- Filters run in order, using small `PlusOne` and `Double` stub filters. (3+1)*2 is 8, and 3*2+1 is 7.
- A filter only applies to its own sensor.
- An `AggregationResult` becomes `{value, unit, timestamp}` in the state.

### TestAssemblePacket: `_assemble_packet`

| Test | What and how |
|---|---|
| empty state gives defaults | `id` is `"rov"`, the timestamp is the fake `now`, and defaults are 0 with the right unit. |
| state values flow into the packet | A state entry appears unchanged in the packet. |
| sensors without state keep defaults | Setting `depth` doesn't change `actuator_2`. |
| exactly the schema properties | The packet keys equal the schema's property names. |
| default packet is valid against schema | Validates with `jsonschema` (see Known issues). |
| invalid packet is reported but returned | A bad `depth` value is still returned, and `capsys` sees "Schema validation error". |

### TestConstruction

| Test | What and how |
|---|---|
| requires env | `None` and `{}` raise `ValueError`. |
| topic without schema / schema load failure / invalid network type | Each raises `ValueError`. The load failure is simulated by patching `load_schemas`. |
| Kalman filters built from config | Checks the instance type and its `q`/`r` values, plus the defaults (1e-5, 1e-2). |
| `high_freq_sensors` and `publish_interval` | Read from config, with defaults. A separate test documents that the aggregator window (1000) and publish interval (0.05) default differently. |

### TestPublisherSettings
Uses `publisher_calls` to read the arguments passed to `MQTTPublisher`.
- Env beats config for host and port, and the port becomes an `int`.
- Config is used when env is `None`, and the defaults are `localhost:1883`.
- `MQTT_USE_TLS`: `true/TRUE/1/yes/on` is `True`. Anything else, including `""`, is `False`. `None` falls back to config.
- The CA certs path from env beats config. `client_id`, `base_topic` and `tls_insecure` are passed through.

### TestParseConfigAndEnv
Uses `tmp_path` and `clean_environ`.
- It reads the config JSON and the `.env` next to it.
- Unset variables are `None`.
- A real environment variable beats `.env`.
- A missing config file raises `FileNotFoundError`.

### TestPublishLoop: `_publish_loop`
`clock.on_sleep` flips `running` to `False` after N iterations, so the loop ends without sleeping.
- It publishes once per iteration and sleeps `publish_interval` each time.
- Data older than 3 seconds isn't published, but the loop keeps running.
- Data exactly 3 seconds old still publishes.
- It exits at once when `running` is `False`.
- The published packet reflects the latest state.

### TestLifecycle
- `stop()` and the signal handler clear `running`.
- `start()` returns without starting the receiver if the broker isn't connected.
- `_cleanup()` flushes the aggregator (a buffered high-frequency sample reaches the state) and disconnects the publisher.

## Known issues (expected failures)

| Test | Why it fails |
|---|---|
| `test_default_packet_is_valid_against_schema` | `common`'s `load_schemas()` opens the schema files without `encoding="utf-8"`. On non-UTF-8 locales (Windows cp1252) `²` is read as `Â²`, so the schema's unit never matches `"rad/s²"`. This is marked `xfail` only on non-UTF-8 locales. With `PYTHONUTF8=1` it passes. |
| `test_cleanup_without_start_does_not_crash` | `publish_thread` is only set in `start()`, so `_cleanup()` raises `AttributeError` if `start()` never ran. This is a strict `xfail`, so it will fail loudly when someone fixes the bug, to remind them to remove the marker. |