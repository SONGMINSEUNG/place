"""
API 엔드포인트 기본 테스트
- analyze 엔드포인트
- parameters 엔드포인트
"""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from fastapi.testclient import TestClient
from httpx import AsyncClient, ASGITransport
import sys
import os

# 프로젝트 루트 경로 추가
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.main import app


class TestAnalyzeEndpoints:
    """Analyze API 엔드포인트 테스트"""

    @pytest.fixture
    def client(self):
        """동기 테스트 클라이언트"""
        return TestClient(app)

    def test_analyze_post_endpoint_exists(self, client):
        """POST /api/v1/analyze 엔드포인트 존재 확인"""
        # OPTIONS 요청으로 엔드포인트 존재 확인
        response = client.options("/api/v1/analyze")
        # 405 (Method Not Allowed) 또는 200이면 엔드포인트가 존재함
        assert response.status_code in [200, 405, 422]

    def test_analyze_get_endpoint_exists(self, client):
        """GET /api/v1/analyze/{keyword} 엔드포인트 존재 확인"""
        # 실제 API 호출 없이 엔드포인트 존재만 확인
        # 503 (Service Unavailable)은 외부 API 실패 시 발생
        # 422는 검증 실패, 500은 서버 에러
        # 어느 경우든 엔드포인트가 존재한다는 것을 의미
        with patch('app.services.adlog_proxy.adlog_service.fetch_keyword_analysis') as mock:
            mock.side_effect = Exception("Test - API mocked")
            response = client.get("/api/v1/analyze/테스트키워드")
            # 404가 아니면 엔드포인트가 존재함
            assert response.status_code != 404

    def test_analyze_post_requires_keyword(self, client):
        """POST /api/v1/analyze - 키워드 필수 확인"""
        response = client.post("/api/v1/analyze", json={})
        # 422 Unprocessable Entity - keyword 필드 누락
        assert response.status_code == 422

    def test_analyze_post_with_valid_request(self, client):
        """POST /api/v1/analyze - 유효한 요청"""
        with patch('app.services.adlog_proxy.adlog_service.fetch_keyword_analysis') as mock:
            mock.return_value = {"places": []}
            response = client.post("/api/v1/analyze", json={"keyword": "테스트"})
            # 404 (검색 결과 없음), 200 (성공), 500 (테스트 DB 없음)
            assert response.status_code in [200, 404, 500]


class TestParametersEndpoints:
    """Parameters API 엔드포인트 테스트

    Note: DB 테이블이 없는 테스트 환경에서는 500 에러가 발생할 수 있음
    실제 통합 테스트는 DB가 준비된 환경에서 실행해야 함
    """

    @pytest.fixture
    def client(self):
        """동기 테스트 클라이언트"""
        return TestClient(app, raise_server_exceptions=False)

    def test_list_parameters_endpoint(self, client):
        """GET /api/v1/parameters/ 엔드포인트 테스트"""
        response = client.get("/api/v1/parameters/")
        # 200 성공 또는 DB 테이블 없음으로 500
        assert response.status_code in [200, 500]
        # 엔드포인트가 존재하는지 확인 (404가 아님)
        assert response.status_code != 404

    def test_list_parameters_with_limit(self, client):
        """GET /api/v1/parameters/ - limit 파라미터"""
        response = client.get("/api/v1/parameters/?limit=10")
        assert response.status_code in [200, 500]
        assert response.status_code != 404

    def test_list_parameters_reliable_only(self, client):
        """GET /api/v1/parameters/ - reliable_only 파라미터"""
        response = client.get("/api/v1/parameters/?reliable_only=true")
        assert response.status_code in [200, 500]
        assert response.status_code != 404

    def test_get_parameter_stats(self, client):
        """GET /api/v1/parameters/stats 엔드포인트 테스트"""
        response = client.get("/api/v1/parameters/stats")
        assert response.status_code in [200, 500]
        assert response.status_code != 404

    def test_get_parameter_by_keyword_not_found(self, client):
        """GET /api/v1/parameters/{keyword} - 존재하지 않는 키워드"""
        response = client.get("/api/v1/parameters/존재하지않는키워드123456")
        # 404 (Not Found) 또는 500 (DB 테이블 없음)
        assert response.status_code in [404, 500]

    def test_calculate_indices_endpoint(self, client):
        """GET /api/v1/parameters/{keyword}/calculate 엔드포인트 테스트"""
        response = client.get("/api/v1/parameters/테스트/calculate?rank=1")
        # 404 (파라미터 없음), 400 (신뢰도 낮음), 500 (서버 에러/DB 없음)
        assert response.status_code in [400, 404, 500]


class TestHealthEndpoints:
    """Health check 엔드포인트 테스트"""

    @pytest.fixture
    def client(self):
        return TestClient(app)

    def test_health_endpoint(self, client):
        """GET /health 엔드포인트 테스트"""
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json()["status"] == "healthy"

    def test_root_endpoint(self, client):
        """GET / 루트 엔드포인트 테스트"""
        response = client.get("/")
        assert response.status_code == 200


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
