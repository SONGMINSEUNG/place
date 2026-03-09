"""
Application Configuration
환경 변수 기반 설정 관리
"""
from pydantic_settings import BaseSettings
from pydantic import SecretStr, model_validator
from typing import Optional, List
import os
import logging

logger = logging.getLogger(__name__)


class Settings(BaseSettings):
    """Application settings loaded from environment variables"""

    # ===========================================
    # Application
    # ===========================================
    APP_NAME: str = "Place Analytics"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False
    SECRET_KEY: str = "your-secret-key-change-in-production"

    # ===========================================
    # Server
    # ===========================================
    HOST: str = "0.0.0.0"
    PORT: int = 8001

    # ===========================================
    # JWT Authentication
    # ===========================================
    JWT_SECRET_KEY: str = "your-jwt-secret-key-here"
    JWT_ALGORITHM: str = "HS256"
    ALGORITHM: str = "HS256"  # alias for JWT_ALGORITHM
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    @model_validator(mode="after")
    def validate_critical_settings(self):
        """SECRET_KEY와 DATABASE_URL 유효성 검증"""
        # SECRET_KEY 검증: 기본값 사용 시 경고
        dangerous_defaults = [
            "your-secret-key-change-in-production",
            "your-jwt-secret-key-here",
            "secret",
            "changeme",
        ]
        if self.SECRET_KEY in dangerous_defaults:
            logger.warning(
                "[SECURITY] SECRET_KEY가 기본값입니다. "
                ".env 파일에 안전한 SECRET_KEY를 설정하세요. "
                "기본값 사용 시 서버 재시작마다 기존 토큰이 무효화될 수 있습니다."
            )

        # DATABASE_URL 검증: 없거나 SQLite면 경고
        if not self.DATABASE_URL:
            logger.warning(
                "[DATABASE] DATABASE_URL이 설정되지 않았습니다. "
                "SQLite 폴백을 사용하면 서버 재시작 시 데이터가 유실될 수 있습니다. "
                ".env 파일에 Supabase PostgreSQL URL을 설정하세요."
            )
        elif "sqlite" in self.DATABASE_URL.lower():
            logger.warning(
                "[DATABASE] SQLite를 사용 중입니다. "
                "프로덕션 환경에서는 PostgreSQL 사용을 권장합니다."
            )

        return self

    # ===========================================
    # ADLOG API (Hidden from frontend)
    # ===========================================
    ADLOG_API_URL: str = "http://adlog.ai.kr/placeAnalysis.php"

    # ===========================================
    # Naver API (DataLab)
    # ===========================================
    NAVER_CLIENT_ID: Optional[str] = None
    NAVER_CLIENT_SECRET: Optional[str] = None

    # ===========================================
    # Naver AD API (Keyword Volume)
    # ===========================================
    NAVER_AD_API_KEY: Optional[str] = None
    NAVER_AD_SECRET_KEY: Optional[str] = None
    NAVER_AD_CUSTOMER_ID: Optional[str] = None

    # ===========================================
    # Supabase Database
    # ===========================================
    SUPABASE_URL: Optional[str] = None
    SUPABASE_KEY: Optional[str] = None
    SUPABASE_SERVICE_KEY: Optional[str] = None
    DATABASE_URL: Optional[str] = None  # 환경변수로 설정 시 PostgreSQL 사용

    @property
    def database_url(self) -> str:
        """
        DATABASE_URL 환경변수가 있으면 PostgreSQL 사용, 없으면 SQLite 사용
        postgresql:// -> postgresql+asyncpg:// 자동 변환
        """
        if self.DATABASE_URL:
            url = self.DATABASE_URL
            # Supabase/Render에서 제공하는 URL을 asyncpg용으로 변환
            if url.startswith("postgresql://"):
                url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
            elif url.startswith("postgres://"):
                url = url.replace("postgres://", "postgresql+asyncpg://", 1)
            return url
        # 로컬 개발용 SQLite
        return "sqlite+aiosqlite:///./place_analytics.db"

    # ===========================================
    # Redis Cache (Optional)
    # ===========================================
    REDIS_URL: Optional[str] = None

    # ===========================================
    # ML Model Settings
    # ===========================================
    MODEL_PATH: str = "./ml_models"
    MIN_TRAINING_SAMPLES: int = 100
    TRAINING_SCHEDULE_HOUR: int = 3

    # ===========================================
    # CORS Settings
    # ===========================================
    ALLOWED_ORIGINS: str = "http://localhost:3000,https://place-chi.vercel.app,https://place-analytics.vercel.app"

    @property
    def allowed_origins_list(self) -> List[str]:
        """Parse ALLOWED_ORIGINS to list"""
        return [origin.strip() for origin in self.ALLOWED_ORIGINS.split(",")]

    # ===========================================
    # Rate Limiting
    # ===========================================
    RATE_LIMIT_ANALYZE: str = "30/minute"
    RATE_LIMIT_DEFAULT: str = "100/minute"

    class Config:
        env_file = ".env"
        case_sensitive = True
        extra = "ignore"  # 추가 환경변수 무시


# Create global settings instance
settings = Settings()


def get_settings() -> Settings:
    """Dependency injection for settings"""
    return settings
