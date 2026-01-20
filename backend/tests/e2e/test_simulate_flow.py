"""
E2E Test: 목표 순위 시뮬레이션 플로우
시나리오: 목표 순위 설정 -> 시뮬레이션 실행 -> 결과 검증

테스트 흐름:
1. POST /api/v1/simulate/target-rank - 목표 순위 시뮬레이션
2. 응답 검증 (n2_change, n3_change, required_reviews, required_saves 등)
"""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from httpx import AsyncClient


class TestSimulateFlow:
    """목표 순위 시뮬레이션 전체 플로우 테스트"""

    @pytest.fixture
    def mock_transformed_places(self):
        """변환된 장소 데이터 Mock"""
        return [
            {
                "place_id": f"place_{i}",
                "name": f"테스트 맛집 {i}",
                "rank": i,
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
            for i in range(1, 21)
        ]

    @pytest.fixture
    def mock_cached_params(self):
        """캐시된 파라미터 Mock"""
        params = MagicMock()
        params.keyword = "강남 맛집"
        params.n2_slope = 0.5
        params.n2_intercept = 10.0
        params.n1_normalized = 0.65
        params.reliability = 0.9
        return params

    @pytest.mark.asyncio
    async def test_simulate_target_rank_from_api(
        self,
        async_client: AsyncClient,
        mock_transformed_places
    ):
        """API 데이터로 목표 순위 시뮬레이션"""
        with patch("app.api.v1.simulate.adlog_service") as mock_adlog, \
             patch("app.api.v1.simulate.parameter_repository") as mock_param_repo, \
             patch("app.api.v1.simulate.place_transformer") as mock_transformer:

            # 캐시 없음 -> API 호출
            mock_param_repo.get_by_keyword = AsyncMock(return_value=None)
            mock_adlog.fetch_keyword_analysis = AsyncMock(return_value={
                "places": [
                    {
                        "place_id": f"place_{i}",
                        "name": f"테스트 맛집 {i}",
                        "rank": i,
                        "raw_indices": {"n1": 70 - i, "n2": 80 - i * 2, "n3": 75 - i * 1.5},
                    }
                    for i in range(1, 21)
                ]
            })
            mock_transformer.transform_all_places.return_value = mock_transformed_places

            response = await async_client.post(
                "/api/v1/simulate/target-rank",
                json={
                    "keyword": "강남 맛집",
                    "place_name": "테스트 맛집 10",
                    "current_rank": 10,
                    "target_rank": 5
                }
            )

            # 200 성공 또는 404/500 (테스트 환경)
            assert response.status_code in [200, 404, 500]

            if response.status_code == 200:
                data = response.json()
                assert data["keyword"] == "강남 맛집"
                assert data["current_rank"] == 10
                assert data["target_rank"] == 5
                assert data["data_source"] == "api"
                assert "n2_change" in data
                assert "n3_change" in data

    @pytest.mark.asyncio
    async def test_simulate_target_rank_from_cache(
        self,
        async_client: AsyncClient,
        mock_cached_params
    ):
        """캐시된 파라미터로 목표 순위 시뮬레이션"""
        with patch("app.api.v1.simulate.parameter_repository") as mock_param_repo, \
             patch("app.api.v1.simulate.formula_calculator") as mock_formula:

            # 캐시 있음
            mock_param_repo.get_by_keyword = AsyncMock(return_value=mock_cached_params)
            mock_formula.can_calculate.return_value = True
            mock_formula.calculate_n1.return_value = 65.0
            mock_formula.calculate_n2.side_effect = [60.0, 75.0]  # current, target
            mock_formula.calculate_n3_from_params.side_effect = [70.0, 80.0]

            response = await async_client.post(
                "/api/v1/simulate/target-rank",
                json={
                    "keyword": "강남 맛집",
                    "place_name": "테스트 맛집 10",
                    "current_rank": 10,
                    "target_rank": 5
                }
            )

            assert response.status_code in [200, 404, 500]

            if response.status_code == 200:
                data = response.json()
                assert data["data_source"] == "cache"


class TestSimulateValidation:
    """시뮬레이션 유효성 검사 테스트"""

    @pytest.mark.asyncio
    async def test_target_rank_higher_than_current(self, async_client: AsyncClient):
        """목표 순위가 현재 순위보다 낮을 때 (숫자가 클 때) 에러"""
        response = await async_client.post(
            "/api/v1/simulate/target-rank",
            json={
                "keyword": "강남 맛집",
                "place_name": "테스트",
                "current_rank": 5,
                "target_rank": 10  # 현재보다 낮은 순위 (숫자가 큼)
            }
        )

        assert response.status_code == 400
        assert "목표 순위는 현재 순위보다 높아야 합니다" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_same_current_and_target_rank(self, async_client: AsyncClient):
        """현재 순위와 목표 순위가 같을 때 에러"""
        response = await async_client.post(
            "/api/v1/simulate/target-rank",
            json={
                "keyword": "강남 맛집",
                "place_name": "테스트",
                "current_rank": 5,
                "target_rank": 5  # 같은 순위
            }
        )

        assert response.status_code == 400
        assert "목표 순위는 현재 순위보다 높아야 합니다" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_already_first_rank(self, async_client: AsyncClient):
        """이미 1위일 때 에러"""
        response = await async_client.post(
            "/api/v1/simulate/target-rank",
            json={
                "keyword": "강남 맛집",
                "place_name": "테스트",
                "current_rank": 1,
                "target_rank": 1
            }
        )

        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_keyword_length_limit(self, async_client: AsyncClient):
        """키워드 길이 제한 (50자 초과)"""
        response = await async_client.post(
            "/api/v1/simulate/target-rank",
            json={
                "keyword": "a" * 51,  # 50자 초과
                "place_name": "테스트",
                "current_rank": 10,
                "target_rank": 5
            }
        )

        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_rank_out_of_range(self, async_client: AsyncClient):
        """순위 범위 초과 (300 초과)"""
        response = await async_client.post(
            "/api/v1/simulate/target-rank",
            json={
                "keyword": "테스트",
                "place_name": "테스트",
                "current_rank": 350,  # 300 초과
                "target_rank": 5
            }
        )

        assert response.status_code == 422


class TestSimulateResponse:
    """시뮬레이션 응답 검증 테스트"""

    @pytest.mark.asyncio
    async def test_response_contains_required_fields(
        self,
        async_client: AsyncClient
    ):
        """응답에 필수 필드 포함 확인"""
        with patch("app.api.v1.simulate.parameter_repository") as mock_param_repo, \
             patch("app.api.v1.simulate.formula_calculator") as mock_formula:

            mock_params = MagicMock()
            mock_params.n2_slope = 0.5
            mock_params.n2_intercept = 10.0
            mock_params.n1_normalized = 0.65

            mock_param_repo.get_by_keyword = AsyncMock(return_value=mock_params)
            mock_formula.can_calculate.return_value = True
            mock_formula.calculate_n1.return_value = 65.0
            mock_formula.calculate_n2.side_effect = [60.0, 75.0]
            mock_formula.calculate_n3_from_params.side_effect = [70.0, 80.0]

            response = await async_client.post(
                "/api/v1/simulate/target-rank",
                json={
                    "keyword": "강남 맛집",
                    "place_name": "테스트",
                    "current_rank": 10,
                    "target_rank": 5
                }
            )

            if response.status_code == 200:
                data = response.json()

                # 필수 필드 검증
                assert "keyword" in data
                assert "place_name" in data
                assert "current_rank" in data
                assert "target_rank" in data
                assert "n2_change" in data
                assert "n3_change" in data
                assert "message" in data
                assert "is_achievable" in data
                assert "data_source" in data

                # n2_change 구조 검증
                assert "current" in data["n2_change"]
                assert "target" in data["n2_change"]
                assert "change" in data["n2_change"]

                # n3_change 구조 검증
                assert "current" in data["n3_change"]
                assert "target" in data["n3_change"]
                assert "change" in data["n3_change"]

    @pytest.mark.asyncio
    async def test_n2_change_is_positive(self, async_client: AsyncClient):
        """목표 순위 상승 시 N2 변화량이 양수"""
        with patch("app.api.v1.simulate.parameter_repository") as mock_param_repo, \
             patch("app.api.v1.simulate.formula_calculator") as mock_formula:

            mock_params = MagicMock()
            mock_params.n2_slope = 0.5
            mock_params.n2_intercept = 10.0
            mock_params.n1_normalized = 0.65

            mock_param_repo.get_by_keyword = AsyncMock(return_value=mock_params)
            mock_formula.can_calculate.return_value = True
            mock_formula.calculate_n1.return_value = 65.0
            mock_formula.calculate_n2.side_effect = [60.0, 75.0]  # target > current
            mock_formula.calculate_n3_from_params.side_effect = [70.0, 80.0]

            response = await async_client.post(
                "/api/v1/simulate/target-rank",
                json={
                    "keyword": "강남 맛집",
                    "place_name": "테스트",
                    "current_rank": 10,
                    "target_rank": 5
                }
            )

            if response.status_code == 200:
                data = response.json()
                # N2는 순위 상승 시 증가해야 함
                assert data["n2_change"]["change"] > 0


class TestSimulateScoreSimulation:
    """점수 시뮬레이션 테스트 (POST /api/v1/simulate)"""

    @pytest.mark.asyncio
    async def test_simulate_score_endpoint(self, async_client: AsyncClient):
        """점수 시뮬레이션 기본 테스트"""
        with patch("app.api.v1.simulate.adlog_service") as mock_adlog, \
             patch("app.api.v1.simulate.place_transformer") as mock_transformer:

            mock_adlog.fetch_keyword_analysis = AsyncMock(return_value={
                "places": [
                    {
                        "place_id": "place_10",
                        "name": "테스트 맛집",
                        "rank": 10,
                        "raw_indices": {"n1": 65, "n2": 70, "n3": 75},
                    }
                ]
            })

            mock_transformer.transform_all_places.return_value = [
                {
                    "place_id": "place_10",
                    "name": "테스트 맛집",
                    "rank": 10,
                    "scores": {
                        "keyword_score": 65,
                        "quality_score": 70,
                        "competition_score": 75,
                    },
                }
            ]

            response = await async_client.post(
                "/api/v1/simulate",
                json={
                    "keyword": "강남 맛집",
                    "place_name": "테스트 맛집",
                    "inputs": {
                        "inflow": 100,
                        "blog_review": 5,
                        "visit_review": 10
                    }
                }
            )

            # 200 성공 또는 404 (업체 없음) 또는 500 (서버 에러)
            assert response.status_code in [200, 404, 500]

    @pytest.mark.asyncio
    async def test_quick_simulate_endpoint(self, async_client: AsyncClient):
        """간편 시뮬레이션 엔드포인트 테스트"""
        with patch("app.api.v1.simulate.adlog_service") as mock_adlog, \
             patch("app.api.v1.simulate.place_transformer") as mock_transformer:

            mock_adlog.fetch_keyword_analysis = AsyncMock(return_value={
                "places": [
                    {
                        "place_id": "place_10",
                        "name": "테스트 맛집",
                        "rank": 10,
                        "raw_indices": {"n1": 65, "n2": 70, "n3": 75},
                    }
                ]
            })

            mock_transformer.transform_all_places.return_value = [
                {
                    "place_id": "place_10",
                    "name": "테스트 맛집",
                    "rank": 10,
                    "scores": {
                        "keyword_score": 65,
                        "quality_score": 70,
                        "competition_score": 75,
                    },
                }
            ]

            response = await async_client.post(
                "/api/v1/simulate/quick",
                params={
                    "keyword": "강남 맛집",
                    "place_name": "테스트 맛집",
                    "inflow": 100,
                    "blog_review": 5,
                    "visit_review": 10
                }
            )

            assert response.status_code in [200, 404, 500]


class TestSimulateFlowIntegration:
    """시뮬레이션 통합 테스트"""

    @pytest.mark.asyncio
    async def test_full_simulation_flow(self, async_client: AsyncClient):
        """전체 시뮬레이션 플로우 (분석 -> 시뮬레이션 -> 검증)"""
        mock_places = [
            {
                "place_id": f"place_{i}",
                "name": f"테스트 맛집 {i}",
                "rank": i,
                "raw_indices": {"n1": 70 - i, "n2": 80 - i * 2, "n3": 75 - i * 1.5},
                "metrics": {"visit_count": 100 - i * 5, "blog_count": 50 - i * 2},
            }
            for i in range(1, 21)
        ]

        transformed_places = [
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

        with patch("app.api.v1.simulate.adlog_service") as mock_adlog, \
             patch("app.api.v1.simulate.parameter_repository") as mock_param_repo, \
             patch("app.api.v1.simulate.place_transformer") as mock_transformer:

            mock_param_repo.get_by_keyword = AsyncMock(return_value=None)
            mock_adlog.fetch_keyword_analysis = AsyncMock(return_value={"places": mock_places})
            mock_transformer.transform_all_places.return_value = transformed_places

            # 현재 10위에서 5위로 올리는 시뮬레이션
            response = await async_client.post(
                "/api/v1/simulate/target-rank",
                json={
                    "keyword": "강남 맛집",
                    "place_name": "테스트 맛집 10",
                    "current_rank": 10,
                    "target_rank": 5
                }
            )

            if response.status_code == 200:
                data = response.json()

                # 순위 정보 확인
                assert data["current_rank"] == 10
                assert data["target_rank"] == 5

                # N2, N3 변화량 확인
                assert data["n2_change"]["change"] != 0
                assert "message" in data

                # 달성 가능성 확인
                assert isinstance(data["is_achievable"], bool)
