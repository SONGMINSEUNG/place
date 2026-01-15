"""
Analyze API
키워드 분석 엔드포인트

항상 네이버 크롤링으로 전체 업체 가져옴
- 새 키워드: ADLOG API로 파라미터 추출 → 저장 → 네이버 크롤링
- 캐시 키워드: 캐시된 파라미터 사용 → 네이버 크롤링
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
from app.services.naver_place import NaverPlaceService
from app.ml.predictor import predictor
from app.core.database import get_db
import logging

# 네이버 크롤링 서비스 인스턴스
naver_service = NaverPlaceService()

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/analyze", response_model=AnalyzeResponse)
async def analyze_keyword(
    request: AnalyzeRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    키워드 분석 API - 항상 네이버 크롤링으로 50개 업체 조회

    - keyword: 검색 키워드 (필수)
    - place_name: 업체명 (선택) - 지정 시 해당 업체 하이라이트
    - inflow: 오늘 유입수 (선택)
    """
    try:
        # 1. 키워드 파라미터 캐시 확인
        cached_params = await parameter_repository.get_by_keyword(db, request.keyword)

        # 2. 캐시 없으면 ADLOG API로 파라미터 추출 (1회만)
        if not cached_params or not formula_calculator.can_calculate(cached_params):
            logger.info(f"New keyword, extracting parameters from ADLOG: {request.keyword}")
            try:
                raw_data = await adlog_service.fetch_keyword_analysis(request.keyword)
                adlog_places = raw_data.get("places", [])
                if adlog_places:
                    extracted_params = parameter_extractor.extract_from_adlog_response(
                        request.keyword, adlog_places
                    )
                    await parameter_repository.save_or_update(db, extracted_params)
                    await db.commit()
                    cached_params = extracted_params
                    logger.info(f"Saved keyword parameters for: {request.keyword}")
            except Exception as e:
                logger.error(f"Failed to extract parameters from ADLOG: {str(e)}")
        else:
            await parameter_repository.increment_cache_hit(db, request.keyword)

        # 3. 네이버 크롤링으로 전체 업체 가져오기
        logger.info(f"Fetching places from Naver for: {request.keyword}")
        try:
            naver_places = await naver_service.search_places(request.keyword, max_results=300)
            logger.info(f"Naver returned {len(naver_places)} places")
        except Exception as e:
            logger.error(f"Naver crawling failed: {e}")
            naver_places = []

        if not naver_places:
            raise HTTPException(status_code=404, detail="검색 결과가 없습니다.")

        # 4. 크롤링 결과에 N1, N2, N3 계산하여 추가
        places = []
        for idx, naver_place in enumerate(naver_places):
            rank = idx + 1

            # 파라미터가 있으면 자체 계산, 없으면 기본값
            if cached_params and formula_calculator.can_calculate(cached_params):
                indices = formula_calculator.calculate_all_indices(cached_params, rank)
            else:
                indices = {"n1": 50.0, "n2": 50.0, "n3": 50.0}  # 기본값

            places.append({
                "place_id": naver_place.get("place_id", f"naver_{rank}"),
                "name": naver_place.get("name", f"업체 {rank}"),
                "rank": rank,
                "raw_indices": {
                    "n1": indices["n1"],
                    "n2": indices["n2"],
                    "n3": indices["n3"],
                },
                "metrics": {
                    "visit_count": naver_place.get("visitor_review_count", 0),
                    "blog_count": naver_place.get("blog_review_count", 0),
                    "save_count": naver_place.get("save_count", 0),
                },
            })

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
