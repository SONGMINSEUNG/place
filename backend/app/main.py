from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from app.core.config import settings
from app.core.database import init_db
from app.api import api_router
from app.services.scheduler import place_scheduler
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

    # 스케줄러 시작
    try:
        place_scheduler.start()
        logger.info("Scheduler started successfully")
    except Exception as e:
        logger.error(f"Failed to start scheduler: {e}")

    logger.info("API Ready")

    yield

    # Shutdown
    logger.info("Shutting down Place Analytics API...")
    try:
        place_scheduler.stop()
        logger.info("Scheduler stopped")
    except Exception as e:
        logger.error(f"Error stopping scheduler: {e}")


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="네이버 플레이스 순위 분석 및 시뮬레이션 API",
    lifespan=lifespan
)

# CORS 설정 - 프로덕션 환경을 위해 명시적으로 설정
# 주의: Vercel 프론트엔드에서 요청 시 정확한 origin이 필요
default_origins = [
    # 로컬 개발 환경
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:8080",
    "http://127.0.0.1:8080",
    # 프로덕션 환경 - Vercel
    "https://place-chi.vercel.app",
    "https://place-analytics.vercel.app",
    # Vercel Preview URLs (와일드카드 패턴은 지원 안됨, 필요시 추가)
]

# 환경변수에서 추가 origins 가져오기
env_origins = settings.allowed_origins_list
origins = list(set(default_origins + env_origins))

# 빈 문자열 제거
origins = [o for o in origins if o and o.strip()]

logger.info(f"CORS allowed origins: {origins}")

# CORS 미들웨어 - 가장 먼저 추가해야 함
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],  # 모든 HTTP 메서드 허용
    allow_headers=["*"],  # 모든 헤더 허용
    expose_headers=["*"],
    max_age=600,  # preflight 캐시 10분
)

# API 라우터 등록
app.include_router(api_router, prefix="/api")


@app.get("/")
@app.head("/")
async def root():
    return {
        "name": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "status": "running"
    }


@app.get("/health")
@app.head("/health")
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
