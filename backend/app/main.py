from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from app.core.config import settings
from app.core.database import init_db, check_db_connection
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

    # 데이터베이스 초기화 (실패해도 서버 시작)
    db_initialized = False
    try:
        db_initialized = await init_db(max_retries=3, retry_delay=5.0)
        if db_initialized:
            logger.info("Database initialized successfully")
        else:
            logger.warning("Database initialization failed - API will start without DB connection")
            logger.warning("Database features will be unavailable until connection is restored")
    except Exception as e:
        logger.error(f"Database initialization error: {e}")
        logger.warning("API will start without DB connection")

    # 스케줄러 시작 (DB 연결된 경우에만)
    if db_initialized:
        try:
            place_scheduler.start()
            logger.info("Scheduler started successfully")
        except Exception as e:
            logger.error(f"Failed to start scheduler: {e}")
    else:
        logger.warning("Scheduler not started - database connection required")

    logger.info("API Ready")

    yield

    # Shutdown
    logger.info("Shutting down Place Analytics API...")

    # 스케줄러 종료
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

# CORS 설정
# 로컬 개발용 + 프로덕션 도메인 포함
default_origins = [
    # 로컬 개발 환경
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:8080",
    "http://127.0.0.1:8080",
    # 프로덕션 환경 (Vercel)
    "https://place-chi.vercel.app",
    "https://place-analytics.vercel.app",
]

# 환경변수에서 추가 origins 병합
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
    """헬스체크 - DB 연결 상태 포함"""
    db_connected = await check_db_connection()
    return {
        "status": "healthy",
        "database": "connected" if db_connected else "disconnected"
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG
    )
