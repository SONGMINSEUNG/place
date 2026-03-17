from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base
from sqlalchemy.pool import NullPool
from app.core.config import settings
import logging

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

# PostgreSQL에서는 NullPool + pgbouncer 호환 설정
if is_postgres:
    engine_kwargs["poolclass"] = NullPool

    # --- pgbouncer (transaction mode) 완전 호환 설정 ---
    #
    # pgbouncer transaction mode에서는 prepared statement가 작동하지 않는다.
    # 두 레이어 모두에서 비활성화해야 한다:
    #
    # Layer 1) asyncpg 레벨 - connect_args로 전달
    #   statement_cache_size=0: asyncpg의 내장 prepared statement 캐시 비활성화
    #
    # Layer 2) SQLAlchemy asyncpg dialect 레벨 - URL 쿼리 파라미터로 전달
    #   prepared_statement_cache_size=0: dialect의 prepared statement 캐시 비활성화
    #   이것이 없으면 SQLAlchemy가 자체적으로 PREPARE/DEALLOCATE를 실행하여
    #   "select pg_catalog.version()" 등의 초기 쿼리에서 에러 발생

    engine_kwargs["connect_args"] = {
        "statement_cache_size": 0,  # asyncpg 내장 prepared stmt 캐시 OFF
    }

    # URL에 prepared_statement_cache_size 쿼리 파라미터 추가
    separator = "&" if "?" in db_url else "?"
    db_url = f"{db_url}{separator}prepared_statement_cache_size=0"

    logger.info(
        "[DATABASE] PostgreSQL + pgbouncer 호환 모드 활성화 "
        "(asyncpg statement_cache_size=0, dialect prepared_statement_cache_size=0)"
    )

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
