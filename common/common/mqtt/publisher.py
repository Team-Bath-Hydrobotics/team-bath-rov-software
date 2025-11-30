import json

import jsonschema
import paho.mqtt.client as mqtt


class MQTTPublisher:
    def __init__(
        self, broker_address: str, broker_port: int, username: str, password: str
    ):
        """Initializes the MQTT publisher with connection details."""
        self.client = mqtt.Client()
        self.id = f"publisher_{id(self)}"
        self.client.username_pw_set(username=username, password=password)
        self.client.tls_set()
        self.client.connect(broker_address, broker_port)
        self.client.loop_start()

    def publish(self, topic: str, message: dict, schema: dict):
        """Publishes a message to a given topic after validating it against the schema."""
        try:
            jsonschema.validate(instance=message, schema=schema)
            self.client.publish(topic, json.dumps(message))
        except jsonschema.ValidationError as e:
            print(f"Invalid message for topic {topic}: {e.message}")
        except Exception as e:
            print(f"Failed to publish message to topic {topic}: {e}")
