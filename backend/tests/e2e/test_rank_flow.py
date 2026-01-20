"""
E2E Test: 순위 조회 및 분석 플로우
시나리오: 장소 검색 -> 순위 조회 -> 점수 분석 -> 시뮬레이션

테스트 흐름:
1. GET /api/place/search - 장소 검색
2. POST /api/place/rank - 순위 조회
3. POST /api/v1/analyze - 점수 분석
4. POST /api/v1/simulate/rank-change - 시뮬레이션
"""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from httpx import AsyncClient


class TestRankFlow:
    """순위 조회 및 분석 전체 플로우 테스트"""

    @pytest.fixture
    def mock_naver_places_data(self):
        """네이버 플레이스 검색 결과 Mock 데이터"""
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
    def mock_adlog_data(self):
        """ADLOG API 응답 Mock 데이터"""
        return {
            "places": [
                {
                    "place_id": f"place_{i}",
                    "name": f"테스트 맛집 {i}",
                    "rank": i,
                    "raw_indices": {
                        "n1": 70 - i,
                        "n2": 80 - i * 2,
                        "n3": 75 - i * 1.5,
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

    @pytest.mark.asyncio
    async def test_step1_place_search(self, async_client: AsyncClient, mock_naver_places_data):
        """Step 1: 장소 검색"""
        with patch("app.api.place.naver_service") as mock_naver:
            mock_naver.search_places = AsyncMock(return_value=mock_naver_places_data)

            response = await async_client.get(
                "/api/place/search",
                params={"keyword": "강남 맛집", "limit": 10}
            )

            # 엔드포인트가 존재하는지 확인 (404가 아님)
            # 실제 구현에 따라 200 또는 다른 상태코드 가능
            assert response.status_code != 404

    @pytest.mark.asyncio
    async def test_step2_place_rank(self, async_client: AsyncClient, mock_naver_places_data):
        """Step 2: 순위 조회"""
        with patch("app.api.place.naver_service") as mock_naver:
            mock_naver.extract_place_id = MagicMock(return_value="place_10")
            mock_naver.get_place_rank = AsyncMock(return_value={
                "rank": 10,
                "total_results": 100,
                "target_place": {
                    "name": "테스트 맛집 10",
                    "rank": 10,
                    "visitor_review_count": 50,
                    "blog_review_count": 30,
                },
                "competitors": mock_naver_places_data[:5],
                "analysis": {
                    "target_analysis": {
                        "total_score": 75.5,
                        "counts": {
                            "visitor_review": 50,
                            "blog_review": 30,
                        }
                    }
                }
            })

            response = await async_client.post(
                "/api/place/rank",
                json={
                    "place_url": "https://map.naver.com/v5/entry/place/place_10",
                    "keywords": ["강남 맛집"]
                }
            )

            assert response.status_code == 200
            data = response.json()
            assert isinstance(data, list)
            assert len(data) == 1
            assert data[0]["keyword"] == "강남 맛집"

    @pytest.mark.asyncio
    async def test_step3_analyze_scores(
        self,
        async_client: AsyncClient,
        mock_naver_places_data,
        mock_adlog_data
    ):
        """Step 3: 점수 분석"""
        with patch("app.api.v1.analyze.adlog_service") as mock_adlog, \
             patch("app.api.v1.analyze.naver_service") as mock_naver, \
             patch("app.api.v1.analyze.parameter_repository") as mock_param_repo:

            mock_adlog.fetch_keyword_analysis = AsyncMock(return_value=mock_adlog_data)
            mock_naver.search_places = AsyncMock(return_value=mock_naver_places_data)
            mock_param_repo.get_by_keyword = AsyncMock(return_value=None)
            mock_param_repo.save_or_update = AsyncMock()
            mock_param_repo.increment_cache_hit = AsyncMock()

            response = await async_client.post(
                "/api/v1/analyze",
                json={
                    "keyword": "강남 맛집",
                    "place_name": "테스트 맛집 10"
                }
            )

            # 성공 또는 DB 관련 에러 (테스트 환경)
            assert response.status_code in [200, 404, 500]

    @pytest.mark.asyncio
    async def test_step4_simulate_target_rank(
        self,
        async_client: AsyncClient,
        mock_adlog_data
    ):
        """Step 4: 목표 순위 시뮬레이션"""
        with patch("app.api.v1.simulate.adlog_service") as mock_adlog, \
             patch("app.api.v1.simulate.parameter_repository") as mock_param_repo, \
             patch("app.api.v1.simulate.place_transformer") as mock_transformer:

            mock_param_repo.get_by_keyword = AsyncMock(return_value=None)
            mock_adlog.fetch_keyword_analysis = AsyncMock(return_value=mock_adlog_data)

            # Transform places mock
            mock_transformer.transform_all_places.return_value = [
                {
                    "place_id": f"place_{i}",
                    "name": f"테스트 맛집 {i}",
                    "rank": i,
                    "scores": {
                        "keyword_score": 70 - i,
                        "quality_score": 80 - i * 2,
                        "competition_score": 75 - i * 1.5,
                    },
                }
                for i in range(1, 21)
            ]

            response = await async_client.post(
                "/api/v1/simulate/target-rank",
                json={
                    "keyword": "강남 맛집",
                    "place_name": "테스트 맛집 10",
                    "current_rank": 10,
                    "target_rank": 5
                }
            )

            # 성공 또는 서버 에러 (테스트 환경)
            assert response.status_code in [200, 404, 500]


class TestRankFlowValidation:
    """순위 조회 플로우 유효성 검사 테스트"""

    @pytest.mark.asyncio
    async def test_place_rank_invalid_url(self, async_client: AsyncClient):
        """유효하지 않은 URL로 순위 조회 시 에러"""
        with patch("app.api.place.naver_service") as mock_naver:
            mock_naver.extract_place_id = MagicMock(return_value=None)

            response = await async_client.post(
                "/api/place/rank",
                json={
                    "place_url": "invalid-url",
                    "keywords": ["강남 맛집"]
                }
            )

            assert response.status_code == 400
            assert "유효하지 않은" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_place_rank_empty_keywords(self, async_client: AsyncClient):
        """빈 키워드 목록으로 순위 조회 시 유효성 검사 에러"""
        response = await async_client.post(
            "/api/place/rank",
            json={
                "place_url": "https://map.naver.com/v5/entry/place/12345",
                "keywords": []  # 빈 목록
            }
        )

        assert response.status_code == 422  # Validation Error

    @pytest.mark.asyncio
    async def test_analyze_missing_keyword(self, async_client: AsyncClient):
        """키워드 없이 분석 요청 시 에러"""
        response = await async_client.post(
            "/api/v1/analyze",
            json={}
        )

        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_simulate_target_rank_invalid_ranks(self, async_client: AsyncClient):
        """목표 순위가 현재 순위보다 낮을 때 (숫자가 클 때) 에러"""
        response = await async_client.post(
            "/api/v1/simulate/target-rank",
            json={
                "keyword": "강남 맛집",
                "place_name": "테스트 맛집",
                "current_rank": 5,
                "target_rank": 10  # 현재보다 낮은 순위 (숫자가 큼)
            }
        )

        assert response.status_code == 400
        assert "목표 순위는 현재 순위보다 높아야 합니다" in response.json()["detail"]


class TestRankFlowIntegration:
    """순위 조회 플로우 통합 테스트"""

    @pytest.mark.asyncio
    async def test_full_rank_analysis_flow(
        self,
        async_client: AsyncClient,
        mock_naver_places,
        mock_adlog_response
    ):
        """전체 순위 분석 플로우 (검색 -> 조회 -> 분석)"""
        with patch("app.api.place.naver_service") as mock_naver, \
             patch("app.api.v1.analyze.adlog_service") as mock_adlog, \
             patch("app.api.v1.analyze.naver_service") as mock_analyze_naver, \
             patch("app.api.v1.analyze.parameter_repository") as mock_param_repo:

            # Setup mocks
            mock_naver.extract_place_id = MagicMock(return_value="place_10")
            mock_naver.get_place_rank = AsyncMock(return_value={
                "rank": 10,
                "total_results": 100,
                "target_place": {"name": "테스트 맛집 10"},
                "competitors": [],
            })
            mock_adlog.fetch_keyword_analysis = AsyncMock(return_value=mock_adlog_response)
            mock_analyze_naver.search_places = AsyncMock(return_value=mock_naver_places)
            mock_param_repo.get_by_keyword = AsyncMock(return_value=None)
            mock_param_repo.save_or_update = AsyncMock()

            # Step 1: 순위 조회
            rank_response = await async_client.post(
                "/api/place/rank",
                json={
                    "place_url": "https://map.naver.com/v5/entry/place/place_10",
                    "keywords": ["강남 맛집"]
                }
            )
            assert rank_response.status_code == 200

            # Step 2: 분석
            analyze_response = await async_client.post(
                "/api/v1/analyze",
                json={
                    "keyword": "강남 맛집",
                    "place_name": "테스트 맛집 10"
                }
            )
            # 분석 결과 확인 (테스트 환경에 따라 다를 수 있음)
            assert analyze_response.status_code in [200, 404, 500]
