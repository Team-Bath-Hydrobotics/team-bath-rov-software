"""Main entry point for the telemetry processor."""

import argparse
import json
import signal
import threading
import time
from typing import Dict, List, Optional

import jsonschema
from aggregation.aggregator import AggregationResult, TimeWindowAggregator
from data_interface.telemetry_data import TelemetryData
from filters.base_filter import BaseFilter
from filters.kalman_filter import KalmanFilter
from input.telemetry_receiver import TelemetryReceiver

from common.mqtt.publisher import MQTTPublisher
from common.mqtt.schema_loader import get_schema_for_topic, load_schemas
from common.network.network_type import NetworkEnum


class TelemetryProcessor:
    """Telemetry Processor to coordinate receiving, filtering, and publishing."""

    def __init__(self, config: dict):
        self.config = config
        self.running = False

        # Parse configuration
        self.input_config = config.get("input", {})
        self.output_config = config.get("output", {})
        self.processing_config = config.get("processing", {})

        # Components
        self.receiver: Optional[TelemetryReceiver] = None
        self.publisher: Optional[MQTTPublisher] = None
        self.filters: Dict[str, List[BaseFilter]] = {}
        self.aggregator: Optional[TimeWindowAggregator] = None
        self.telemetry_state = {}
        self.last_received = {}
        self.schemas = load_schemas()
        self.schema = None
        if not self.schemas:
            raise ValueError(
                "Failed to start telemetry processor: Could not load schemas."
            )
        self._setup_components()

    def _setup_components(self):
        """Initialize all components based on configuration."""
        # Setup receiver
        input_host = self.input_config.get("host", "0.0.0.0")
        input_port = self.input_config.get("port", 5000)
        input_network = self.input_config.get("network_type", "udp")

        self.receiver = TelemetryReceiver(
            host=input_host,
            port=input_port,
            network_type=NetworkEnum(input_network),
            callback=self._on_telemetry_received,
        )

        # Setup MQTT publisher
        mqtt_config = self.output_config.get("mqtt", {})
        topic = mqtt_config.get("base_topic", "rov/telemetry")
        schema = get_schema_for_topic(self.schemas, topic)
        if not schema:
            raise ValueError(f"No schema defined for topic {topic}")
        self.schema = schema

        self.publisher = MQTTPublisher(
            broker_host=mqtt_config.get("broker_host", "localhost"),
            broker_port=mqtt_config.get("broker_port", 1883),
            username=mqtt_config.get("username"),
            password=mqtt_config.get("password"),
            client_id=mqtt_config.get("client_id", "telemetry-processor"),
            base_topic=topic,
        )

        # Setup filters per sensor
        filter_config = self.processing_config.get("filters", {})
        for sensor_id, sensor_filters in filter_config.items():
            self.filters[sensor_id] = []
            for f in sensor_filters:
                if f.get("type") == "kalman":
                    self.filters[sensor_id].append(
                        KalmanFilter(
                            process_variance=f.get("process_variance", 1e-5),
                            measurement_variance=f.get("measurement_variance", 1e-2),
                        )
                    )

        self.aggregator = TimeWindowAggregator(
            window_duration_ms=self.processing_config.get("window_ms", 1000),
            emit_callback=self._on_aggregation_ready,
        )
        self.high_freq_sensors = set(
            self.processing_config.get("high_freq_sensors", [])
        )
        self.publish_interval = self.processing_config.get("window_ms", 50) / 1000.0

    def _on_telemetry_received(self, data: TelemetryData):
        """Handle received telemetry data."""
        # Apply filters
        filtered_data = data
        if data.sensor_id in self.filters:
            for f in self.filters[data.sensor_id]:
                filtered_data = f.apply(filtered_data)

        if data.sensor_id in self.high_freq_sensors:
            self.aggregator.add(filtered_data)
        else:
            self.telemetry_state[data.sensor_id] = {
                "value": filtered_data.value,
                "unit": filtered_data.unit,
                "timestamp": getattr(filtered_data, "timestamp", time.time()),
            }

    def _on_aggregation_ready(self, result: AggregationResult):
        """Handle aggregated data."""
        # Convert aggregation result to telemetry for publishing
        self.telemetry_state[result.sensor_id] = {
            "value": result.mean,
            "unit": result.unit,
            "timestamp": result.timestamp
            if hasattr(result, "timestamp")
            else time.time(),
        }

    def start(self):
        """Start the telemetry processor."""
        print("Starting Telemetry Processor...")
        self.running = True

        # Connect to MQTT broker
        self.publisher.connect()
        time.sleep(1)  # Wait for connection

        # Start receiver
        self.receiver.start()

        print("Telemetry Processor started!")
        signal.signal(signal.SIGINT, self._signal_handler)

        self.publish_thread = threading.Thread(target=self._publish_loop, daemon=True)
        self.publish_thread.start()
        # Main loop
        while self.running:
            time.sleep(1)

        self._cleanup()

    def stop(self):
        """Stop the telemetry processor."""
        self.running = False

    def _signal_handler(self, sig, frame):
        """Handle interrupt signal."""
        print("\nReceived interrupt signal...")
        self.stop()

    def _cleanup(self):
        """Cleanup resources."""
        if self.aggregator:
            self.aggregator.flush()
        if self.receiver:
            self.receiver.stop()
        if self.publisher:
            self.publisher.disconnect()
        print("Telemetry Processor stopped.")
        if self.publish_thread:
            self.running = False
            self.publish_thread.join()
            self.publish_thread = None

    def _publish_loop(self):
        while self.running:
            packet = self._assemble_packet()
            self.publisher.publish(packet)
            print(f"Published packet: {packet}")
            time.sleep(self.publish_interval)

    def get_field(
        self, sensor, subfield=None, default_value=0, default_unit="", default_ts=0
    ):
        entry = self.telemetry_state.get(sensor, {})
        if subfield:
            entry = entry.get(subfield, {})
        return {
            "value": entry.get("value", default_value),
            "unit": entry.get("unit", default_unit),
            "timestamp": entry.get("timestamp", default_ts),
        }

    def _assemble_packet(self) -> dict:
        """
        Assemble the telemetry state into a JSON-compliant packet for publishing.
        For high-frequency sensors, use the aggregated value if available.
        For low-frequency sensors, keep the last received value with original timestamp.
        """

        now = time.time()
        packet = {
            "timestamp": now,
            "id": "rov",
            "attitude": {
                "roll": self.get_field("attitude", "roll", 0, "deg", 0),
                "pitch": self.get_field("attitude", "pitch", 0, "deg", 0),
                "yaw": self.get_field("attitude", "yaw", 0, "deg", 0),
            },
            "angular_velocity": {
                "x": self.get_field("angular_velocity", "x", 0, "rad/s", 0),
                "y": self.get_field("angular_velocity", "y", 0, "rad/s", 0),
                "z": self.get_field("angular_velocity", "z", 0, "rad/s", 0),
            },
            "linear_acceleration": {
                "x": self.get_field("linear_acceleration", "x", 0, "m/s²", 0),
                "y": self.get_field("linear_acceleration", "y", 0, "m/s²", 0),
                "z": self.get_field("linear_acceleration", "z", 0, "m/s²", 0),
            },
            "linear_velocity": {
                "x": self.get_field("linear_velocity", "x", 0, "m/s", 0),
                "y": self.get_field("linear_velocity", "y", 0, "m/s", 0),
                "z": self.get_field("linear_velocity", "z", 0, "m/s", 0),
            },
            "depth": self.get_field("depth", None, 0, "m", 0),
            "ambient_temperature": self.get_field(
                "ambient_temperature", None, 0, "C", 0
            ),
            "internal_temperature": self.get_field(
                "internal_temperature", None, 0, "C", 0
            ),
            "ambient_pressure": self.get_field("ambient_pressure", None, 0, "Pa", 0),
            "cardinal_direction": self.telemetry_state.get("cardinal_direction", ""),
            "grove_water_sensor": self.get_field("grove_water_sensor", None, 0, "?", 0),
            "actuators": {
                "a1": self.get_field("actuators", "a1", 0, "%", 0),
                "a2": self.get_field("actuators", "a2", 0, "%", 0),
                "a3": self.get_field("actuators", "a3", 0, "%", 0),
                "a4": self.get_field("actuators", "a4", 0, "%", 0),
                "a5": self.get_field("actuators", "a5", 0, "%", 0),
                "a6": self.get_field("actuators", "a6", 0, "%", 0),
            },
        }

        try:
            jsonschema.validate(instance=packet, schema=self.schema)
        except jsonschema.ValidationError as e:
            print(f"Schema validation error: {e.message}")

        return packet


def parse_config(config_path: str) -> dict:
    """Parse configuration from JSON file."""
    with open(config_path, "r") as f:
        return json.load(f)


def main():
    parser = argparse.ArgumentParser(description="ROV Telemetry Processor")
    parser.add_argument(
        "--config",
        type=str,
        required=True,
        help="Path to JSON configuration file",
    )
    args = parser.parse_args()

    config = parse_config(args.config)
    processor = TelemetryProcessor(config)
    processor.start()


if __name__ == "__main__":
    main()
