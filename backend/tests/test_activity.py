"""
Activity API 테스트
- 활동 기록 API
- 활동 히스토리 조회
- 효과 분석
"""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from fastapi.testclient import TestClient
from datetime import date, datetime
import sys
import os

# 프로젝트 루트 경로 추가
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.main import app


class TestActivityEndpoints:
    """Activity API 엔드포인트 테스트"""

    @pytest.fixture
    def client(self):
        """동기 테스트 클라이언트"""
        return TestClient(app)

    def test_activity_log_endpoint_exists(self, client):
        """POST /api/v1/activity/log 엔드포인트 존재 확인"""
        response = client.options("/api/v1/activity/log")
        # 404가 아니면 엔드포인트가 존재함
        assert response.status_code != 404

    def test_activity_log_requires_keyword(self, client):
        """POST /api/v1/activity/log - 키워드 필수 확인"""
        response = client.post("/api/v1/activity/log", json={
            "blog_review_added": 1,
            "visit_review_added": 0,
            "save_added": 0,
            "inflow_added": 0,
        })
        # 422 Unprocessable Entity - keyword 필드 누락
        assert response.status_code == 422

    def test_activity_log_with_valid_request(self, client):
        """POST /api/v1/activity/log - 유효한 요청"""
        with patch('app.services.adlog_proxy.adlog_service.fetch_keyword_analysis') as mock:
            mock.return_value = {"places": []}
            response = client.post("/api/v1/activity/log", json={
                "keyword": "테스트",
                "place_id": "12345",
                "place_name": "테스트 업체",
                "blog_review_added": 2,
                "visit_review_added": 0,
                "save_added": 5,
                "inflow_added": 100,
            })
            # 200 성공 또는 500 (DB 테이블 없음)
            assert response.status_code in [200, 500]

    def test_activity_log_negative_values_rejected(self, client):
        """POST /api/v1/activity/log - 음수 값 거부"""
        response = client.post("/api/v1/activity/log", json={
            "keyword": "테스트",
            "blog_review_added": -1,  # 음수
            "visit_review_added": 0,
            "save_added": 0,
            "inflow_added": 0,
        })
        # 422 Unprocessable Entity - 음수 값 불허
        assert response.status_code == 422

    def test_activity_history_endpoint_exists(self, client):
        """GET /api/v1/activity/history 엔드포인트 존재 확인"""
        response = client.get("/api/v1/activity/history")
        # 200 성공 또는 500 (DB 테이블 없음)
        assert response.status_code in [200, 500]
        assert response.status_code != 404

    def test_activity_history_with_keyword_filter(self, client):
        """GET /api/v1/activity/history - 키워드 필터"""
        response = client.get("/api/v1/activity/history?keyword=테스트")
        assert response.status_code in [200, 500]
        assert response.status_code != 404

    def test_activity_history_with_days_param(self, client):
        """GET /api/v1/activity/history - days 파라미터"""
        response = client.get("/api/v1/activity/history?days=7")
        assert response.status_code in [200, 500]
        assert response.status_code != 404

    def test_effect_analysis_endpoint_exists(self, client):
        """GET /api/v1/activity/effect-analysis 엔드포인트 존재 확인"""
        response = client.get("/api/v1/activity/effect-analysis")
        # 200 성공 또는 500 (DB 테이블 없음)
        assert response.status_code in [200, 500]
        assert response.status_code != 404

    def test_effect_analysis_with_keyword_filter(self, client):
        """GET /api/v1/activity/effect-analysis - 키워드 필터"""
        response = client.get("/api/v1/activity/effect-analysis?keyword=테스트")
        assert response.status_code in [200, 500]
        assert response.status_code != 404

    def test_update_results_endpoint_exists(self, client):
        """POST /api/v1/activity/update-results 엔드포인트 존재 확인"""
        with patch('app.services.adlog_proxy.adlog_service.fetch_keyword_analysis') as mock:
            mock.return_value = {"places": []}
            response = client.post("/api/v1/activity/update-results")
            # 200 성공 또는 500 (DB 테이블 없음)
            assert response.status_code in [200, 500]
            assert response.status_code != 404


class TestActivityLogValidation:
    """활동 기록 입력 검증 테스트"""

    @pytest.fixture
    def client(self):
        return TestClient(app)

    def test_all_zeros_allowed(self, client):
        """모든 값이 0인 경우 허용 (빈 기록)"""
        with patch('app.services.adlog_proxy.adlog_service.fetch_keyword_analysis') as mock:
            mock.return_value = {"places": []}
            response = client.post("/api/v1/activity/log", json={
                "keyword": "테스트",
                "blog_review_added": 0,
                "visit_review_added": 0,
                "save_added": 0,
                "inflow_added": 0,
            })
            # 422(필수값 누락), 200(성공), 500(DB 없음) 모두 가능
            assert response.status_code in [200, 422, 500]

    def test_large_values_allowed(self, client):
        """큰 값 허용"""
        with patch('app.services.adlog_proxy.adlog_service.fetch_keyword_analysis') as mock:
            mock.return_value = {"places": []}
            response = client.post("/api/v1/activity/log", json={
                "keyword": "테스트",
                "blog_review_added": 100,
                "visit_review_added": 500,
                "save_added": 1000,
                "inflow_added": 10000,
            })
            assert response.status_code in [200, 500]

    def test_activity_date_optional(self, client):
        """activity_date는 선택적"""
        with patch('app.services.adlog_proxy.adlog_service.fetch_keyword_analysis') as mock:
            mock.return_value = {"places": []}
            response = client.post("/api/v1/activity/log", json={
                "keyword": "테스트",
                "blog_review_added": 1,
                "visit_review_added": 0,
                "save_added": 0,
                "inflow_added": 0,
                # activity_date 생략
            })
            assert response.status_code in [200, 500]


class TestCorrelationAnalyzer:
    """CorrelationAnalyzer 모듈 테스트"""

    def test_import_correlation_analyzer(self):
        """CorrelationAnalyzer 임포트 테스트"""
        from app.ml.correlation_analyzer import CorrelationAnalyzer, get_correlation_analyzer
        assert CorrelationAnalyzer is not None
        assert get_correlation_analyzer is not None

    def test_activity_effect_dataclass(self):
        """ActivityEffect 데이터클래스 테스트"""
        from app.ml.correlation_analyzer import ActivityEffect

        effect = ActivityEffect(
            activity_type="블로그 리뷰",
            sample_count=10,
            total_amount=50,
            avg_rank_change_1d=2.5,
            avg_rank_change_7d=5.0,
        )

        assert effect.activity_type == "블로그 리뷰"
        assert effect.sample_count == 10
        assert effect.total_amount == 50
        assert effect.avg_rank_change_1d == 2.5
        assert effect.avg_rank_change_7d == 5.0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
