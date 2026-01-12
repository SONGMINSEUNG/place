from fastapi import APIRouter
from app.api.v1.router import router as v1_router
from app.api.auth import router as auth_router
from app.api.place import router as place_router
from app.api.keywords import router as keywords_router

api_router = APIRouter()

# Auth API
api_router.include_router(auth_router, prefix="/auth", tags=["인증"])

# Place API (기존)
api_router.include_router(place_router, prefix="/place", tags=["플레이스"])

# Keywords API (기존)
api_router.include_router(keywords_router, prefix="/keywords", tags=["키워드"])

# V1 API (ADLOG 분석)
api_router.include_router(v1_router)
