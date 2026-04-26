import base64
import gc
import logging
import os
import threading
import tomllib
from pathlib import Path

import cv2
import numpy as np
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from src.pipeline import CrabPipeline

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

load_dotenv(Path(__file__).resolve().parents[1] / ".env", override=False)


def get_version():
    pyproject = Path(__file__).resolve().parents[1] / "pyproject.toml"
    with open(pyproject, "rb") as f:
        data = tomllib.load(f)
    return data["tool"]["poetry"]["version"]


APP_VERSION = get_version()

app = FastAPI()

pipeline = None
model = None
pipeline_lock = threading.Lock()


def resolve_model_from_env():
    raw_value = os.getenv("MODEL", "yolov8")
    normalized = raw_value.strip().strip('"').strip("'").lower().replace("-", "_")
    if normalized == "rfdetr":
        normalized = "rf_detr"
    if normalized not in {"yolov8", "rf_detr", "yolo"}:
        logger.warning("Invalid MODEL=%r; defaulting to yolov8", raw_value)
        normalized = "yolov8"
    return normalized


def to_jsonable(value):
    if isinstance(value, np.floating):
        return float(value)
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.ndarray):
        return [to_jsonable(item) for item in value.tolist()]
    if isinstance(value, dict):
        return {k: to_jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [to_jsonable(item) for item in value]
    return value


@app.on_event("startup")
def startup():
    global model
    model = resolve_model_from_env()
    logger.info(f"API starting up with model: {model}")


def get_pipeline():
    global pipeline
    global model
    if pipeline is None:
        logger.info("Initializing pipeline...")
        with pipeline_lock:
            if pipeline is None:
                if model is None:
                    model = resolve_model_from_env()
                    logger.info(f"API starting up with model: {model}")
                pipeline = CrabPipeline(model_type=model)
                logger.info("Pipeline initialized.")
    return pipeline


@app.on_event("shutdown")
def shutdown():
    global pipeline
    global model
    pipeline = None
    model = None
    gc.collect()


class FrameRequest(BaseModel):
    frame: str


@app.get("/model")
def model_info():
    return {
        "app_name": "crab_detection_api",
        "app_version": APP_VERSION,
        "framework": "pytorch",
        "model": model,
    }


@app.post("/detect")
def detect(request: FrameRequest):
    active_pipeline = get_pipeline()

    image_bytes = base64.b64decode(request.frame)
    np_arr = np.frombuffer(image_bytes, np.uint8)
    frame = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)

    if frame is None:
        raise HTTPException(status_code=400, detail="Could not decode image")

    processed, count, detections = active_pipeline.process_frame(frame)

    # Convert detections (list-based or dict-based) and numpy values for JSON serialization
    serializable_detections = to_jsonable(detections)
    return {
        "processed_frame": base64.b64encode(cv2.imencode(".jpg", processed)[1]).decode(
            "utf-8"
        ),
        "detections": serializable_detections,
        "count": int(count),
    }
