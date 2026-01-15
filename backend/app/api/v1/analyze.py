"""
Analyze API
키워드 분석 엔드포인트

Phase 1: 키워드 파라미터 캐싱 시스템 적용
- 캐시 있고 신뢰할 수 있으면 자체 계산
- 캐시 없거나 신뢰도 낮으면 ADLOG API 호출 후 파라미터 저장
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
from app.services.parameter_extractor import parameter_extractor, parameter_repository
from app.services.formula_calculator import formula_calculator
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

    응답에 data_source 필드 추가:
    - "api": ADLOG API에서 직접 조회
    - "cache": 캐싱된 파라미터로 자체 계산
    """
    try:
        data_source = "api"  # 기본값

        # 1. 키워드 파라미터 캐시 확인
        cached_params = await parameter_repository.get_by_keyword(db, request.keyword)

        # 2. 캐시가 있고 신뢰할 수 있으면 자체 계산 (Phase 2: 활성화됨)
        if cached_params and formula_calculator.can_calculate(cached_params):
            data_source = "cache"
            await parameter_repository.increment_cache_hit(db, request.keyword)
            logger.info(f"Using cached parameters for keyword: {request.keyword}")

            # 자체 계산으로 가상 places 생성 (순위 1-50까지)
            places = []
            for rank in range(1, 51):
                indices = formula_calculator.calculate_all_indices(cached_params, rank)
                places.append({
                    "place_id": f"cached_{rank}",
                    "name": f"순위 {rank} 업체 (캐시)",
                    "rank": rank,
                    "raw_indices": {
                        "n1": indices["n1"],
                        "n2": indices["n2"],
                        "n3": indices["n3"],
                    },
                    "metrics": {
                        "visit_count": 0,
                        "blog_count": 0,
                        "save_count": 0,
                    },
                })
        else:
            # 3. 캐시 없거나 신뢰도 낮으면 ADLOG API 호출
            raw_data = await adlog_service.fetch_keyword_analysis(request.keyword)
            places = raw_data.get("places", [])

        # 4. 파라미터 추출 및 저장 (API 호출한 경우에만)
        if data_source == "api" and places:
            try:
                extracted_params = parameter_extractor.extract_from_adlog_response(
                    request.keyword, places
                )
                await parameter_repository.save_or_update(db, extracted_params)
                await db.commit()
                logger.info(f"Saved keyword parameters for: {request.keyword}")
            except Exception as e:
                logger.error(f"Failed to save keyword parameters: {str(e)}")
                # 파라미터 저장 실패해도 분석 결과는 반환

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

        # 3.1 유입수가 있으면 사용자 데이터 저장
        if my_place_data and request.inflow is not None:
            try:
                raw_indices = my_place_raw.get("raw_indices", {}) if my_place_raw else {}
                metrics = my_place_raw.get("metrics", {}) if my_place_raw else {}

                user_data = UserInputData(
                    keyword=request.keyword,
                    place_id=my_place_data["place_id"],
                    place_name=my_place_data["name"],
                    inflow=request.inflow or 0,
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
                logger.info(f"Saved user input data: keyword={request.keyword}, place={my_place_data['name']}, inflow={request.inflow}")
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
            data_source=data_source,
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
    place_name: Optional[str] = None,
    db: AsyncSession = Depends(get_db)
):
    """GET 방식 분석 (간단 조회용)"""
    request = AnalyzeRequest(keyword=keyword, place_name=place_name)
    return await analyze_keyword(request, db)
