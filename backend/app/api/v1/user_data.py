"""
User Data API
사용자 데이터 입력 및 상관관계 분석 엔드포인트
"""
from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime
from typing import List, Optional
import numpy as np
from scipy import stats

from app.models.schemas import (
    SubmitDataRequest,
    SubmitDataResponse,
    CorrelationResult,
    CorrelationResponse,
)
from app.models.place import UserInputData
from app.services.adlog_proxy import adlog_service, AdlogApiError
from app.core.database import get_db
import logging

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/submit-data", response_model=SubmitDataResponse)
async def submit_user_data(
    request: SubmitDataRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    사용자 데이터 제출 API

    - keyword: 검색 키워드
    - place_id: 플레이스 ID
    - place_name: 업체명 (선택)
    - inflow: 유입수
    - reservation: 예약수

    내부적으로 ADLOG API를 호출하여 N2 값을 가져와 함께 저장합니다.
    """
    try:
        # 1. ADLOG API 호출하여 N2 값 가져오기
        n1, n2, n3 = None, None, None
        rank = None
        visitor_review_count = 0
        blog_review_count = 0
        save_count = 0

        try:
            raw_data = await adlog_service.fetch_keyword_analysis(request.keyword)
            places = raw_data.get("places", [])

            # place_id나 place_name으로 해당 업체 찾기
            for place in places:
                place_match = False
                if request.place_id and place.get("place_id") == request.place_id:
                    place_match = True
                elif request.place_name and request.place_name.lower() in place.get("name", "").lower():
                    place_match = True

                if place_match:
                    raw_indices = place.get("raw_indices", {})
                    n1 = raw_indices.get("n1")
                    n2 = raw_indices.get("n2")
                    n3 = raw_indices.get("n3")
                    rank = place.get("rank")
                    metrics = place.get("metrics", {})
                    visitor_review_count = metrics.get("visit_count", 0)
                    blog_review_count = metrics.get("blog_count", 0)
                    save_count = metrics.get("save_count", 0)
                    break

        except AdlogApiError as e:
            logger.warning(f"ADLOG API error while fetching N2: {str(e)}")
            # ADLOG API 실패해도 사용자 데이터는 저장

        # 2. 데이터베이스에 저장
        user_data = UserInputData(
            keyword=request.keyword,
            place_id=request.place_id,
            place_name=request.place_name,
            inflow=request.inflow,
            reservation=request.reservation,
            n1=n1,
            n2=n2,
            n3=n3,
            rank=rank,
            visitor_review_count=visitor_review_count,
            blog_review_count=blog_review_count,
            save_count=save_count,
        )
        db.add(user_data)
        await db.commit()
        await db.refresh(user_data)

        logger.info(f"User data saved: keyword={request.keyword}, place_id={request.place_id}, n2={n2}")

        return SubmitDataResponse(
            success=True,
            data_id=user_data.id,
            keyword=user_data.keyword,
            place_id=user_data.place_id,
            place_name=user_data.place_name,
            inflow=user_data.inflow,
            reservation=user_data.reservation,
            n2=user_data.n2,
            rank=user_data.rank,
            created_at=user_data.created_at,
        )

    except Exception as e:
        logger.error(f"Error submitting user data: {str(e)}")
        raise HTTPException(status_code=500, detail="데이터 저장 중 오류가 발생했습니다.")


def calculate_correlation(x: List[float], y: List[float]) -> tuple:
    """
    피어슨 상관계수 및 p-value 계산

    Returns:
        (correlation, p_value)
    """
    if len(x) < 3 or len(y) < 3:
        return 0.0, 1.0

    # NaN 값 제거
    valid_pairs = [(xi, yi) for xi, yi in zip(x, y) if xi is not None and yi is not None]
    if len(valid_pairs) < 3:
        return 0.0, 1.0

    x_clean = [p[0] for p in valid_pairs]
    y_clean = [p[1] for p in valid_pairs]

    try:
        correlation, p_value = stats.pearsonr(x_clean, y_clean)
        return float(correlation), float(p_value)
    except Exception:
        return 0.0, 1.0


@router.get("/correlation", response_model=CorrelationResponse)
async def get_correlation_analysis(
    keyword: Optional[str] = None,
    db: AsyncSession = Depends(get_db)
):
    """
    상관관계 분석 API

    수집된 사용자 데이터를 바탕으로 다음 상관관계를 분석합니다:
    - 유입수 <-> N2 (품질점수)
    - 예약수 <-> N2 (품질점수)
    - 유입수 <-> 순위
    - 예약수 <-> 순위

    Args:
        keyword: 특정 키워드로 필터링 (선택)
    """
    try:
        # 데이터 조회
        query = select(UserInputData)
        if keyword:
            query = query.where(UserInputData.keyword == keyword)

        result = await db.execute(query)
        data_list = result.scalars().all()

        if len(data_list) < 3:
            raise HTTPException(
                status_code=400,
                detail=f"상관관계 분석을 위해 최소 3개 이상의 데이터가 필요합니다. 현재: {len(data_list)}개"
            )

        # 데이터 추출
        inflows = [d.inflow for d in data_list]
        reservations = [d.reservation for d in data_list]
        n2_values = [d.n2 for d in data_list if d.n2 is not None]
        ranks = [d.rank for d in data_list if d.rank is not None]

        # 상관관계 계산
        # 유입수 <-> N2
        inflow_n2_corr, inflow_n2_pval = calculate_correlation(
            inflows,
            [d.n2 for d in data_list]
        )

        # 예약수 <-> N2
        res_n2_corr, res_n2_pval = calculate_correlation(
            reservations,
            [d.n2 for d in data_list]
        )

        # 유입수 <-> 순위 (순위는 낮을수록 좋으므로 음의 상관이 좋은 것)
        inflow_rank_corr, inflow_rank_pval = calculate_correlation(
            inflows,
            [d.rank for d in data_list]
        )

        # 예약수 <-> 순위
        res_rank_corr, res_rank_pval = calculate_correlation(
            reservations,
            [d.rank for d in data_list]
        )

        # 해석 생성
        interpretation_parts = []

        if inflow_n2_pval < 0.05:
            if inflow_n2_corr > 0.5:
                interpretation_parts.append("유입수와 품질점수(N2) 사이에 강한 양의 상관관계가 있습니다.")
            elif inflow_n2_corr > 0.3:
                interpretation_parts.append("유입수와 품질점수(N2) 사이에 중간 정도의 양의 상관관계가 있습니다.")
            elif inflow_n2_corr < -0.3:
                interpretation_parts.append("유입수와 품질점수(N2) 사이에 음의 상관관계가 있습니다.")

        if res_n2_pval < 0.05:
            if res_n2_corr > 0.5:
                interpretation_parts.append("예약수와 품질점수(N2) 사이에 강한 양의 상관관계가 있습니다.")
            elif res_n2_corr > 0.3:
                interpretation_parts.append("예약수와 품질점수(N2) 사이에 중간 정도의 양의 상관관계가 있습니다.")

        if inflow_rank_pval < 0.05 and inflow_rank_corr < -0.3:
            interpretation_parts.append("유입수가 높을수록 순위가 좋아지는 경향이 있습니다.")

        if res_rank_pval < 0.05 and res_rank_corr < -0.3:
            interpretation_parts.append("예약수가 높을수록 순위가 좋아지는 경향이 있습니다.")

        if not interpretation_parts:
            interpretation_parts.append("현재 데이터에서는 유의미한 상관관계가 발견되지 않았습니다. 더 많은 데이터 수집이 필요합니다.")

        interpretation = " ".join(interpretation_parts)

        return CorrelationResponse(
            inflow_n2=CorrelationResult(
                variable1="유입수",
                variable2="품질점수(N2)",
                correlation=round(inflow_n2_corr, 4),
                p_value=round(inflow_n2_pval, 4),
                is_significant=inflow_n2_pval < 0.05,
                sample_size=len([d for d in data_list if d.n2 is not None]),
            ),
            reservation_n2=CorrelationResult(
                variable1="예약수",
                variable2="품질점수(N2)",
                correlation=round(res_n2_corr, 4),
                p_value=round(res_n2_pval, 4),
                is_significant=res_n2_pval < 0.05,
                sample_size=len([d for d in data_list if d.n2 is not None]),
            ),
            inflow_rank=CorrelationResult(
                variable1="유입수",
                variable2="순위",
                correlation=round(inflow_rank_corr, 4),
                p_value=round(inflow_rank_pval, 4),
                is_significant=inflow_rank_pval < 0.05,
                sample_size=len([d for d in data_list if d.rank is not None]),
            ),
            reservation_rank=CorrelationResult(
                variable1="예약수",
                variable2="순위",
                correlation=round(res_rank_corr, 4),
                p_value=round(res_rank_pval, 4),
                is_significant=res_rank_pval < 0.05,
                sample_size=len([d for d in data_list if d.rank is not None]),
            ),
            total_samples=len(data_list),
            analysis_date=datetime.now(),
            interpretation=interpretation,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in correlation analysis: {str(e)}")
        raise HTTPException(status_code=500, detail="상관관계 분석 중 오류가 발생했습니다.")


@router.get("/user-data")
async def get_user_data(
    keyword: Optional[str] = None,
    place_id: Optional[str] = None,
    limit: int = 100,
    db: AsyncSession = Depends(get_db)
):
    """
    저장된 사용자 데이터 조회

    Args:
        keyword: 키워드로 필터링
        place_id: 플레이스 ID로 필터링
        limit: 조회 개수 (기본 100)
    """
    try:
        query = select(UserInputData).order_by(UserInputData.created_at.desc()).limit(limit)

        if keyword:
            query = query.where(UserInputData.keyword == keyword)
        if place_id:
            query = query.where(UserInputData.place_id == place_id)

        result = await db.execute(query)
        data_list = result.scalars().all()

        return {
            "total": len(data_list),
            "data": [
                {
                    "id": d.id,
                    "keyword": d.keyword,
                    "place_id": d.place_id,
                    "place_name": d.place_name,
                    "inflow": d.inflow,
                    "reservation": d.reservation,
                    "n1": d.n1,
                    "n2": d.n2,
                    "n3": d.n3,
                    "rank": d.rank,
                    "visitor_review_count": d.visitor_review_count,
                    "blog_review_count": d.blog_review_count,
                    "save_count": d.save_count,
                    "created_at": d.created_at.isoformat(),
                }
                for d in data_list
            ]
        }

    except Exception as e:
        logger.error(f"Error fetching user data: {str(e)}")
        raise HTTPException(status_code=500, detail="데이터 조회 중 오류가 발생했습니다.")
