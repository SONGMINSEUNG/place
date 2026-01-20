"""
Pytest Configuration and Fixtures
E2E 및 통합 테스트를 위한 공통 설정
"""
import pytest
import pytest_asyncio
import asyncio
from typing import AsyncGenerator, Generator
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, date

from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

from app.main import app
from app.core.database import get_db


# ===========================================
# Database Fixtures
# ===========================================

@pytest.fixture
def mock_db() -> MagicMock:
    """Mock database session for unit tests."""
    db = MagicMock(spec=AsyncSession)
    db.commit = AsyncMock()
    db.refresh = AsyncMock()
    db.execute = AsyncMock()
    db.add = MagicMock()
    return db


# ===========================================
# HTTP Client Fixtures
# ===========================================

@pytest_asyncio.fixture
async def async_client() -> AsyncGenerator[AsyncClient, None]:
    """
    Async HTTP client for E2E tests.
    Uses ASGITransport to test the FastAPI app directly.
    """
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


# ===========================================
# Mock Data Fixtures
# ===========================================

@pytest.fixture
def mock_naver_places() -> list:
    """Mock Naver place search results."""
    return [
        {
            "place_id": f"place_{i}",
            "name": f"테스트 맛집 {i}",
            "category": "음식점",
            "visitor_review_count": 100 - i * 5,
            "blog_review_count": 50 - i * 2,
            "save_count": 200 - i * 10,
            "address": f"서울시 강남구 테스트로 {i}",
        }
        for i in range(1, 21)
    ]


@pytest.fixture
def mock_adlog_response() -> dict:
    """Mock ADLOG API response."""
    return {
        "places": [
            {
                "place_id": f"place_{i}",
                "name": f"테스트 맛집 {i}",
                "rank": i,
                "raw_indices": {
                    "n1": 0.7 - i * 0.01,
                    "n2": 0.8 - i * 0.02,
                    "n3": 0.75 - i * 0.015,
                },
                "metrics": {
                    "visit_count": 100 - i * 5,
                    "blog_count": 50 - i * 2,
                    "save_count": 200 - i * 10,
                },
            }
            for i in range(1, 21)
        ]
    }


@pytest.fixture
def mock_keyword_params() -> MagicMock:
    """Mock cached keyword parameters."""
    params = MagicMock()
    params.keyword = "강남 맛집"
    params.n2_slope = 0.5
    params.n2_intercept = 10.0
    params.n1_normalized = 0.65
    params.reliability = 0.9
    params.created_at = datetime.now()
    params.updated_at = datetime.now()
    return params


@pytest.fixture
def mock_activity_log() -> dict:
    """Mock activity log data."""
    return {
        "keyword": "강남 맛집",
        "place_id": "place_10",
        "place_name": "테스트 맛집 10",
        "activity_date": str(date.today()),
        "blog_review_added": 2,
        "visit_review_added": 5,
        "save_added": 10,
        "inflow_added": 100,
    }


@pytest.fixture
def mock_saved_keyword() -> dict:
    """Mock saved keyword data."""
    return {
        "id": 1,
        "place_id": "place_10",
        "place_name": "테스트 맛집",
        "keyword": "강남 맛집",
        "last_rank": 10,
        "best_rank": 8,
        "visitor_review_count": 50,
        "blog_review_count": 30,
        "is_active": True,
    }


# ===========================================
# Mock Service Fixtures
# ===========================================

@pytest.fixture
def mock_naver_service():
    """Mock NaverPlaceService."""
    with patch("app.services.naver_place.NaverPlaceService") as mock:
        instance = mock.return_value
        instance.search_places = AsyncMock(return_value=[])
        instance.get_place_rank = AsyncMock(return_value={
            "rank": 10,
            "total_results": 100,
            "target_place": {"name": "테스트 맛집", "rank": 10},
            "competitors": [],
        })
        instance.extract_place_id = MagicMock(return_value="place_10")
        yield instance


@pytest.fixture
def mock_adlog_service():
    """Mock ADLOG API service."""
    with patch("app.services.adlog_proxy.adlog_service") as mock:
        mock.fetch_keyword_analysis = AsyncMock(return_value={"places": []})
        yield mock


# ===========================================
# Test Data Generators
# ===========================================

def generate_places(count: int, start_rank: int = 1) -> list:
    """Generate mock place data for testing."""
    return [
        {
            "place_id": f"place_{i}",
            "name": f"테스트 업체 {i}",
            "rank": start_rank + i - 1,
            "scores": {
                "keyword_score": 70 - i,
                "quality_score": 80 - i * 2,
                "competition_score": 75 - i * 1.5,
            },
            "metrics": {
                "visit_count": 100 - i * 5,
                "blog_count": 50 - i * 2,
                "save_count": 200 - i * 10,
            },
        }
        for i in range(1, count + 1)
    ]


def generate_rank_history(keyword_id: int, days: int = 7) -> list:
    """Generate mock rank history data."""
    from datetime import timedelta

    base_date = datetime.now()
    return [
        {
            "id": i,
            "keyword_id": keyword_id,
            "rank": 10 - (i % 3),  # 순위 변동 시뮬레이션
            "total_results": 100,
            "checked_at": base_date - timedelta(days=days - i),
        }
        for i in range(1, days + 1)
    ]
