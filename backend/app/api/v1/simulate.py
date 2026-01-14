"""
Simulate API
점수 시뮬레이션 엔드포인트
"""
from fastapi import APIRouter, HTTPException, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, Field
from typing import Optional

from app.models.schemas import SimulateRequest, SimulateResponse, SimulateEffectItem
from app.services.adlog_proxy import adlog_service, AdlogApiError
from app.services.score_converter import place_transformer
from app.services.parameter_extractor import parameter_repository
from app.services.formula_calculator import formula_calculator
from app.ml.predictor import predictor, calculate_n3
from app.core.database import get_db
import logging

logger = logging.getLogger(__name__)
router = APIRouter()


# ===========================================
# 목표 순위 시뮬레이션 스키마
# ===========================================

class ScoreChange(BaseModel):
    """점수 변화 정보"""
    current: float = Field(..., description="현재 점수")
    target: float = Field(..., description="목표 점수")
    change: float = Field(..., description="변화량")


class TargetRankRequest(BaseModel):
    """목표 순위 시뮬레이션 요청"""
    keyword: str = Field(..., min_length=1, max_length=50, description="검색 키워드")
    place_name: str = Field(..., min_length=1, max_length=100, description="업체명")
    current_rank: int = Field(..., ge=1, le=300, description="현재 순위")
    target_rank: int = Field(..., ge=1, le=300, description="목표 순위")


class TargetRankResponse(BaseModel):
    """목표 순위 시뮬레이션 응답"""
    keyword: str
    place_name: str
    current_rank: int
    target_rank: int
    n2_change: ScoreChange
    n3_change: ScoreChange
    message: str
    is_achievable: bool = Field(default=True, description="달성 가능 여부")
    data_source: str = Field(default="api", description="데이터 소스 (api/cache)")


@router.post("/simulate", response_model=SimulateResponse)
async def simulate_score(request: SimulateRequest):
    """
    점수 시뮬레이션 API

    사용자가 입력한 수치로 예상 점수 계산

    - keyword: 검색 키워드
    - place_name: 업체명
    - inputs:
        - inflow: 유입수 추가
        - blog_review: 블로그 리뷰 추가
        - visit_review: 방문자 리뷰 추가
    """
    try:
        # 1. ADLOG API 호출하여 현재 데이터 조회
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
        for place in transformed_places:
            if request.place_name.lower() in place["name"].lower():
                my_place = place
                break

        if not my_place:
            raise HTTPException(
                status_code=404,
                detail=f"'{request.place_name}' 업체를 찾을 수 없습니다."
            )

        # 4. 시뮬레이션 실행
        current_score = my_place["scores"]["quality_score"]  # N2
        current_n1 = my_place["scores"]["keyword_score"]  # N1
        current_n3 = my_place["scores"]["competition_score"]  # N3 (실제 API 값)
        current_rank = my_place["rank"]

        inputs = {
            "inflow": request.inputs.inflow,
            "blog_review": request.inputs.blog_review,
            "visit_review": request.inputs.visit_review,
        }

        # N1과 현재 N3를 전달하여 시뮬레이션 (현재 N3는 실제 값 사용)
        simulation_result = predictor.simulate(
            current_score,
            inputs,
            n1=current_n1,
            current_n3_actual=current_n3  # 실제 API에서 받아온 N3 값
        )

        # 5. 예상 순위 계산 (N3 기준)
        predicted_score = simulation_result["predicted_score"]
        predicted_rank = predictor.estimate_rank(
            predicted_score,
            transformed_places,
            use_n3=True,
            my_n1=current_n1
        )

        # 6. 응답 구성
        effects = {}
        for key, value in simulation_result["effects"].items():
            effects[key] = SimulateEffectItem(
                amount=value["amount"],
                effect=value["effect"]
            )

        return SimulateResponse(
            current_score=current_score,
            current_rank=current_rank,
            effects=effects,
            total_effect=simulation_result["total_effect"],
            predicted_score=predicted_score,
            predicted_rank=predicted_rank,
            # N3 관련 필드 추가
            current_n3=simulation_result.get("current_n3"),
            predicted_n3=simulation_result.get("predicted_n3"),
            n3_change=simulation_result.get("n3_change"),
        )

    except AdlogApiError as e:
        logger.error(f"ADLOG API error: {str(e)}")
        raise HTTPException(status_code=503, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Simulation error: {str(e)}")
        raise HTTPException(status_code=500, detail="시뮬레이션 중 오류가 발생했습니다.")


@router.post("/simulate/quick")
async def quick_simulate(
    keyword: str,
    place_name: str,
    inflow: int = 0,
    blog_review: int = 0,
    visit_review: int = 0,
):
    """
    간편 시뮬레이션 (쿼리 파라미터 방식)
    """
    from app.models.schemas import SimulateInputs

    request = SimulateRequest(
        keyword=keyword,
        place_name=place_name,
        inputs=SimulateInputs(
            inflow=inflow,
            blog_review=blog_review,
            visit_review=visit_review,
        )
    )
    return await simulate_score(request)


@router.post("/simulate/target-rank", response_model=TargetRankResponse)
async def simulate_target_rank(
    request: TargetRankRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    목표 순위 기반 시뮬레이션

    현재 순위에서 목표 순위로 이동 시 예상되는 N2, N3 점수 변화를 계산합니다.
    키워드별 파라미터(n2_slope, n2_intercept)를 사용하여 정확한 예측을 제공합니다.

    - keyword: 검색 키워드
    - place_name: 업체명
    - current_rank: 현재 순위
    - target_rank: 목표 순위 (1 ~ current_rank-1)
    """
    # 유효성 검사
    if request.target_rank >= request.current_rank:
        raise HTTPException(
            status_code=400,
            detail="목표 순위는 현재 순위보다 높아야 합니다 (작은 숫자)."
        )

    if request.current_rank == 1:
        raise HTTPException(
            status_code=400,
            detail="이미 1위입니다! 목표 순위 시뮬레이션이 필요하지 않습니다."
        )

    data_source = "cache"
    current_n1: Optional[float] = None
    current_n2: Optional[float] = None
    target_n2: Optional[float] = None

    try:
        # 1. 캐싱된 파라미터 확인
        params = await parameter_repository.get_by_keyword(db, request.keyword)

        if params and formula_calculator.can_calculate(params):
            # 캐싱된 파라미터로 계산
            current_n1 = formula_calculator.calculate_n1(params)
            current_n2 = formula_calculator.calculate_n2(params, request.current_rank)
            target_n2 = formula_calculator.calculate_n2(params, request.target_rank)

            logger.info(f"Using cached parameters for keyword: {request.keyword}")
        else:
            # 캐시가 없으면 ADLOG API 호출
            data_source = "api"
            raw_data = await adlog_service.fetch_keyword_analysis(request.keyword)
            places = raw_data.get("places", [])

            if not places:
                raise HTTPException(
                    status_code=404,
                    detail="검색 결과가 없습니다."
                )

            # 점수 변환
            transformed_places = place_transformer.transform_all_places(places)

            # 내 업체 찾기 (현재 순위로 매칭)
            my_place = None
            target_place = None

            for place in transformed_places:
                if request.place_name.lower() in place["name"].lower():
                    my_place = place
                if place["rank"] == request.target_rank:
                    target_place = place

            if not my_place:
                raise HTTPException(
                    status_code=404,
                    detail=f"'{request.place_name}' 업체를 찾을 수 없습니다."
                )

            current_n1 = my_place["scores"]["keyword_score"]
            current_n2 = my_place["scores"]["quality_score"]

            # 목표 순위 업체의 N2 참조 (없으면 선형 추정)
            if target_place:
                target_n2 = target_place["scores"]["quality_score"]
            else:
                # 선형 추정: N2 = current_n2 + (순위 차이 * 추정 slope)
                # 일반적으로 순위 1 상승당 N2 약 0.5~1.0 증가
                rank_diff = request.current_rank - request.target_rank
                estimated_increase = rank_diff * 0.8  # 순위당 0.8점 증가 추정
                target_n2 = min(100.0, current_n2 + estimated_increase)

            logger.info(f"Using ADLOG API for keyword: {request.keyword}")

        # 2. N3 계산
        if current_n1 is None or current_n2 is None or target_n2 is None:
            raise HTTPException(
                status_code=500,
                detail="점수 계산에 필요한 데이터가 부족합니다."
            )

        current_n3 = calculate_n3(current_n1, current_n2) * 100
        target_n3 = calculate_n3(current_n1, target_n2) * 100

        # 3. 변화량 계산
        n2_change_value = target_n2 - current_n2
        n3_change_value = target_n3 - current_n3

        # 4. 메시지 생성
        rank_diff = request.current_rank - request.target_rank

        if n2_change_value > 0:
            message = f"{request.target_rank}위 달성을 위해 N2(품질점수)를 약 {n2_change_value:.2f}점 높여야 합니다. N3(경쟁력)은 약 {n3_change_value:.2f}점 상승할 것으로 예상됩니다."
        else:
            message = f"현재 점수로도 {request.target_rank}위 달성이 가능할 수 있습니다. 경쟁사 변동에 주의하세요."

        # 달성 가능성 판단 (N2가 100점 이상 필요하면 어려움)
        is_achievable = target_n2 <= 100.0

        return TargetRankResponse(
            keyword=request.keyword,
            place_name=request.place_name,
            current_rank=request.current_rank,
            target_rank=request.target_rank,
            n2_change=ScoreChange(
                current=round(current_n2, 4),
                target=round(target_n2, 4),
                change=round(n2_change_value, 4)
            ),
            n3_change=ScoreChange(
                current=round(current_n3, 4),
                target=round(target_n3, 4),
                change=round(n3_change_value, 4)
            ),
            message=message,
            is_achievable=is_achievable,
            data_source=data_source
        )

    except AdlogApiError as e:
        logger.error(f"ADLOG API error: {str(e)}")
        raise HTTPException(status_code=503, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Target rank simulation error: {str(e)}")
        raise HTTPException(status_code=500, detail="목표 순위 시뮬레이션 중 오류가 발생했습니다.")
