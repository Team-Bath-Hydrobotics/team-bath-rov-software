import fnmatch
import json
from pathlib import Path


def load_schemas():
    """Tries to load all schemas from the schemas directory."""
    try:
        base = Path(__file__).parent / "schemas"
        print(f"Loading schemas from {base}")
        video_frame_schema = json.load(open(base / "video_frame.schema.json"))
        rov_telemetry_schema = json.load(open(base / "rov_telemetry.schema.json"))
        rov_command_schema = json.load(open(base / "rov_command.schema.json"))
        float_telemetry_schema = json.load(open(base / "float_telemetry.schema.json"))
        status_schema = json.load(open(base / "project_status.schema.json"))
        return {
            "hydrobotics/video/+/frame": video_frame_schema,
            "hydrobotics/rov/+/telemetry": rov_telemetry_schema,
            "hydrobotics/rov/+/command": rov_command_schema,
            "hydrobotics/float/+/telemetry": float_telemetry_schema,
            "hydrobotics/project/video_processor/status": status_schema,
            "hydrobotics/project/pre_processor/status": status_schema,
        }
    except Exception as e:
        print(f"Error loading schemas: {e}")
        return None


def get_schema_for_topic(schemas, topic):
    """Retrieves the schema for a given topic using wildcard matching."""
    for pattern, schema in schemas.items():
        if fnmatch.fnmatch(topic, pattern.replace("+", "*")):
            return schema
    return None


def init_state_from_schema(schema: dict) -> dict:
    state = {}
    for key, prop in schema.get("properties", {}).items():
        if prop["type"] == "object" and "properties" in prop:
            if "value" in prop["properties"] and "unit" in prop["properties"]:
                unit = (
                    prop["properties"]["unit"].get("const")
                    or prop["properties"]["unit"].get("enum", [None])[0]
                )
                state[key] = {"value": None, "unit": unit}
            else:
                state[key] = init_state_from_schema(prop)
        else:
            state[key] = None
    return state
