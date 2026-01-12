"""
Analyze API
키워드 분석 엔드포인트
"""
from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional
from app.models.schemas import (
    AnalyzeRequest,
    AnalyzeResponse,
    PlaceResponse,
    ScoresResponse,
    MetricsResponse,
    ChangesResponse,
    ComparisonResponse,
    CompetitorResponse,
    RecommendationItem,
)
from app.models.place import UserInputData
from app.services.adlog_proxy import adlog_service, AdlogApiError
from app.services.score_converter import score_converter, place_transformer
from app.ml.predictor import predictor
from app.core.database import get_db
import logging

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/analyze", response_model=AnalyzeResponse)
async def analyze_keyword(
    request: AnalyzeRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    키워드 분석 API

    - keyword: 검색 키워드 (필수)
    - place_name: 업체명 (선택) - 지정 시 해당 업체 하이라이트
    - inflow: 오늘 유입수 (선택)
    - reservation: 오늘 예약수 (선택)
    """
    try:
        # 1. ADLOG API 호출
        raw_data = await adlog_service.fetch_keyword_analysis(request.keyword)
        places = raw_data.get("places", [])

        if not places:
            raise HTTPException(
                status_code=404,
                detail="검색 결과가 없습니다."
            )

        # 2. 점수 변환
        transformed_places = place_transformer.transform_all_places(places)

        # 3. 내 업체 찾기
        my_place = None
        my_place_data = None
        my_place_raw = None  # 원본 데이터 (N1, N2, N3 저장용)
        if request.place_name:
            for idx, place in enumerate(transformed_places):
                if request.place_name.lower() in place["name"].lower():
                    my_place_data = place
                    my_place = PlaceResponse(
                        place_id=place["place_id"],
                        name=place["name"],
                        rank=place["rank"],
                        scores=ScoresResponse(**place["scores"]),
                        metrics=MetricsResponse(**place["metrics"]),
                        changes=ChangesResponse(**place["changes"]),
                    )
                    # 원본 데이터에서 raw_indices 찾기
                    for raw_place in places:
                        if raw_place.get("place_id") == place["place_id"]:
                            my_place_raw = raw_place
                            break
                    break

        # 3.1 유입수/예약수가 있으면 사용자 데이터 저장
        if my_place_data and (request.inflow is not None or request.reservation is not None):
            try:
                raw_indices = my_place_raw.get("raw_indices", {}) if my_place_raw else {}
                metrics = my_place_raw.get("metrics", {}) if my_place_raw else {}

                user_data = UserInputData(
                    keyword=request.keyword,
                    place_id=my_place_data["place_id"],
                    place_name=my_place_data["name"],
                    inflow=request.inflow or 0,
                    reservation=request.reservation or 0,
                    n1=raw_indices.get("n1"),
                    n2=raw_indices.get("n2"),
                    n3=raw_indices.get("n3"),
                    rank=my_place_data["rank"],
                    visitor_review_count=metrics.get("visit_count", 0),
                    blog_review_count=metrics.get("blog_count", 0),
                    save_count=metrics.get("save_count", 0),
                )
                db.add(user_data)
                await db.commit()
                logger.info(f"Saved user input data: keyword={request.keyword}, place={my_place_data['name']}, inflow={request.inflow}, reservation={request.reservation}")
            except Exception as e:
                logger.error(f"Failed to save user input data: {str(e)}")
                # 저장 실패해도 분석 결과는 반환

        # 4. 1위 비교 분석
        comparison = None
        rank_1_place = None
        for place in transformed_places:
            if place["rank"] == 1:
                rank_1_place = place
                break

        if my_place_data and rank_1_place:
            my_score = my_place_data["scores"]["quality_score"]
            rank_1_score = rank_1_place["scores"]["quality_score"]
            comparison = ComparisonResponse(
                rank_1_gap=round(rank_1_score - my_score, 4),
                rank_1_score=rank_1_score,
            )

        # 5. 마케팅 제언 생성
        recommendations = []
        if my_place_data:
            current_score = my_place_data["scores"]["quality_score"]
            current_n1 = my_place_data["scores"]["keyword_score"]  # N1 값 추가
            target_score = rank_1_place["scores"]["quality_score"] if rank_1_place else None
            raw_recommendations = predictor.generate_recommendations(
                current_score,
                target_score,
                current_n1=current_n1  # N3 효과 계산을 위해 N1 전달
            )
            # dict를 RecommendationItem으로 변환
            recommendations = [
                RecommendationItem(**rec) for rec in raw_recommendations
            ]

        # 6. 경쟁사 정보
        competitors = []
        for place in transformed_places[:10]:  # 상위 10개
            competitors.append(CompetitorResponse(
                rank=place["rank"],
                name=place["name"],
                score=place["scores"]["quality_score"],
            ))

        # 7. 전체 업체 리스트
        all_places = []
        for place in transformed_places:
            all_places.append(PlaceResponse(
                place_id=place["place_id"],
                name=place["name"],
                rank=place["rank"],
                scores=ScoresResponse(**place["scores"]),
                metrics=MetricsResponse(**place["metrics"]),
                changes=ChangesResponse(**place["changes"]),
            ))

        return AnalyzeResponse(
            keyword=request.keyword,
            my_place=my_place,
            comparison=comparison,
            recommendations=recommendations,
            competitors=competitors,
            all_places=all_places,
        )

    except AdlogApiError as e:
        logger.error(f"ADLOG API error: {str(e)}")
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        logger.error(f"Analysis error: {str(e)}")
        raise HTTPException(status_code=500, detail="분석 중 오류가 발생했습니다.")


@router.get("/analyze/{keyword}")
async def analyze_keyword_get(
    keyword: str,
    place_name: Optional[str] = None
):
    """GET 방식 분석 (간단 조회용)"""
    request = AnalyzeRequest(keyword=keyword, place_name=place_name)
    return await analyze_keyword(request)
