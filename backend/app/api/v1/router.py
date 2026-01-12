"""
API V1 Router
모든 v1 API 라우터 통합
"""
from fastapi import APIRouter
from app.api.v1 import analyze, simulate, user_data

router = APIRouter(prefix="/v1")

# 분석 API
router.include_router(
    analyze.router,
    tags=["분석"]
)

# 시뮬레이션 API
router.include_router(
    simulate.router,
    tags=["시뮬레이션"]
)

# 사용자 데이터 API
router.include_router(
    user_data.router,
    tags=["사용자 데이터"]
)
