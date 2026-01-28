from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base
from sqlalchemy.pool import NullPool
from app.core.config import settings
import asyncio
import socket
import logging

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
    # asyncpg 연결 타임아웃 설정 (초 단위)
    engine_kwargs["connect_args"] = {
        "timeout": 30,  # 연결 타임아웃 30초
        "command_timeout": 60,  # 쿼리 타임아웃 60초
        "server_settings": {
            "application_name": "place-analytics"
        }
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


async def init_db():
    """
    데이터베이스 초기화 - 연결 테스트 및 테이블 생성
    상세한 디버깅 정보를 포함하여 연결 문제 진단
    """
    # Import models to register them with Base
    from app.models import User, Place, PlaceSearch, RankHistory, SavedKeyword, AdlogTrainingData, UserInputData, KeywordParameter

    # 디버깅: DB URL 확인 (비밀번호 마스킹)
    masked_url = db_url.replace(db_url.split(':')[2].split('@')[0], '****') if ':' in db_url else db_url
    logger.info(f"Attempting to connect to: {masked_url}")
    logger.info(f"Is PostgreSQL: {is_postgres}")

    if is_postgres:
        # 호스트 추출 및 DNS 확인
        try:
            # URL에서 호스트 추출: postgresql+asyncpg://user:pass@host:port/db
            host_part = db_url.split('@')[1].split('/')[0]
            host = host_part.split(':')[0]
            port = int(host_part.split(':')[1]) if ':' in host_part else 5432

            logger.info(f"Database host: {host}, port: {port}")

            # DNS 확인
            try:
                ip_addresses = socket.getaddrinfo(host, port, socket.AF_UNSPEC, socket.SOCK_STREAM)
                logger.info(f"DNS resolved: {len(ip_addresses)} addresses found")
                for addr in ip_addresses[:3]:  # 처음 3개만 로깅
                    logger.info(f"  - {addr[0].name}: {addr[4][0]}")
            except socket.gaierror as dns_err:
                logger.error(f"DNS resolution failed: {dns_err}")
                raise ConnectionError(f"Cannot resolve database host: {host}") from dns_err

        except (IndexError, ValueError) as parse_err:
            logger.warning(f"Could not parse database URL for diagnostics: {parse_err}")

    # 연결 시도 with timeout wrapper
    try:
        logger.info("Starting database connection (timeout: 30s)...")

        # asyncio timeout으로 추가 보호
        async with asyncio.timeout(45):  # 전체 작업 45초 제한
            async with engine.begin() as conn:
                logger.info("Connection established, creating tables...")
                await conn.run_sync(Base.metadata.create_all)

        logger.info("Database tables created successfully")

    except asyncio.TimeoutError:
        logger.error("DATABASE CONNECTION TIMEOUT: Connection took longer than 45 seconds")
        logger.error("Possible causes:")
        logger.error("  1. Firewall blocking port 5432/6543")
        logger.error("  2. Supabase project paused or unreachable")
        logger.error("  3. Network connectivity issues from Render")
        logger.error("  4. IPv6 connectivity issues (try forcing IPv4)")
        raise ConnectionError("Database connection timed out after 45 seconds")

    except Exception as e:
        error_type = type(e).__name__
        error_msg = str(e)

        logger.error(f"DATABASE CONNECTION FAILED: {error_type}")
        logger.error(f"Error message: {error_msg}")

        # 에러 유형별 상세 진단
        if "timeout" in error_msg.lower():
            logger.error("Diagnosis: Connection timeout - check network/firewall")
        elif "authentication" in error_msg.lower() or "password" in error_msg.lower():
            logger.error("Diagnosis: Authentication failed - check DATABASE_URL credentials")
        elif "does not exist" in error_msg.lower():
            logger.error("Diagnosis: Database not found - check database name in URL")
        elif "connection refused" in error_msg.lower():
            logger.error("Diagnosis: Connection refused - check host/port and firewall")
        elif "ssl" in error_msg.lower():
            logger.error("Diagnosis: SSL/TLS error - check SSL configuration")
        else:
            logger.error(f"Diagnosis: Unknown error - full exception: {repr(e)}")

        # 원본 예외 다시 발생
        raise
