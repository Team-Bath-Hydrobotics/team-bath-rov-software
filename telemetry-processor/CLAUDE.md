# Telemetry Processor

Sits between the ROV's Jetson and the MQTT broker. Receives raw telemetry, filters it, optionally aggregates high-frequency sensors, and republishes one JSON packet at a fixed rate.

## Commands

Run from `telemetry-processor/`:

- Install: `poetry install`
- Run: `poetry run python src/telemetry_processor.py --config src/config.json`
- Format: `poetry run black src/ tests/`
- Lint: `poetry run flake8 src/ tests/`
- Test: `poetry run pytest`

Depends on the sibling `../common` package (`common.data_interface`, `common.mqtt`, `common.network`).

## Pipeline

1. **Receive** (`src/input/telemetry_receiver.py`)
   - Connects as a *client* to the Jetson host/port over TCP or UDP (it does not listen).
   - 5 startup retries, 2s apart. After that the receive loop retries every 5s, including after socket errors or a closed TCP connection.
   - Message format: 8-byte length header (`struct "Q"`) followed by a **pickled** `ROVData` object, passed to the callback.
2. **Process** (`src/telemetry_processor.py`, class `TelemetryProcessor`)
   - Loads MQTT JSON schemas and picks the one for `base_topic`.
   - `_on_telemetry_received` walks the schema properties, pulls the matching field from `ROVData` (including `_x/_y/_z` sub-fields), and runs it through the sensor's filter chain.
   - Sensors in `high_freq_sensors` go to the aggregator. Others write straight into `telemetry_state` (latest `{value, unit, timestamp}` per sensor).
3. **Filter** (`src/filters/`)
   - `BaseFilter` is an ABC with `apply` and `reset`.
   - `KalmanFilter` is a 1D filter (`process_variance`, `measurement_variance`). The first sample only seeds state and is returned unfiltered.
   - Kalman is the only filter type. Filters are built per sensor name from `processing.filters`.
4. **Aggregate** (`src/aggregation/aggregator.py`)
   - `TimeWindowAggregator` buffers samples per sensor. The window is checked when a new sample arrives. On expiry it emits the **mean** and clears the buffer.
   - The mean is written into `telemetry_state`. `flush()` runs on shutdown.
5. **Publish**
   - A daemon thread (`_publish_loop`) calls `_assemble_packet` every `publish_interval` and publishes via `common.mqtt.publisher.MQTTPublisher`.
   - Sensors with no data default to 0 plus a hardcoded unit.
   - The packet is validated against the schema. Validation failure is only printed and the packet is still published.
   - Publishing pauses if no telemetry has arrived for 3s.

## Config and env

- `--config` JSON, plus a `.env` in the same directory. Env vars `MQTT_BROKER_HOST`, `MQTT_BROKER_PORT`, `MQTT_USE_TLS`, `MQTT_TLS_CA_CERTS` override the broker settings in the config.
- Config keys actually read: `input.{host,port,network_type}`, `output.mqtt.*`, `processing.filters`, `processing.high_freq_sensors`, `processing.window_ms`.
- `base_topic` in `src/config.json` contains a literal `<rov_id>` placeholder.

## Known issues / gotchas

- **README and config are out of sync with the code.**
  - `window_ms` is read from `processing.window_ms`, not `processing.aggregation.window_ms`.
  - `aggregation.enabled` is never read.
  - The README mentions `output/` and `data_interface/` dirs that don't exist here.
  - The README sample JSON has a trailing comma.
- **Publish rate is tied to the window.** `publish_interval = window_ms / 1000`, so 1000 ms means 1 packet/s, not the 20 Hz the README describes.
- **Sensor names may not line up.** `high_freq_sensors` lists `attitude_roll/pitch/yaw`, but `_assemble_packet` uses `attitude_x/y/z`. Filters are keyed by schema property name. Verify before relying on them.
- **`pickle.loads` on network data** can run arbitrary code. Only safe on a trusted link.
- **TCP framing.** One `recv(4096)` is assumed to hold one whole message, so large or coalesced messages can be dropped or corrupted.
- **Tests are stale.** `tests/conftest.py` imports `data_interface.telemetry_data` and uses `sensor_id`/`metadata`, but the code uses `common.data_interface` and `sensor_name`. There are no actual test files.
- **Noisy debug prints.** `Using env vars: {env}` prints on startup and the packet and state prints fire every cycle.

## Writing tests (issue #37: unit tests for aggregator and filters)

Status: `tests/` has only `conftest.py` and `__init__.py`. `pytest --collect-only` finds 0 tests. pytest 7.4.4 is in the dev deps and the poetry env imports everything fine.

### Setup facts (verified)
- `conftest.py` puts `src/` on `sys.path`, so tests import `from aggregation.aggregator import TimeWindowAggregator, AggregationResult` and `from filters.kalman_filter import KalmanFilter`.
- `TelemetryData` lives in `common/common/data_interface/telemetry_data.py`. It is a dataclass: `timestamp: float`, `sensor_name: str`, `value: float`, `unit: Optional[str] = None`, plus `to_dict()`. Import it with `from common.data_interface import TelemetryData`.
- `conftest.py`'s `sample_telemetry_data` fixture is **broken**: it imports `data_interface.telemetry_data` and passes `sensor_id` and `metadata`, neither of which exist. Fix it to the dataclass above, or replace it with a `make_data(value, ts, sensor="depth", unit="m")` helper.
- `conftest.py`'s `sample_config` still uses `aggregation.enabled`/`window_ms`, which the code doesn't read. It isn't needed for aggregator/filter tests.
- `common/data_interface/__init__.py` has `FloatData` in `__all__` without importing it. Explicit imports are fine, but `import *` would fail.
- There is no CI that runs these tests. `.github/workflows` only has `build-photogrammetry.yml` and `deploy-docs.yml`.
- In the Git Bash tool, `poetry run python -c ...` printed no output. Use the venv python directly if that happens: `C:/Users/josep/AppData/Local/pypoetry/Cache/virtualenvs/telemetry-processor-4RWt0SNA-py3.14/Scripts/python.exe`.

### Planned files
`tests/test_aggregator.py`, `tests/test_kalman_filter.py`, `tests/test_base_filter.py`. Keep tests free of sleeps, sockets and real time, and pass timestamps explicitly. Use exact-in-float timestamps such as `1000.0` and `1000.5` at window boundaries.

### Aggregator cases (`TimeWindowAggregator`)
- No emit before the window elapses. It emits when `elapsed >= window_duration_ms`.
- The mean includes the sample that triggers the emit.
- The result carries the right `sensor_name`, `timestamp` and `unit`. The unit comes from the first buffered sample.
- The buffer clears after an emit and the window restarts from the emit time.
- Sensors are independent (separate buffers and windows).
- The first sample for a sensor sets `_last_emit` and can't emit on its own.
- `flush(name)` emits a partial buffer. `flush()` flushes all sensors. Flushing an empty or unknown sensor is a no-op.
- It works with no `emit_callback`.
- Capture emissions with `results.append` as the callback.

### Kalman cases (`KalmanFilter`)
- The first sample passes through, returning the same object, and seeds state.
- **Hand-computed step, verified by running it:** `q=0, r=1`, seed 10.0, then feed 12.0. The result is 11.0 and `p` becomes 0.5 (gain 0.5).
- A constant input stays constant. A step moves toward the new value without overshooting.
- Seeded noise (`random.Random(0)`) gives lower output variance than input variance.
- A higher `measurement_variance` means a slower response. A higher `process_variance` means a faster response.
- `timestamp`, `sensor_name` and `unit` are preserved, and `value` is a `float`.
- `reset()` restores `x`, `p` and `_initialized=False`, so the next sample re-seeds.
- Separate instances share no state.

### BaseFilter cases
- Direct instantiation raises `TypeError`.
- A subclass missing `apply` or `reset` raises `TypeError`.
- A complete subclass instantiates.

### Possible real bugs to flag (don't bend tests to hide them)
- The first Kalman sample returns the input object uncopied.
- The aggregator only checks the window when a new sample arrives, so a quiet sensor never emits until `flush`.

### Out of scope
`TelemetryProcessor` and `TelemetryReceiver` need sockets and an MQTT broker.

### Deliver
Branch `feature/TBHY-37-unit-tests` (matches the `feature/TBHY-29` naming). Before opening the PR, run `poetry run pytest -v`, `poetry run black src/ tests/` and `poetry run flake8 src/ tests/`. Reference #37 in the PR. Also check the tests can fail: break the code temporarily, confirm a test fails, then revert.
