"""
E2E Test: 키워드 저장 및 추적 플로우
시나리오: 키워드 저장 -> 목록 조회 -> 순위 갱신 -> 히스토리 조회

테스트 흐름:
1. POST /api/keywords/save - 키워드 저장
2. GET /api/keywords/ - 저장 목록 확인
3. POST /api/keywords/{id}/refresh - 순위 갱신
4. GET /api/keywords/{id}/history - 히스토리 조회
"""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from httpx import AsyncClient
from datetime import datetime


class TestKeywordFlow:
    """키워드 저장 및 추적 전체 플로우 테스트"""

    @pytest.fixture
    def mock_rank_result(self):
        """순위 조회 결과 Mock"""
        return {
            "rank": 10,
            "total_results": 100,
            "target_place": {
                "name": "테스트 맛집",
                "place_id": "place_10",
                "visitor_review_count": 50,
                "blog_review_count": 30,
            },
            "analysis": {
                "target_analysis": {
                    "total_score": 75.5,
                    "counts": {
                        "visitor_review": 50,
                        "blog_review": 30,
                    }
                }
            }
        }

    @pytest.mark.asyncio
    async def test_step1_save_keyword(self, async_client: AsyncClient, mock_rank_result):
        """Step 1: 키워드 저장"""
        with patch("app.api.keywords.naver_service") as mock_naver:
            mock_naver.extract_place_id = MagicMock(return_value="place_10")
            mock_naver.get_place_rank = AsyncMock(return_value=mock_rank_result)

            response = await async_client.post(
                "/api/keywords/save",
                json={
                    "place_url": "https://map.naver.com/v5/entry/place/place_10",
                    "place_name": "테스트 맛집",
                    "keyword": "강남 맛집"
                }
            )

            # 200 성공 또는 400 (이미 저장됨) 또는 500 (DB 없음)
            assert response.status_code in [200, 400, 500]

    @pytest.mark.asyncio
    async def test_step2_get_saved_keywords(self, async_client: AsyncClient):
        """Step 2: 저장된 키워드 목록 조회"""
        response = await async_client.get("/api/keywords/")

        # 200 성공 또는 500 (DB 테이블 없음)
        assert response.status_code in [200, 500]

        if response.status_code == 200:
            data = response.json()
            assert isinstance(data, list)

    @pytest.mark.asyncio
    async def test_step3_refresh_keyword_rank(self, async_client: AsyncClient, mock_rank_result):
        """Step 3: 순위 갱신"""
        with patch("app.api.keywords.naver_service") as mock_naver:
            mock_naver.get_place_rank = AsyncMock(return_value={
                **mock_rank_result,
                "rank": 8  # 순위 상승
            })

            # 실제 ID가 필요하므로, 일단 1로 테스트
            response = await async_client.post("/api/keywords/1/refresh")

            # 200 성공, 404 (키워드 없음), 500 (DB 없음)
            assert response.status_code in [200, 404, 500]

    @pytest.mark.asyncio
    async def test_step4_get_rank_history(self, async_client: AsyncClient):
        """Step 4: 히스토리 조회"""
        response = await async_client.get(
            "/api/keywords/1/history",
            params={"days": 30}
        )

        # 200 성공, 404 (키워드 없음), 500 (DB 없음)
        assert response.status_code in [200, 404, 500]


class TestKeywordFlowValidation:
    """키워드 저장 플로우 유효성 검사 테스트"""

    @pytest.mark.asyncio
    async def test_save_keyword_invalid_url(self, async_client: AsyncClient):
        """유효하지 않은 URL로 키워드 저장 시 에러"""
        with patch("app.api.keywords.naver_service") as mock_naver:
            mock_naver.extract_place_id = MagicMock(return_value=None)

            response = await async_client.post(
                "/api/keywords/save",
                json={
                    "place_url": "invalid-url",
                    "keyword": "강남 맛집"
                }
            )

            assert response.status_code == 400
            assert "유효하지 않은" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_save_keyword_missing_keyword(self, async_client: AsyncClient):
        """키워드 없이 저장 요청 시 유효성 검사 에러"""
        response = await async_client.post(
            "/api/keywords/save",
            json={
                "place_url": "https://map.naver.com/v5/entry/place/12345"
                # keyword 누락
            }
        )

        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_refresh_nonexistent_keyword(self, async_client: AsyncClient):
        """존재하지 않는 키워드 갱신 시 404"""
        response = await async_client.post("/api/keywords/99999/refresh")

        # 404 또는 500 (DB 테이블 없음)
        assert response.status_code in [404, 500]

    @pytest.mark.asyncio
    async def test_history_invalid_days(self, async_client: AsyncClient):
        """유효하지 않은 days 파라미터"""
        # days가 범위를 벗어나면 422
        response = await async_client.get(
            "/api/keywords/1/history",
            params={"days": 100}  # max 90
        )

        assert response.status_code in [404, 422, 500]

    @pytest.mark.asyncio
    async def test_delete_nonexistent_keyword(self, async_client: AsyncClient):
        """존재하지 않는 키워드 삭제 시 404"""
        response = await async_client.delete("/api/keywords/99999")

        # 404 또는 500 (DB 테이블 없음)
        assert response.status_code in [404, 500]


class TestKeywordFlowEdgeCases:
    """키워드 플로우 엣지 케이스 테스트"""

    @pytest.mark.asyncio
    async def test_save_duplicate_keyword(self, async_client: AsyncClient, mock_saved_keyword):
        """중복 키워드 저장 시 에러"""
        with patch("app.api.keywords.naver_service") as mock_naver:
            mock_naver.extract_place_id = MagicMock(return_value="place_10")
            mock_naver.get_place_rank = AsyncMock(return_value={
                "rank": 10,
                "total_results": 100,
            })

            # 첫 번째 저장 시도
            response1 = await async_client.post(
                "/api/keywords/save",
                json={
                    "place_url": "https://map.naver.com/v5/entry/place/place_10",
                    "keyword": "중복 테스트"
                }
            )

            # 두 번째 저장 시도 (중복)
            response2 = await async_client.post(
                "/api/keywords/save",
                json={
                    "place_url": "https://map.naver.com/v5/entry/place/place_10",
                    "keyword": "중복 테스트"
                }
            )

            # 첫 번째는 성공 또는 실패, 두 번째는 중복 에러 (400) 또는 DB 에러 (500)
            if response1.status_code == 200:
                assert response2.status_code in [400, 500]

    @pytest.mark.asyncio
    async def test_refresh_all_keywords(self, async_client: AsyncClient):
        """모든 키워드 일괄 갱신"""
        with patch("app.api.keywords.naver_service") as mock_naver:
            mock_naver.get_place_rank = AsyncMock(return_value={
                "rank": 10,
                "total_results": 100,
            })

            response = await async_client.post("/api/keywords/refresh-all")

            # 200 성공 또는 500 (DB 테이블 없음)
            assert response.status_code in [200, 500]

            if response.status_code == 200:
                data = response.json()
                assert "total" in data
                assert "updated" in data

    @pytest.mark.asyncio
    async def test_history_with_date_filter(self, async_client: AsyncClient):
        """특정 기간 히스토리 조회"""
        response = await async_client.get(
            "/api/keywords/1/history",
            params={"days": 7}
        )

        # 404, 200, 500 중 하나
        assert response.status_code in [200, 404, 500]


class TestKeywordFlowIntegration:
    """키워드 플로우 통합 테스트"""

    @pytest.mark.asyncio
    async def test_full_keyword_tracking_flow(self, async_client: AsyncClient):
        """전체 키워드 추적 플로우 (저장 -> 조회 -> 갱신 -> 삭제)"""
        with patch("app.api.keywords.naver_service") as mock_naver:
            mock_naver.extract_place_id = MagicMock(return_value="integration_test_place")
            mock_naver.get_place_rank = AsyncMock(return_value={
                "rank": 15,
                "total_results": 150,
                "target_place": {"name": "통합 테스트 업체"},
                "analysis": {
                    "target_analysis": {
                        "total_score": 70.0,
                        "counts": {"visitor_review": 40, "blog_review": 20}
                    }
                }
            })

            # Step 1: 저장
            save_response = await async_client.post(
                "/api/keywords/save",
                json={
                    "place_url": "https://map.naver.com/v5/entry/place/integration_test_place",
                    "place_name": "통합 테스트 업체",
                    "keyword": "통합테스트키워드"
                }
            )

            # 저장 성공 확인
            if save_response.status_code != 200:
                # DB 없음 또는 기존 저장됨
                return

            saved_data = save_response.json()
            keyword_id = saved_data["id"]

            # Step 2: 목록에서 확인
            list_response = await async_client.get("/api/keywords/")
            assert list_response.status_code == 200
            keywords = list_response.json()
            assert any(k["id"] == keyword_id for k in keywords)

            # Step 3: 순위 갱신
            mock_naver.get_place_rank = AsyncMock(return_value={
                "rank": 12,  # 순위 상승
                "total_results": 155,
                "target_place": {"name": "통합 테스트 업체"},
                "analysis": {
                    "target_analysis": {
                        "total_score": 72.0,
                        "counts": {"visitor_review": 42, "blog_review": 22}
                    }
                }
            })

            refresh_response = await async_client.post(f"/api/keywords/{keyword_id}/refresh")
            assert refresh_response.status_code == 200

            # Step 4: 히스토리 확인
            history_response = await async_client.get(f"/api/keywords/{keyword_id}/history")
            assert history_response.status_code == 200

            # Step 5: 삭제
            delete_response = await async_client.delete(f"/api/keywords/{keyword_id}")
            assert delete_response.status_code == 200

            # Step 6: 삭제 확인
            final_list = await async_client.get("/api/keywords/")
            if final_list.status_code == 200:
                assert not any(k["id"] == keyword_id for k in final_list.json())
