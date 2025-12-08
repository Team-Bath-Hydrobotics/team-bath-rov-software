import json

import jsonschema
import paho.mqtt.client as mqtt

from .mqtt_config import MqttConfig
from .schema_loader import get_schema_for_topic, load_schemas


class MQTTPublisher:
    def __init__(
        self,
        config: MqttConfig,
    ):
        """Initializes the MQTT publisher with connection details."""
        self.client = mqtt.Client(client_id=config.id)
        self.broker_host = config.broker_host
        self.broker_port = config.broker_port
        self.id = f"publisher_{id(self)}"
        self.client.username_pw_set(username=config.username, password=config.password)
        self.client.tls_set()
        self.connected = False
        self.schemas = load_schemas()
        self.base_topic = config.base_topic
        if not self.schemas:
            raise ValueError("Failed to start subscriber: Could not load schemas.")

    def publish(self, message: dict):
        """Publishes a message to a given topic after validating it against the schema."""
        try:
            topic = self.base_topic
            schema = get_schema_for_topic(self.schemas, topic)
            if not schema:
                raise ValueError(f"No schema defined for topic {topic}")
            jsonschema.validate(instance=message, schema=schema)
            payload = json.dumps(message)
            result = self.client.publish(topic, payload)
            if result.rc != mqtt.MQTT_ERR_SUCCESS:
                print(f"Failed to publish to {topic}: {result.rc}")
        except jsonschema.ValidationError as e:
            print(f"Invalid message for topic {topic}: {e.message} at {list(e.path)}")
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
            self.connected = True
        except Exception as e:
            print(f"Publisher failed to connect to MQTT broker: {e}")
            self.connected = False

    def is_connected(self) -> bool:
        """Returns whether the client is connected to the broker."""
        return self.connected
