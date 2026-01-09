"""Main entry point for the telemetry processor."""

import argparse
import json
import os
import signal
import threading
import time
from typing import Dict, List, Optional

import jsonschema
from aggregation.aggregator import AggregationResult, TimeWindowAggregator
from dotenv import load_dotenv
from filters.base_filter import BaseFilter
from filters.kalman_filter import KalmanFilter
from input.telemetry_receiver import TelemetryReceiver

from common.data_interface.telemetry_data import TelemetryData
from common.mqtt.publisher import MQTTPublisher
from common.mqtt.schema_loader import get_schema_for_topic, load_schemas
from common.network.network_type import NetworkEnum


class TelemetryProcessor:
    """Telemetry Processor to coordinate receiving, filtering, and publishing."""

    def __init__(self, config: dict, env: dict = None):
        if env is None or env == {}:
            raise ValueError("Environment variables must be provided.")

        self.config = config
        self.env = env
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
        self.last_received_time = time.time()
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
        print(f"Using env vars: {self.env}")  # Debug print to verify env vars
        broker_host = self.env.get("mqtt_broker_host") or mqtt_config.get("broker_host", "localhost")
        broker_port = self.env.get("mqtt_broker_port") or mqtt_config.get("broker_port", 1883)
        self.publisher = MQTTPublisher(
            broker_host=broker_host,
            broker_port=int(broker_port),
            username=self.env.get("mqtt_username"),
            password=self.env.get("mqtt_password"),
            client_id=mqtt_config.get("client_id", "telemetry-processor"),
            base_topic=topic,
        )

        # Setup filters per sensor
        filter_config = self.processing_config.get("filters", {})
        for sensor_name, sensor_filters in filter_config.items():
            self.filters[sensor_name] = []
            for f in sensor_filters:
                if f.get("type") == "kalman":
                    self.filters[sensor_name].append(
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
        print(f"Publish interval set to {self.publish_interval} seconds.")

    def _on_telemetry_received(self, rov_data):
        """Handle received telemetry data."""
        self.last_received_time = time.time()
        now = time.time()
        properties = self.schema.get("properties", {})

        for prop_name, prop_schema in properties.items():
            if prop_name in ["timestamp", "id"]:
                continue

            prop_type = prop_schema.get("type")

            if "_" in prop_name:
                parts = prop_name.rsplit("_", 1)
                base_name = parts[0]
                component_name = parts[1]  # x, y, z

                if hasattr(rov_data, base_name):
                    base_value = getattr(rov_data, base_name)

                    if hasattr(base_value, component_name):
                        value = getattr(base_value, component_name)

                        if prop_type == "object":
                            nested_props = prop_schema.get("properties", {})
                            self.handle_low_high_frequency(
                                nested_props, prop_name, value, now
                            )
                        continue

            self.handle_object(prop_name, prop_schema, prop_type, rov_data, now)

    def handle_object(self, prop_name, prop_schema, prop_type, data, now):
        if not hasattr(data, prop_name):
            return
        value = getattr(data, prop_name)
        if prop_type == "object":
            nested_props = prop_schema.get("properties", {})
            self.handle_low_high_frequency(nested_props, prop_name, value, now)

    def handle_low_high_frequency(self, nested_props, prop_name, value, now):
        if "value" in nested_props:
            unit_schema = nested_props.get("unit", {})
            unit = unit_schema.get("const") or unit_schema.get("enum", [""])[0]
            value = self.apply_filters(
                prop_name,
                TelemetryData(
                    timestamp=now,
                    sensor_name=prop_name,
                    value=value,
                    unit=unit,
                ),
            ).value
            if prop_name in self.high_freq_sensors:
                telemetry_data = TelemetryData(
                    timestamp=now, sensor_name=prop_name, value=value, unit=unit
                )

                self.aggregator.add(telemetry_data)
            else:
                self.telemetry_state[prop_name] = {
                    "value": value,
                    "unit": unit,
                    "timestamp": now,
                }

    def apply_filters(self, sensor_name: str, data: TelemetryData) -> TelemetryData:
        """Apply configured filters to telemetry data for a sensor."""
        if sensor_name in self.filters:
            for f in self.filters[sensor_name]:
                data = f.apply(data)
        return data

    def _on_aggregation_ready(self, result: AggregationResult):
        """Handle aggregated data."""
        # Convert aggregation result to telemetry for publishing
        self.telemetry_state[result.sensor_name] = {
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
        if not self.publisher.connected:
            print("Failed to connect to MQTT broker. Exiting.")
            self.running = False
            return
        # Start receiver
        self.receiver.start()
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
            if self.last_received_time + 3 < time.time():
                time.sleep(self.publish_interval)
                continue
            packet = self._assemble_packet()
            # ("Publishing packet:", packet)
            self.publisher.publish(packet)
            print(f"Published telemetry packet at {time.time()}")
            time.sleep(self.publish_interval)

    def _assemble_packet(self) -> dict:
        """
        Assemble the telemetry state into a JSON-compliant packet for publishing.
        For high-frequency sensors, use the aggregated value if available.
        For low-frequency sensors, keep the last received value with original timestamp.
        """
        print(f"Current telemetry state: {self.telemetry_state}")
        now = time.time()
        
        # Default structure for missing fields
        default_field = {"value": 0, "unit": "", "timestamp": 0}
        
        packet = {
            "timestamp": now,
            "id": "rov",
            "attitude_x": self.telemetry_state.get("attitude_x", {"value": 0, "unit": "deg", "timestamp": 0}),
            "attitude_y": self.telemetry_state.get("attitude_y", {"value": 0, "unit": "deg", "timestamp": 0}),
            "attitude_z": self.telemetry_state.get("attitude_z", {"value": 0, "unit": "deg", "timestamp": 0}),
            "angular_velocity_x": self.telemetry_state.get("angular_velocity_x", {"value": 0, "unit": "rad/s", "timestamp": 0}),
            "angular_velocity_y": self.telemetry_state.get("angular_velocity_y", {"value": 0, "unit": "rad/s", "timestamp": 0}),
            "angular_velocity_z": self.telemetry_state.get("angular_velocity_z", {"value": 0, "unit": "rad/s", "timestamp": 0}),
            "angular_acceleration_x": self.telemetry_state.get("angular_acceleration_x", {"value": 0, "unit": "rad/s²", "timestamp": 0}),
            "angular_acceleration_y": self.telemetry_state.get("angular_acceleration_y", {"value": 0, "unit": "rad/s²", "timestamp": 0}),
            "angular_acceleration_z": self.telemetry_state.get("angular_acceleration_z", {"value": 0, "unit": "rad/s²", "timestamp": 0}),
            "acceleration_x": self.telemetry_state.get("acceleration_x", {"value": 0, "unit": "m/s²", "timestamp": 0}),
            "acceleration_y": self.telemetry_state.get("acceleration_y", {"value": 0, "unit": "m/s²", "timestamp": 0}),
            "acceleration_z": self.telemetry_state.get("acceleration_z", {"value": 0, "unit": "m/s²", "timestamp": 0}),
            "velocity_x": self.telemetry_state.get("velocity_x", {"value": 0, "unit": "m/s", "timestamp": 0}),
            "velocity_y": self.telemetry_state.get("velocity_y", {"value": 0, "unit": "m/s", "timestamp": 0}),
            "velocity_z": self.telemetry_state.get("velocity_z", {"value": 0, "unit": "m/s", "timestamp": 0}),
            "depth": self.telemetry_state.get("depth", {"value": 0, "unit": "m", "timestamp": 0}),
            "ambient_temperature": self.telemetry_state.get("ambient_temperature", {"value": 0, "unit": "C", "timestamp": 0}),
            "internal_temperature": self.telemetry_state.get("internal_temperature", {"value": 0, "unit": "C", "timestamp": 0}),
            "ambient_pressure": self.telemetry_state.get("ambient_pressure", {"value": 0, "unit": "Pa", "timestamp": 0}),
            "cardinal_direction": self.telemetry_state.get("cardinal_direction", ""),
            "grove_water_sensor": self.telemetry_state.get("grove_water_sensor", {"value": 0, "unit": "?", "timestamp": 0}),
            "actuator_1": self.telemetry_state.get("actuator_1", {"value": 0, "unit": "%", "timestamp": 0}),
            "actuator_2": self.telemetry_state.get("actuator_2", {"value": 0, "unit": "%", "timestamp": 0}),
            "actuator_3": self.telemetry_state.get("actuator_3", {"value": 0, "unit": "%", "timestamp": 0}),
            "actuator_4": self.telemetry_state.get("actuator_4", {"value": 0, "unit": "%", "timestamp": 0}),
            "actuator_5": self.telemetry_state.get("actuator_5", {"value": 0, "unit": "%", "timestamp": 0}),
            "actuator_6": self.telemetry_state.get("actuator_6", {"value": 0, "unit": "%", "timestamp": 0}),
        }

        try:
            jsonschema.validate(instance=packet, schema=self.schema)
        except jsonschema.ValidationError as e:
            print(f"Schema validation error: {e.message}")

        return packet


def parse_config_and_env(config_path: str) -> dict:
    """Parse configuration from JSON file."""
    load_dotenv(dotenv_path=os.path.join(os.path.dirname(config_path), ".env"))
    with open(config_path, "r") as f:
        config = json.load(f)
    env = {
        "mqtt_username": os.getenv("MQTT_USERNAME"),
        "mqtt_password": os.getenv("MQTT_PASSWORD"),
        "mqtt_broker_host": os.getenv("MQTT_BROKER_HOST"),
        "mqtt_broker_port": os.getenv("MQTT_BROKER_PORT"),
    }
    return config, env


def main():
    parser = argparse.ArgumentParser(description="ROV Telemetry Processor")
    parser.add_argument(
        "--config",
        type=str,
        required=True,
        help="Path to JSON configuration file",
    )
    args = parser.parse_args()

    config, env = parse_config_and_env(args.config)
    processor = TelemetryProcessor(config, env)
    processor.start()


if __name__ == "__main__":
    main()
