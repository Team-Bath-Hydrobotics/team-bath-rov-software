"""MQTT publisher for telemetry output."""

import json
from typing import Optional

import paho.mqtt.client as mqtt

from data_interface.telemetry_data import TelemetryData


class MQTTPublisher:
    """Publishes processed telemetry data to MQTT broker."""

    def __init__(
        self,
        broker_host: str,
        broker_port: int = 1883,
        client_id: str = "telemetry-processor",
        base_topic: str = "rov/telemetry",
        username: Optional[str] = None,
        password: Optional[str] = None,
    ):
        self.broker_host = broker_host
        self.broker_port = broker_port
        self.client_id = client_id
        self.base_topic = base_topic

        self.client = mqtt.Client(
            client_id=client_id,
            callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
        )

        if username and password:
            self.client.username_pw_set(username, password)

        self.client.on_connect = self._on_connect
        self.client.on_disconnect = self._on_disconnect

        self.connected = False

    def _on_connect(self, client, userdata, flags, reason_code, properties):
        """Callback when connected to broker."""
        if reason_code == 0:
            print(f"Connected to MQTT broker at {self.broker_host}:{self.broker_port}")
            self.connected = True
        else:
            print(f"Failed to connect to MQTT broker: {reason_code}")

    def _on_disconnect(self, client, userdata, flags, reason_code, properties):
        """Callback when disconnected from broker."""
        print(f"Disconnected from MQTT broker: {reason_code}")
        self.connected = False

    def connect(self):
        """Connect to the MQTT broker."""
        try:
            self.client.connect(self.broker_host, self.broker_port)
            self.client.loop_start()
        except Exception as e:
            print(f"Failed to connect to MQTT broker: {e}")

    def disconnect(self):
        """Disconnect from the MQTT broker."""
        self.client.loop_stop()
        self.client.disconnect()

    def publish(self, telemetry: TelemetryData, subtopic: Optional[str] = None):
        """Publish telemetry data to MQTT."""
        if not self.connected:
            print("Not connected to MQTT broker")
            return

        topic = self.base_topic
        if subtopic:
            topic = f"{self.base_topic}/{subtopic}"
        elif telemetry.sensor_id:
            topic = f"{self.base_topic}/{telemetry.sensor_id}"

        payload = json.dumps(telemetry.to_dict())

        result = self.client.publish(topic, payload)
        if result.rc != mqtt.MQTT_ERR_SUCCESS:
            print(f"Failed to publish to {topic}: {result.rc}")
