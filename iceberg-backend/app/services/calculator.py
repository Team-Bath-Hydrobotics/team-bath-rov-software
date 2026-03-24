import math
from dataclasses import dataclass

EARTH_RADIUS_NM = 3440.065  # Earth radius in nautical miles


@dataclass(frozen=True)
class Platform:
    name: str
    latitude: float
    longitude: float
    depth: float  # water depth in metres (positive)


PLATFORMS = [
    Platform("Hibernia", 43.7504, -48.7819, 78),
    Platform("Sea Rose", 46.7895, -48.1417, 107),
    Platform("Terra Nova", 46.4000, -48.4000, 91),
    Platform("Hebron", 46.5440, -48.4980, 93),
]


def haversine_distance_nm(
    lat1: float, lon1: float, lat2: float, lon2: float
) -> float:
    """Haversine distance between two lat/lon points in nautical miles."""
    d_lat = math.radians(lat2 - lat1)
    d_lon = math.radians(lon2 - lon1)
    a = (
        math.sin(d_lat / 2) ** 2
        + math.cos(math.radians(lat1))
        * math.cos(math.radians(lat2))
        * math.sin(d_lon / 2) ** 2
    )
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return EARTH_RADIUS_NM * c


def surface_threat(
    distance_nm: float, keel_depth: float, platform_depth: float
) -> str:
    """
    Surface platform threat level.

    Grounding override: if keel_depth >= 1.1 * platform_depth, iceberg
    grounds before reaching the platform -> Green regardless of distance.
    Otherwise:
      Green:  distance > 10 nm
      Yellow: 5 <= distance <= 10 nm
      Red:    distance < 5 nm
    """
    if keel_depth >= 1.1 * platform_depth:
        return "Green"

    if distance_nm > 10:
        return "Green"
    if distance_nm >= 5:
        return "Yellow"
    return "Red"


def subsea_threat(
    distance_nm: float, keel_depth: float, platform_depth: float
) -> str:
    """
    Subsea asset threat level.

    Only threatened if distance <= 25 nm.
      Green (grounding):    keel >= 1.1 * depth
      Red (critical):       0.9 * depth <= keel < 1.1 * depth
      Yellow (caution):     0.7 * depth <= keel < 0.9 * depth
      Green (safe passing): keel < 0.7 * depth
    """
    if distance_nm > 25:
        return "Green"

    if keel_depth >= 1.1 * platform_depth:
        return "Green"
    if keel_depth >= 0.9 * platform_depth:
        return "Red"
    if keel_depth >= 0.7 * platform_depth:
        return "Yellow"
    return "Green"


def calculate_threats(
    iceberg_lat: float,
    iceberg_lon: float,
    keel_depth: float,
) -> list[dict]:
    """Calculate threat levels for all platforms given iceberg data."""
    results = []
    for platform in PLATFORMS:
        dist = haversine_distance_nm(
            iceberg_lat, iceberg_lon, platform.latitude, platform.longitude
        )
        results.append(
            {
                "platform_name": platform.name,
                "distance_nm": round(dist, 2),
                "surface_threat": surface_threat(dist, keel_depth, platform.depth),
                "subsea_threat": subsea_threat(dist, keel_depth, platform.depth),
            }
        )
    return results
