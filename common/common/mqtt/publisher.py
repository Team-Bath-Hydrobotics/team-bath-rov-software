import json

import jsonschema
import paho.mqtt.client as mqtt

from .schema_loader import get_schema_for_topic, load_schemas


class MQTTPublisher:
    def __init__(
        self,
        tls_url: str,
        username: str,
        password: str,
        client_id: str,
        base_topic: str,
    ):
        """Initializes the MQTT publisher with connection details."""
        self.client = mqtt.Client(client_id=client_id)
        self.tls_url = tls_url
        self.id = f"publisher_{id(self)}"
        self.client.username_pw_set(username=username, password=password)
        self.client.tls_set()
        self.client.on_connect = self._on_connect
        self.client.on_disconnect = self._on_disconnect
        self.connected = False
        self.schemas = load_schemas()
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
            jsonschema.validate(instance=message, schema=schema)
            print(message)
            print(schema)
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
            host, port = self.tls_url.split(":")
            port = int(port)
            self.client.connect(host, port)
            self.client.loop_start()
        except Exception as e:
            print(f"Failed to connect to MQTT broker: {e}")
            self.connected = False

    def _on_connect(self, client, userdata, flags, rc, properties=None):
        """Callback when connected to broker."""
        if rc == 0:
            print(f"Connected to MQTT broker at {self.tls_url}")
            self.connected = True
        else:
            print(f"Failed to connect to MQTT broker: {rc}")

    def _on_disconnect(self, client, userdata, flags, rc=None, properties=None):
        """Callback when disconnected from broker."""
        if rc is not None:
            print(f"Disconnected from MQTT broker with code {rc}")
        else:
            print("Disconnected from MQTT broker")
        self.connected = False
