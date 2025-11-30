import fnmatch
import json
from pathlib import Path

import jsonschema
import paho.mqtt.client as mqtt


class MQTTSubscriber:
    def __init__(
        self, broker_address: str, broker_port: int, username: str, password: str
    ):
        """Initializes the MQTT subscriber with connection details."""
        self.client = mqtt.Client()
        self.id = f"subscriber_{id(self)}"
        self.client.username_pw_set(username=username, password=password)
        self.client.tls_set()
        self.client.connect(broker_address, broker_port)
        self.schemas = self.load_schemas()
        if not self.schemas:
            raise ValueError("Failed to start subscriber: Could not load schemas.")

    def subscribe(self, topic: str):
        """Subscribes to a given topic."""
        self.client.subscribe(topic)
        self.client.on_message = self.on_message
        self.client.loop_start()

    def on_message(self, msg):
        """Callback for when a message is received."""
        schema = self.get_schema_for_topic(msg.topic)
        if not schema:
            raise ValueError(f"No schema defined for topic {msg.topic}")
        try:
            message = self.validate_message(msg, schema)
        except jsonschema.ValidationError as e:
            print(f"Invalid message on topic {msg.topic}: {e.message}")
        return message

    def get_schema_for_topic(self, topic):
        """Retrieves the schema for a given topic using wildcard matching."""
        for pattern, schema in self.schemas.items():
            if fnmatch.fnmatch(topic, pattern.replace("+", "*")):
                return schema
        return None

    def validate_message(self, msg, schema):
        """Validates and returns the message payload."""
        message = json.loads(msg.payload)
        jsonschema.validate(instance=message, schema=schema)
        return message

    def load_schemas(self):
        """Tries to load all schemas from the schemas directory."""
        try:
            video_frame_schema = json.load(
                open(Path("schemas/video_frame.schema.json"))
            )
            rov_telemetry_schema = json.load(
                open(Path("schemas/rov_telemetry.schema.json"))
            )
            rov_command_schema = json.load(
                open(Path("schemas/rov_command.schema.json"))
            )
            float_telemetry_schema = json.load(
                open(Path("schemas/float_telemetry.schema.json"))
            )
            video_processor_status_schema = json.load(
                open(Path("schemas/video_processor_status.schema.json"))
            )
            pre_processor_status_schema = json.load(
                open(Path("schemas/pre_processor_status.schema.json"))
            )
            return {
                "hydrobotics/video/+/frame": video_frame_schema,
                "hydrobotics/rov/+/telemetry": rov_telemetry_schema,
                "hydrobotics/rov/+/command": rov_command_schema,
                "hydrobotics/float/+/telemetry": float_telemetry_schema,
                "hydrobotics/project/video_processor/status": video_processor_status_schema,
                "hydrobotics/project/pre_processor/status": pre_processor_status_schema,
            }
        except Exception as e:
            print(f"Error loading schemas: {e}")
            return None
