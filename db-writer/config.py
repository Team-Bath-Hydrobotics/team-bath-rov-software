import os
import sys

from dotenv import load_dotenv
from logger import setup_logger

logger = setup_logger("config")

load_dotenv()

MQTT_HOST = os.getenv("MQTT_HOST")
MQTT_PORT = int(os.getenv("MQTT_PORT", 1883))
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

if not all([MQTT_HOST, SUPABASE_URL, SUPABASE_KEY]):
    logger.critical("Missing required environment variables. Please check .env file.")
    sys.exit(1)
    