"""
Test Simulate API
목표 순위 시뮬레이션 API 테스트
"""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from fastapi import HTTPException
from httpx import AsyncClient

from app.api.v1.simulate import (
    simulate_target_rank,
    TargetRankRequest,
    TargetRankResponse,
)


class TestSimulateTargetRank:
    """목표 순위 시뮬레이션 테스트"""

    @pytest.fixture
    def mock_db(self):
        """Mock database session"""
        return AsyncMock()

    @pytest.fixture
    def valid_request(self):
        """Valid simulation request"""
        return TargetRankRequest(
            keyword="강남 맛집",
            place_name="테스트 맛집",
            current_rank=10,
            target_rank=5
        )

    @pytest.fixture
    def mock_adlog_response(self):
        """Mock ADLOG API response"""
        return {
            "places": [
                {
                    "place_id": f"place_{i}",
                    "name": f"맛집 {i}" if i != 5 else "테스트 맛집",
                    "rank": i,
                    "raw_indices": {"n1": 0.7 - i*0.01, "n2": 0.8 - i*0.02, "n3": 0.75 - i*0.015},
                    "metrics": {"visit_count": 100 - i*5, "blog_count": 50 - i*2, "save_count": 200 - i*10},
                }
                for i in range(1, 21)
            ]
        }

    @pytest.mark.asyncio
    async def test_simulate_target_rank_success(self, mock_db, valid_request, mock_adlog_response):
        """성공적인 목표 순위 시뮬레이션 테스트"""
        # Mock parameter_repository
        with patch("app.api.v1.simulate.parameter_repository") as mock_param_repo, \
             patch("app.api.v1.simulate.adlog_service") as mock_adlog, \
             patch("app.api.v1.simulate.place_transformer") as mock_transformer:

            # Setup mocks
            mock_param_repo.get_by_keyword = AsyncMock(return_value=None)
            mock_adlog.fetch_keyword_analysis = AsyncMock(return_value=mock_adlog_response)
            mock_transformer.transform_all_places.return_value = [
                {
                    "place_id": f"place_{i}",
                    "name": f"맛집 {i}" if i != 10 else "테스트 맛집",
                    "rank": i,
                    "scores": {
                        "keyword_score": 70 - i,
                        "quality_score": 80 - i*2,
                        "competition_score": 75 - i*1.5
                    },
                }
                for i in range(1, 21)
            ]

            # Execute
            result = await simulate_target_rank(valid_request, mock_db)

            # Assert
            assert result.keyword == "강남 맛집"
            assert result.place_name == "테스트 맛집"
            assert result.current_rank == 10
            assert result.target_rank == 5
            assert result.n2_change is not None
            assert result.n3_change is not None
            assert result.message is not None
            assert result.data_source == "api"

    @pytest.mark.asyncio
    async def test_simulate_target_rank_invalid_rank_target_higher_than_current(self, mock_db):
        """목표 순위가 현재 순위보다 높을 때 에러 테스트"""
        request = TargetRankRequest(
            keyword="강남 맛집",
            place_name="테스트 맛집",
            current_rank=5,
            target_rank=10  # 현재보다 낮은 순위 (숫자가 큼)
        )

        with pytest.raises(HTTPException) as exc_info:
            await simulate_target_rank(request, mock_db)

        assert exc_info.value.status_code == 400
        assert "목표 순위는 현재 순위보다 높아야 합니다" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_simulate_target_rank_invalid_rank_same(self, mock_db):
        """목표 순위가 현재 순위와 같을 때 에러 테스트"""
        request = TargetRankRequest(
            keyword="강남 맛집",
            place_name="테스트 맛집",
            current_rank=5,
            target_rank=5  # 같은 순위
        )

        with pytest.raises(HTTPException) as exc_info:
            await simulate_target_rank(request, mock_db)

        assert exc_info.value.status_code == 400
        assert "목표 순위는 현재 순위보다 높아야 합니다" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_simulate_target_rank_already_first(self, mock_db):
        """이미 1위일 때 에러 테스트 (target_rank >= current_rank)"""
        request = TargetRankRequest(
            keyword="강남 맛집",
            place_name="테스트 맛집",
            current_rank=1,
            target_rank=1  # 이미 1위
        )

        with pytest.raises(HTTPException) as exc_info:
            await simulate_target_rank(request, mock_db)

        assert exc_info.value.status_code == 400
        # 1위면 target >= current 조건에 걸림
        assert "목표 순위는 현재 순위보다 높아야 합니다" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_simulate_target_rank_cache_hit(self, mock_db, valid_request):
        """캐시 히트 시 테스트"""
        mock_cached_params = MagicMock()
        mock_cached_params.n2_slope = 0.5
        mock_cached_params.n2_intercept = 10.0
        mock_cached_params.n1_normalized = 0.65

        with patch("app.api.v1.simulate.parameter_repository") as mock_param_repo, \
             patch("app.api.v1.simulate.formula_calculator") as mock_formula:

            mock_param_repo.get_by_keyword = AsyncMock(return_value=mock_cached_params)
            mock_formula.can_calculate.return_value = True
            mock_formula.calculate_n1.return_value = 65.0
            mock_formula.calculate_n2.side_effect = [60.0, 75.0]  # current, target

            result = await simulate_target_rank(valid_request, mock_db)

            assert result.data_source == "cache"
            assert result.n2_change.current == 60.0
            assert result.n2_change.target == 75.0

    @pytest.mark.asyncio
    async def test_simulate_target_rank_place_not_found(self, mock_db):
        """업체를 찾지 못했을 때 테스트"""
        request = TargetRankRequest(
            keyword="강남 맛집",
            place_name="존재하지않는맛집",
            current_rank=10,
            target_rank=5
        )

        with patch("app.api.v1.simulate.parameter_repository") as mock_param_repo, \
             patch("app.api.v1.simulate.adlog_service") as mock_adlog, \
             patch("app.api.v1.simulate.place_transformer") as mock_transformer:

            mock_param_repo.get_by_keyword = AsyncMock(return_value=None)
            mock_adlog.fetch_keyword_analysis = AsyncMock(return_value={"places": []})
            mock_transformer.transform_all_places.return_value = []

            with pytest.raises(HTTPException) as exc_info:
                await simulate_target_rank(request, mock_db)

            assert exc_info.value.status_code == 404
            assert "검색 결과가 없습니다" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_simulate_target_rank_api_error(self, mock_db, valid_request):
        """ADLOG API 에러 처리 테스트"""
        from app.services.adlog_proxy import AdlogApiError

        with patch("app.api.v1.simulate.parameter_repository") as mock_param_repo, \
             patch("app.api.v1.simulate.adlog_service") as mock_adlog:

            mock_param_repo.get_by_keyword = AsyncMock(return_value=None)
            mock_adlog.fetch_keyword_analysis = AsyncMock(
                side_effect=AdlogApiError("API connection failed")
            )

            with pytest.raises(HTTPException) as exc_info:
                await simulate_target_rank(valid_request, mock_db)  # valid_request 사용

            assert exc_info.value.status_code == 503


class TestTargetRankResponseModel:
    """TargetRankResponse 모델 테스트"""

    def test_response_model_valid(self):
        """유효한 응답 모델 테스트"""
        from app.api.v1.simulate import ScoreChange

        response = TargetRankResponse(
            keyword="강남 맛집",
            place_name="테스트 맛집",
            current_rank=10,
            target_rank=5,
            n2_change=ScoreChange(current=60.0, target=75.0, change=15.0),
            n3_change=ScoreChange(current=55.0, target=70.0, change=15.0),
            message="5위 달성을 위해 N2를 15점 높여야 합니다.",
            is_achievable=True,
            data_source="api"
        )

        assert response.keyword == "강남 맛집"
        assert response.target_rank == 5
        assert response.n2_change.change == 15.0
        assert response.is_achievable is True


class TestTargetRankRequestValidation:
    """TargetRankRequest 유효성 검사 테스트"""

    def test_valid_request(self):
        """유효한 요청 테스트"""
        request = TargetRankRequest(
            keyword="강남 맛집",
            place_name="테스트 맛집",
            current_rank=10,
            target_rank=1
        )
        assert request.current_rank == 10
        assert request.target_rank == 1

    def test_request_rank_boundaries(self):
        """순위 경계값 테스트"""
        # 최소값
        request = TargetRankRequest(
            keyword="테스트",
            place_name="테스트",
            current_rank=2,
            target_rank=1
        )
        assert request.target_rank == 1

        # 최대값
        request = TargetRankRequest(
            keyword="테스트",
            place_name="테스트",
            current_rank=300,
            target_rank=299
        )
        assert request.current_rank == 300

    def test_request_keyword_length(self):
        """키워드 길이 제한 테스트"""
        # 너무 긴 키워드는 pydantic에서 자동 validation
        with pytest.raises(ValueError):
            TargetRankRequest(
                keyword="a" * 51,  # 50자 제한 초과
                place_name="테스트",
                current_rank=10,
                target_rank=5
            )
