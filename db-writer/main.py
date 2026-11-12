import paho.mqtt.client as mqtt
from config import MQTT_HOST, MQTT_PORT
from logger import setup_logger
from mqtt_client import on_connect, on_message

logger = setup_logger("main")

def start_service():
    # Initialise client
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    
    # Attach callbacks
    client.on_connect = on_connect
    client.on_message = on_message

    logger.info(f"Attempting to connect to broker at {MQTT_HOST}:{MQTT_PORT}...")
    
    try:
        # Connect to broker
        client.connect(MQTT_HOST, MQTT_PORT, keepalive=60)
        
        # Loop forever handles reconnects and message processing
        client.loop_forever()
    except KeyboardInterrupt:
        logger.info("Keyboard interrupt received. Shutting down...")
        client.disconnect()
    except Exception as e:
        logger.critical(f"Fatal error in MQTT loop: {str(e)}")

if __name__ == "__main__":
    start_service()
    