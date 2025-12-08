import jsonschema
import paho.mqtt.client as mqtt

from .mqtt_config import MqttConfig
from .schema_loader import get_schema_for_topic, load_schemas


class MQTTSubscriber:
    def __init__(self, config: MqttConfig):
        """Initializes the MQTT subscriber with connection details."""
        self.client = mqtt.Client(client_id=config.id)
        self.broker_host = config.broker_host
        self.broker_port = config.broker_port
        self.base_topic = config.base_topic
        self.id = f"subscriber_{id(self)}"
        self.client.username_pw_set(username=config.username, password=config.password)
        self.client.tls_set()
        self.connected = False
        self.schemas = load_schemas()
        if not self.schemas:
            raise ValueError("Failed to start subscriber: Could not load schemas.")

    def subscribe(self):
        """Subscribes to a given topic."""
        self.client.subscribe(self.base_topic)
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
            print(f"Subscriber failed to connect to MQTT broker: {e}")
            self.connected = False

    def is_connected(self) -> bool:
        """Returns whether the client is connected to the broker."""
        return self.connected
