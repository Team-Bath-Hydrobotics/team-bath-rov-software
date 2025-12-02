# Telemetry Processor

Preprocesses telemetry data from the ROV's Jetson, applying filters (e.g., Kalman) and aggregations before publishing to an MQTT broker.

## Overview

This processor:
1. **Receives** telemetry data from the Jetson over UDP or TCP
2. **Filters** noisy sensor data using configurable filters (Kalman, etc.)
3. **Aggregates** data over time windows (optional) to compute statistics
4. **Publishes** processed telemetry to an MQTT broker for consumption by the UI and other systems

## Installation

Ensure you are in the telemetry-processor directory:
```bash
cd telemetry-processor
```

Install dependencies with Poetry:
```bash
poetry install
```

## Running
You'll need a .env file in the root of this project with the following variables defined
```
MQTT_URL=replaceme
MQTT_PORT=replaceme
MQTT_WEBSOCKET_PORT=replaceme
MQTT_TLS_WEBSOCKET_URL=replaceme
MQTT_USERNAME=replaceme
MQTT_PASSWORD=replaceme
```
the values for these have been shared on teams, if you can't find them contact Max.
Run the processor with a configuration file:
```bash
poetry run python src/telemetry_processor.py --config path/to/config.json
```

## Configuration

The configuration file should be JSON with the following structure:

```json
{
  "input": {
    "host": "0.0.0.0",
    "port": 5000,
    "network_type": "udp"
  },
  "output": {
    "mqtt": {
      "client_id": "telemetry-processor",
      "base_topic": "rov/telemetry",
    }
  },
  "processing": {
    "filters": {
      "depth_sensor": [
        {
          "type": "kalman",
          "process_variance": 1e-5,
          "measurement_variance": 1e-2
        }
      ],
      "imu_accel_x": [
        {
          "type": "kalman",
          "process_variance": 1e-4,
          "measurement_variance": 1e-1
        }
      ]
    },
    "aggregation": {
      "enabled": true,
      "window_ms": 1000
    }
  }
}
```

### Configuration Options

**Input:**
- `host`: IP address to bind to (use `0.0.0.0` to accept from any interface)
- `port`: Port to listen on
- `network_type`: Either `"udp"` or `"tcp"`

**Output (MQTT):**
- `broker_host`: MQTT broker hostname/IP
- `broker_port`: MQTT broker port (default: 1883)
- `client_id`: Unique client identifier
- `base_topic`: Base MQTT topic (sensor data published to `{base_topic}/{sensor_id}`)
- `username`/`password`: Optional authentication credentials

**Processing:**
- `filters`: Map of sensor_id to list of filters to apply
  - Kalman filter: Smooths noisy sensor readings
- `aggregation`: Optional time-window aggregation
  - `enabled`: Enable/disable aggregation
  - `window_ms`: Aggregation window duration in milliseconds

## Development

### Linting

Format code with Black:
```bash
poetry run black src/ tests/
```

Check code style with Flake8:
```bash
poetry run flake8 src/ tests/
```

### Testing

Run tests with pytest:
```bash
poetry run pytest
```

## Architecture

```
telemetry-processor/
├── src/
│   ├── input/              # UDP/TCP telemetry receivers
│   ├── output/             # MQTT publisher
│   ├── filters/            # Filter implementations (Kalman, etc.)
│   ├── aggregation/        # Time-window aggregation
│   ├── data_interface/     # Shared data types
│   └── telemetry_processor.py  # Main entry point
└── tests/                  # Test suite
```
