"""
Application Configuration
환경 변수 기반 설정 관리
"""
from pydantic_settings import BaseSettings
from pydantic import SecretStr
from typing import Optional, List
import os


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
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

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
    ALLOWED_ORIGINS: str = "http://localhost:3000,https://your-domain.com"

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
