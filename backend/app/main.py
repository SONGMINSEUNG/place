from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from app.core.config import settings
from app.core.database import init_db
from app.api import api_router
import logging

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """앱 시작/종료 시 실행"""
    # Startup
    logger.info("Starting Place Analytics API...")
    await init_db()
    logger.info("Database initialized")
    logger.info("API Ready")

    yield

    # Shutdown
    logger.info("Shutting down Place Analytics API...")


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="네이버 플레이스 순위 분석 및 시뮬레이션 API",
    lifespan=lifespan
)

# CORS 설정
# 환경변수 ALLOWED_ORIGINS가 있으면 사용, 없으면 로컬 개발용 기본값
default_origins = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:8080",
    "http://127.0.0.1:8080",
]

# settings.allowed_origins_list가 기본값이 아니면 환경변수 사용
origins = settings.allowed_origins_list if settings.ALLOWED_ORIGINS != "http://localhost:3000,https://your-domain.com" else default_origins

# 프로덕션 환경에서 추가 origins 병합
if settings.ALLOWED_ORIGINS and settings.ALLOWED_ORIGINS != "http://localhost:3000,https://your-domain.com":
    # 환경변수에서 설정된 origins와 기본값 병합
    origins = list(set(default_origins + settings.allowed_origins_list))

logger.info(f"CORS allowed origins: {origins}")

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,  # 명시적 origin 목록
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"],
    allow_headers=["*"],
    expose_headers=["*"],
)

# API 라우터 등록
app.include_router(api_router, prefix="/api")


@app.get("/")
async def root():
    return {
        "name": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "status": "running"
    }


@app.get("/health")
async def health_check():
    return {"status": "healthy"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG
    )
