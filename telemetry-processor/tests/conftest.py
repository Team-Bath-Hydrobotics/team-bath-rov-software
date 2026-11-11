"""Pytest configuration and shared fixtures for telemetry processor tests."""

import socket
import sys
import time
from pathlib import Path

import pytest

# Add src directory to path for imports
src_path = Path(__file__).parent.parent / "src"
sys.path.insert(0, str(src_path))


@pytest.fixture
def free_port():
    """Find and return a free TCP port."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("", 0))
        s.listen(1)
        port = s.getsockname()[1]
    return port


@pytest.fixture
def sample_telemetry_data():
    """Return a sample TelemetryData point for testing."""
    from common.data_interface import TelemetryData
    #Updated since data.interface did not exist and instead lives inside common

    return TelemetryData(
        timestamp=1000.0,
        sensor_name="depth",
        value=15.5,
        unit="m",
    )
    #Updated to sensor_name from sensor_id since telemetry dataclass has field sensor_name not sensor_id


@pytest.fixture
def sample_config():
    """Return sample configuration for testing."""
    return {
        "input": {
            "host": "127.0.0.1",
            "port": 5000,
            "network_type": "udp",
        },
        "output": {
            "mqtt": {
                "broker_host": "localhost",
                "broker_port": 1883,
                "base_topic": "rov/telemetry",
            }
        },
        "processing": {
            "filters": {"depth_sensor": [{"type": "kalman", "process_variance": 1e-5}]},
            "aggregation": {
                "enabled": False,
                "window_ms": 1000,
            },
        },
    }


@pytest.fixture
def timeout():
    """Standard timeout for tests (seconds)."""
    return 5.0


@pytest.fixture(autouse=True)
def cleanup_after_test():
    """Cleanup fixture that runs after each test."""
    yield
    # Wait a bit for sockets to close
    time.sleep(0.1)