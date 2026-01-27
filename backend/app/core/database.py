from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base
from sqlalchemy.pool import NullPool
from app.core.config import settings

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
    # Import models to register them with Base
    from app.models import User, Place, PlaceSearch, RankHistory, SavedKeyword, AdlogTrainingData, UserInputData, KeywordParameter
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
