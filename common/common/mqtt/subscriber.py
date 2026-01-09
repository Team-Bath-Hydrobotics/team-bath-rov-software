import json

import jsonschema
import paho.mqtt.client as mqtt

from .schema_loader import get_schema_for_topic, load_schemas


class MQTTSubscriber:
    def __init__(
        self, broker_address: str, broker_port: int, username: str, password: str
    ):
        """Initializes the MQTT subscriber with connection details."""
        self.client = mqtt.Client()
        self.id = f"subscriber_{id(self)}"
        self.client.username_pw_set(username=username, password=password)
        self.client.tls_set()
        self.client.tls_insecure_set(True)
        self.client.connect(broker_address, broker_port)
        self.schemas = load_schemas()
        if not self.schemas:
            raise ValueError("Failed to start subscriber: Could not load schemas.")

    def subscribe(self, topic: str):
        """Subscribes to a given topic."""
        self.client.subscribe(topic)
        self.client.on_message = self.on_message
        self.client.loop_start()

    def on_message(self, msg):
        """Callback for when a message is received."""
        schema = get_schema_for_topic(self.schemas, msg.topic)
        if not schema:
            raise ValueError(f"No schema defined for topic {msg.topic}")
        try:
            message = self.validate_message(msg, schema)
        except jsonschema.ValidationError as e:
            print(f"Invalid message on topic {msg.topic}: {e.message}")
        return message

    def validate_message(self, msg, schema):
        """Validates and returns the message payload."""
        message = json.loads(msg.payload)
        jsonschema.validate(instance=message, schema=schema)
        return message
