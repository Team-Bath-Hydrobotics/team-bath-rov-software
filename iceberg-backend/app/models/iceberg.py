from pydantic import BaseModel


class IcebergInput(BaseModel):
    iceberg_lat: float
    iceberg_lon: float
    iceberg_heading: float
    keel_depth: float


class PlatformThreatResult(BaseModel):
    platform_name: str
    distance_nm: float
    surface_threat: str  # "Green", "Yellow", or "Red"
    subsea_threat: str  # "Green", "Yellow", or "Red"
