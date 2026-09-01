"""系统健康检查。"""
from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Request

from api.config import get_settings
from api.schemas import ApiResponse, HealthData

router = APIRouter(tags=["系统"])


@router.get("/health", response_model=ApiResponse[HealthData], summary="健康检查")
def health_check(request: Request) -> ApiResponse[HealthData]:
    settings = get_settings()
    data = HealthData(
        status="ok",
        service=settings.app_name,
        version=settings.app_version,
        environment=settings.environment,
        timestamp=datetime.now().isoformat(timespec="seconds"),
    )
    return ApiResponse[HealthData](data=data, request_id=request.state.request_id)
