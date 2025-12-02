import json

import jsonschema
import paho.mqtt.client as mqtt

from .schema_loader import get_schema_for_topic


class MQTTPublisher:
    def __init__(
        self,
        broker_address: str,
        broker_port: int,
        username: str,
        password: str,
        client_id: str,
        base_topic: str,
    ):
        """Initializes the MQTT publisher with connection details."""
        self.client = mqtt.Client(client_id=client_id)
        self.id = f"publisher_{id(self)}"
        self.client.username_pw_set(username=username, password=password)
        self.client.tls_set()
        self.client.on_connect = self._on_connect
        self.client.on_disconnect = self._on_disconnect
        self.connected = False
        self.schemas = self.load_schemas()
        self.base_topic = base_topic
        if not self.schemas:
            raise ValueError("Failed to start subscriber: Could not load schemas.")

    def publish(self, message: dict):
        """Publishes a message to a given topic after validating it against the schema."""
        try:
            topic = self.base_topic
            schema = get_schema_for_topic(self.schemas, topic)
            if not schema:
                raise ValueError(f"No schema defined for topic {topic}")
            valid = jsonschema.validate(instance=message, schema=schema)
            if not valid:
                raise jsonschema.ValidationError("Message does not conform to schema.")
            payload = json.dumps(message)
            result = self.client.publish(topic, payload)
            if result.rc != mqtt.MQTT_ERR_SUCCESS:
                print(f"Failed to publish to {topic}: {result.rc}")
        except jsonschema.ValidationError as e:
            print(f"Invalid message for topic {topic}: {e.message}")
        except Exception as e:
            print(f"Failed to publish message to topic {topic}: {e}")

    def disconnect(self):
        """Disconnect from the MQTT broker."""
        self.client.loop_stop()
        self.client.disconnect()

    def connect(self):
        """Connect to the MQTT broker."""
        try:
            self.client.connect(self.broker_host, self.broker_port)
            self.client.loop_start()
        except Exception as e:
            print(f"Failed to connect to MQTT broker: {e}")

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
