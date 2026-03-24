from fastapi import APIRouter

from app.models import IcebergInput, PlatformThreatResult
from app.services import calculate_threats

router = APIRouter(tags=["iceberg"])


@router.post(
    "/mission/iceberg/calculate_threat",
    response_model=list[PlatformThreatResult],
)
async def calculate_threat(data: IcebergInput) -> list[PlatformThreatResult]:
    """Calculate surface and subsea threat levels for all platforms."""
    results = calculate_threats(
        iceberg_lat=data.iceberg_lat,
        iceberg_lon=data.iceberg_lon,
        keel_depth=data.keel_depth,
    )
    return [PlatformThreatResult(**r) for r in results]
