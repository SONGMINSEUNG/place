from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base
from sqlalchemy.pool import NullPool
from app.core.config import settings
import logging
import asyncpg

logger = logging.getLogger(__name__)

# PostgreSQL 사용 시 connection pool 설정 추가
db_url = settings.database_url
is_postgres = db_url.startswith("postgresql")

if not is_postgres:
    logger.warning(
        "========================================\n"
        "[DATABASE] SQLite 사용 중!\n"
        "서버 재시작 시 회원 데이터가 유실될 수 있습니다.\n"
        ".env 파일에 DATABASE_URL을 PostgreSQL URL로 설정하세요.\n"
        "========================================"
    )

engine_kwargs = {
    "echo": settings.DEBUG,
    "future": True,
}

# PostgreSQL에서는 NullPool 사용 (serverless 환경 호환)
if is_postgres:
    engine_kwargs["poolclass"] = NullPool

    # asyncpg 직접 연결 함수 (pgbouncer 호환)
    # URL에서 연결 정보 추출
    import re
    from urllib.parse import urlparse, parse_qs

    parsed = urlparse(db_url.replace("postgresql+asyncpg://", "postgresql://"))

    async def create_asyncpg_connection():
        """pgbouncer 호환을 위해 statement_cache_size=0으로 asyncpg 연결 생성"""
        return await asyncpg.connect(
            host=parsed.hostname,
            port=parsed.port or 5432,
            user=parsed.username,
            password=parsed.password,
            database=parsed.path.lstrip("/"),
            statement_cache_size=0,  # pgbouncer 호환 핵심 설정
            timeout=30,
            command_timeout=60,
        )

    engine_kwargs["async_creator"] = create_asyncpg_connection

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


async def init_db():
    """
    데이터베이스 초기화 - 테이블 생성
    """
    # Import models to register them with Base
    from app.models import User, Place, PlaceSearch, RankHistory, SavedKeyword, AdlogTrainingData, UserInputData, KeywordParameter

    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("Database initialized successfully")
    except Exception as e:
        logger.error(f"Database init failed: {e}")
        raise
