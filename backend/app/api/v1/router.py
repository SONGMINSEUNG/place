"""
API V1 Router
모든 v1 API 라우터 통합
"""
from fastapi import APIRouter
from app.api.v1 import analyze, simulate, user_data, parameters, train, activity

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

# 파라미터 관리 API
router.include_router(
    parameters.router,
    tags=["키워드 파라미터"]
)

# 학습 관리 API
router.include_router(
    train.router,
    tags=["학습"]
)

# 활동 로그 API
router.include_router(
    activity.router,
    tags=["활동 로그"]
)
