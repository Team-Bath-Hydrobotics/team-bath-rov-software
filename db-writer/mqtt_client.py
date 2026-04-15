import json
import paho.mqtt.client as mqtt
from pydantic import ValidationError
from schemas import ValidatedPayload
from database import insert_telemetry
from logger import setup_logger

logger = setup_logger("mqtt_client")

def on_connect(client, userdata, flags, reason_code, properties):
    if reason_code == 0:
        logger.info("Successfully connected to MQTT broker.")
        # Subscribe (QoS 1)
        client.subscribe("hydrobotics/rov/+/telemetry", qos=1)
        logger.info("Subscribed to hydrobotics/rov/+/telemetry")
    else:
        logger.error(f"Failed to connect to MQTT broker with return code {reason_code}")

def on_message(client, userdata, msg):
    try:
        # Decode raw byte payload into dictionary
        raw_payload = msg.payload.decode('utf-8')
        payload_dict = json.loads(raw_payload)
        
        # Validate against Pydantic schema
        validated_data = ValidatedPayload(**payload_dict)

        # Insert into database
        insert_telemetry(validated_data)

    except json.JSONDecodeError:
        logger.warning("Discarded message: Payload is not valid JSON.")
    except ValidationError as e:
        # Schema validation failure --> Log detailed error and discard
        logger.warning(f"Discarded message: Schema validation failed.\nDetails: {e.errors()}")
    except Exception as e:
        logger.error(f"Unexpected error processing message: {str(e)}")