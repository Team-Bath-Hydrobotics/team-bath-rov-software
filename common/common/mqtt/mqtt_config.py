from dataclasses import dataclass


@dataclass
class MqttConfig:
    """Configuration for MQTT connections"""

    broker_host: str
    broker_port: int
    username: str
    password: str
    id: str
    base_topic: str
