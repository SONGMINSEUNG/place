"""
Analyze API
키워드 분석 엔드포인트

- 최초 검색 (캐시 없음): ADLOG API만 사용 (크롤링 X)
- 재검색 (캐시 있음): 네이버 크롤링 실행 (저장된 total_count 기반)
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


def round_index(value: float) -> float:
    """N1, N2, N3 값을 반올림 없이 그대로 반환"""
    return value


def normalize_and_round_index(value: float) -> float:
    """
    N1, N2, N3 원본 값 그대로 반환
    score_converter에서 자체 점수 체계(*137)로 변환하므로 여기서는 원본 유지
    """
    return value


@router.post("/analyze", response_model=AnalyzeResponse)
async def analyze_keyword(
    request: AnalyzeRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    키워드 분석 API

    - 최초 검색 (캐시 없음): ADLOG 결과 그대로 반환 (크롤링 X)
    - 재검색 (캐시 있음): 네이버 크롤링으로 업체 조회

    Parameters:
    - keyword: 검색 키워드 (필수)
    - place_name: 업체명 (선택) - 지정 시 해당 업체 하이라이트
    - inflow: 오늘 유입수 (선택)
    """
    try:
        data_source = "cache"  # 기본값

        # 1. 키워드 파라미터 캐시 확인
        cached_params = await parameter_repository.get_by_keyword(db, request.keyword)

        # 2. 캐시가 없으면 최초 검색 -> ADLOG만 사용 (크롤링 X)
        if not cached_params or not formula_calculator.can_calculate(cached_params):
            data_source = "api"
            logger.info(f"First search - ADLOG only (no crawling): {request.keyword}")

            try:
                raw_data = await adlog_service.fetch_keyword_analysis(request.keyword)
                adlog_places = raw_data.get("places", [])
                adlog_total_count = raw_data.get("total_count", 0)

                if not adlog_places:
                    raise HTTPException(status_code=404, detail="검색 결과가 없습니다.")

                # 파라미터 추출
                extracted_params = parameter_extractor.extract_from_adlog_response(
                    request.keyword, adlog_places
                )
                # total_count 업데이트 (ADLOG 응답의 total_count 사용)
                extracted_params["total_count"] = adlog_total_count

                # 파라미터 저장
                cached_params = await parameter_repository.save_or_update(db, extracted_params)
                await db.commit()
                logger.info(f"Saved keyword parameters for: {request.keyword} (total_count: {adlog_total_count})")

                # ADLOG 결과로 places 생성 (크롤링 없이)
                places = []
                for idx, adlog_place in enumerate(adlog_places):
                    raw = adlog_place.get("raw_indices", {})
                    n1_val = raw.get("n1", 50.0)
                    n2_val = raw.get("n2", 50.0)
                    n3_val = raw.get("n3", 50.0)

                    # 반올림 처리 (소수점 첫째자리)
                    indices = {
                        "n1": normalize_and_round_index(n1_val),
                        "n2": normalize_and_round_index(n2_val),
                        "n3": normalize_and_round_index(n3_val),
                    }

                    # ADLOG 메트릭스
                    metrics = adlog_place.get("metrics", {})

                    places.append({
                        "place_id": adlog_place.get("place_id", f"adlog_{idx + 1}"),
                        "name": adlog_place.get("name", f"업체 {idx + 1}"),
                        "rank": adlog_place.get("rank", idx + 1),
                        "raw_indices": {
                            "n1": indices["n1"],
                            "n2": indices["n2"],
                            "n3": indices["n3"],
                        },
                        "metrics": {
                            "visit_count": metrics.get("visitor_review_count", 0),
                            "blog_count": metrics.get("blog_count", 0),
                            "save_count": metrics.get("save_count", 0),
                        },
                    })

            except AdlogApiError as e:
                logger.error(f"ADLOG API error: {str(e)}")
                raise HTTPException(status_code=503, detail=str(e))
            except HTTPException:
                raise
            except Exception as e:
                logger.error(f"Failed to fetch from ADLOG: {str(e)}")
                raise HTTPException(status_code=500, detail="ADLOG API 호출 중 오류가 발생했습니다.")

        else:
            # 3. 캐시가 있으면 재검색 -> 네이버 크롤링 실행
            await parameter_repository.increment_cache_hit(db, request.keyword)

            # 저장된 total_count 기반으로 크롤링 개수 결정
            crawl_target = cached_params.total_count if cached_params.total_count else 300
            crawl_target = min(300, int(crawl_target * 1.2))  # 20% 여유분, 최대 300

            logger.info(f"Re-search - Naver crawling: {request.keyword} (target: {crawl_target})")

            try:
                naver_places = await naver_service.search_places(request.keyword, max_results=crawl_target)
                logger.info(f"Naver returned {len(naver_places)} places")
            except Exception as e:
                logger.error(f"Naver crawling failed: {e}")
                naver_places = []

            if not naver_places:
                raise HTTPException(status_code=404, detail="검색 결과가 없습니다.")

            # 크롤링 결과에 N1, N2, N3 계산하여 추가
            places = []
            for idx, naver_place in enumerate(naver_places):
                rank = idx + 1

                # 저장된 파라미터로 자체 계산
                if formula_calculator.can_calculate(cached_params):
                    raw_indices = formula_calculator.calculate_all_indices(cached_params, rank)
                    # 반올림 처리 (소수점 첫째자리)
                    indices = {
                        "n1": round_index(raw_indices["n1"]),
                        "n2": round_index(raw_indices["n2"]),
                        "n3": round_index(raw_indices["n3"]),
                    }
                else:
                    indices = {"n1": 50.0, "n2": 50.0, "n3": 50.0}

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

        # 4. 점수 변환
        transformed_places = place_transformer.transform_all_places(places)

        # 5. 내 업체 찾기
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

        # 5.1 유입수가 있으면 사용자 데이터 저장
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

        # 6. 1위 비교 분석
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

        # 7. 마케팅 제언 생성
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

        # 8. 경쟁사 정보 (전체 업체 표시)
        competitors = []
        for place in transformed_places:
            competitors.append(CompetitorResponse(
                rank=place["rank"],
                name=place["name"],
                score=place["scores"]["quality_score"],
            ))

        # 9. 전체 업체 리스트
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
            data_source=data_source,  # api: ADLOG API 최초 조회, cache: 캐시+크롤링
        )

    except AdlogApiError as e:
        logger.error(f"ADLOG API error: {str(e)}")
        raise HTTPException(status_code=503, detail=str(e))
    except HTTPException:
        raise
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
