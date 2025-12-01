"""Main entry point for the telemetry processor."""

import argparse
import json
import signal
import time
from typing import Dict, List, Optional

from aggregation.aggregator import AggregationResult, TimeWindowAggregator
from data_interface.network_type import NetworkEnum
from data_interface.telemetry_data import TelemetryData
from filters.base_filter import BaseFilter
from filters.kalman_filter import KalmanFilter
from input.telemetry_receiver import TelemetryReceiver
from output.mqtt_publisher import MQTTPublisher


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
        self.publisher = MQTTPublisher(
            broker_host=mqtt_config.get("broker_host", "localhost"),
            broker_port=mqtt_config.get("broker_port", 1883),
            client_id=mqtt_config.get("client_id", "telemetry-processor"),
            base_topic=mqtt_config.get("base_topic", "rov/telemetry"),
            username=mqtt_config.get("username"),
            password=mqtt_config.get("password"),
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

        # Setup aggregator
        agg_config = self.processing_config.get("aggregation", {})
        if agg_config.get("enabled", False):
            self.aggregator = TimeWindowAggregator(
                window_duration_ms=agg_config.get("window_ms", 1000),
                emit_callback=self._on_aggregation_ready,
            )

    def _on_telemetry_received(self, data: TelemetryData):
        """Handle received telemetry data."""
        # Apply filters
        filtered_data = data
        if data.sensor_id in self.filters:
            for f in self.filters[data.sensor_id]:
                filtered_data = f.apply(filtered_data)

        # Either aggregate or publish directly
        if self.aggregator:
            self.aggregator.add(filtered_data)
        else:
            self.publisher.publish(filtered_data)

    def _on_aggregation_ready(self, result: AggregationResult):
        """Handle aggregated data."""
        # Convert aggregation result to telemetry for publishing
        telemetry = TelemetryData(
            timestamp=result.timestamp,
            sensor_id=result.sensor_id,
            value=result.mean,
            unit=result.unit,
            metadata={
                "count": result.count,
                "min": result.min_value,
                "max": result.max_value,
            },
        )
        self.publisher.publish(telemetry, subtopic=f"{result.sensor_id}/aggregated")

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
