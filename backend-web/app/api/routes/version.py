"""独立产品版本和部署发布说明。"""
from fastapi import APIRouter

from app.services.version_service import check_update
from common.schemas.common import ApiResponse
from common.version import get_release_info

router = APIRouter(prefix="/version", tags=["版本检测"])


@router.get("/current", response_model=ApiResponse)
async def get_current_version_api() -> ApiResponse:
    return ApiResponse(success=True, data=get_release_info())


@router.get("/check", response_model=ApiResponse)
async def check_update_api() -> ApiResponse:
    result = await check_update()
    result.pop("error")
    return ApiResponse(success=True, data=result)
