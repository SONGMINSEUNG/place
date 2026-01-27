from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base
from sqlalchemy.pool import NullPool
from sqlalchemy import text
from app.core.config import settings
import logging
import asyncio

logger = logging.getLogger(__name__)

# PostgreSQL 사용 시 connection pool 설정 추가
db_url = settings.database_url
is_postgres = db_url.startswith("postgresql")

engine_kwargs = {
    "echo": settings.DEBUG,
    "future": True,
}

# PostgreSQL에서는 NullPool 사용 (serverless 환경 호환)
if is_postgres:
    engine_kwargs["poolclass"] = NullPool
    # asyncpg 연결 옵션: 타임아웃 설정 (Supabase 일시 중지 대비)
    engine_kwargs["connect_args"] = {
        "timeout": 120,  # 연결 타임아웃 120초 (Supabase resume 대비)
        "command_timeout": 60,  # 쿼리 타임아웃 60초
    }

engine = create_async_engine(db_url, **engine_kwargs)

AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False
)

# alias for scheduler (backwards compatibility)
async_session_maker = AsyncSessionLocal

Base = declarative_base()


async def get_db():
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def init_db(max_retries: int = 3, retry_delay: float = 5.0) -> bool:
    """
    데이터베이스 초기화 (테이블 생성)

    Args:
        max_retries: 최대 재시도 횟수
        retry_delay: 재시도 간격 (초)

    Returns:
        bool: 초기화 성공 여부
    """
    # Import models to register them with Base
    from app.models import User, Place, PlaceSearch, RankHistory, SavedKeyword, AdlogTrainingData, UserInputData, KeywordParameter

    for attempt in range(1, max_retries + 1):
        try:
            logger.info(f"Database connection attempt {attempt}/{max_retries}...")
            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
            logger.info("Database initialized successfully")
            return True
        except Exception as e:
            logger.warning(f"Database connection attempt {attempt} failed: {e}")
            if attempt < max_retries:
                logger.info(f"Retrying in {retry_delay} seconds...")
                await asyncio.sleep(retry_delay)
            else:
                logger.error(f"Failed to connect to database after {max_retries} attempts")
                return False
    return False


async def check_db_connection() -> bool:
    """데이터베이스 연결 상태 확인"""
    try:
        async with engine.begin() as conn:
            await conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False
