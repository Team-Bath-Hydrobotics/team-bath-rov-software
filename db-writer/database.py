from datetime import datetime, timezone

from config import SUPABASE_KEY, SUPABASE_URL
from logger import setup_logger
from schemas import ValidatedPayload
from supabase import Client, create_client

logger = setup_logger("database")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)


def extract_value(reading):
    return reading.value if reading is not None else None


def insert_telemetry(payload: ValidatedPayload) -> None:
    try:
        # Cast types and format timestamps
        # Postgres requires an integer for mission_id and ISO 8601 for timestamptz
        mission_id = int(payload.meta.mission_id)
        dt = datetime.fromtimestamp(payload.telemetry.timestamp, tz=timezone.utc)
        timestamp_iso = dt.isoformat()

        # Prepare base telemetry row
        telemetry_row = {
            "mission_id": mission_id,
            "timestamp": timestamp_iso,
            
            "attitude_x": extract_value(payload.telemetry.attitude_x),
            "attitude_y": extract_value(payload.telemetry.attitude_y),
            "attitude_z": extract_value(payload.telemetry.attitude_z),
            
            "angular_velocity_x": extract_value(payload.telemetry.angular_velocity_x),
            "angular_velocity_y": extract_value(payload.telemetry.angular_velocity_y),
            "angular_velocity_z": extract_value(payload.telemetry.angular_velocity_z),
            
            "angular_acceleration_x": extract_value(payload.telemetry.angular_acceleration_x),
            "angular_acceleration_y": extract_value(payload.telemetry.angular_acceleration_y),
            "angular_acceleration_z": extract_value(payload.telemetry.angular_acceleration_z),
            
            "acceleration_x": extract_value(payload.telemetry.acceleration_x),
            "acceleration_y": extract_value(payload.telemetry.acceleration_y),
            "acceleration_z": extract_value(payload.telemetry.acceleration_z),
            
            "velocity_x": extract_value(payload.telemetry.velocity_x),
            "velocity_y": extract_value(payload.telemetry.velocity_y),
            "velocity_z": extract_value(payload.telemetry.velocity_z),
            
            "depth": extract_value(payload.telemetry.depth),
            "ambient_temperature": extract_value(payload.telemetry.ambient_temperature),
            "internal_temperature": extract_value(payload.telemetry.internal_temperature)
        }

        # Insert base telemetry (Supabase expects array of objects)
        supabase.table("telemetry").insert([telemetry_row]).execute()

        # Prepare, insert actuator telemetry
        # Relational --> Go into own table
        actuator_rows = []
        for i in range(1, 7):
            act_reading = getattr(payload.telemetry, f"actuator_{i}", None)
            if act_reading:
                actuator_rows.append({
                    "mission_id": mission_id,
                    "timestamp": timestamp_iso,
                    "actuator_id": i, 
                    "value": act_reading.value
                })

        if actuator_rows:
            supabase.table("actuator_telemetry").insert(actuator_rows).execute()

    except Exception as e:
        # Log error but do not raise --> Prevent service from crashing
        logger.error(f"Supabase write failure for mission {payload.meta.mission_id}: {str(e)}")
        