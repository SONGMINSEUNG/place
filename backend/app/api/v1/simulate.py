"""
Simulate API
점수 시뮬레이션 엔드포인트
"""
from fastapi import APIRouter, HTTPException
from app.models.schemas import SimulateRequest, SimulateResponse, SimulateEffectItem
from app.services.adlog_proxy import adlog_service, AdlogApiError
from app.services.score_converter import place_transformer
from app.ml.predictor import predictor
import logging

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/simulate", response_model=SimulateResponse)
async def simulate_score(request: SimulateRequest):
    """
    점수 시뮬레이션 API

    사용자가 입력한 수치로 예상 점수 계산

    - keyword: 검색 키워드
    - place_name: 업체명
    - inputs:
        - inflow: 유입수 추가
        - reservation: 예약수 추가
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
            "reservation": request.inputs.reservation,
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
    reservation: int = 0,
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
            reservation=reservation,
            blog_review=blog_review,
            visit_review=visit_review,
        )
    )
    return await simulate_score(request)
