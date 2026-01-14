"""
Parameters API
키워드 파라미터 조회 및 관리 엔드포인트
"""
from fastapi import APIRouter, HTTPException, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from typing import Optional, List
from pydantic import BaseModel, Field
from datetime import datetime

from app.models.place import KeywordParameter
from app.services.parameter_extractor import parameter_repository
from app.services.formula_calculator import formula_calculator
from app.core.database import get_db
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/parameters")


# ===========================================
# Response Schemas
# ===========================================

class KeywordParameterResponse(BaseModel):
    """키워드 파라미터 응답"""
    keyword: str
    n1_constant: Optional[float] = None
    n1_std: Optional[float] = None
    n2_slope: Optional[float] = None
    n2_intercept: Optional[float] = None
    n2_r_squared: Optional[float] = None
    sample_count: int = 0
    api_call_count: int = 0
    cache_hit_count: int = 0
    is_reliable: bool = False
    last_trained_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ParameterStatsResponse(BaseModel):
    """파라미터 통계 응답"""
    total_keywords: int
    reliable_keywords: int
    unreliable_keywords: int
    total_api_calls: int
    total_cache_hits: int
    cache_hit_ratio: float
    avg_sample_count: float
    avg_r_squared: Optional[float]


class CalculatedIndicesResponse(BaseModel):
    """계산된 지수 응답"""
    keyword: str
    rank: int
    n1: Optional[float] = None
    n2: Optional[float] = None
    n3: Optional[float] = None
    is_reliable: bool = False


# ===========================================
# API Endpoints
# ===========================================

@router.get("/", response_model=List[KeywordParameterResponse])
async def list_parameters(
    limit: int = Query(50, ge=1, le=500, description="조회 개수"),
    offset: int = Query(0, ge=0, description="오프셋"),
    reliable_only: bool = Query(False, description="신뢰할 수 있는 것만"),
    db: AsyncSession = Depends(get_db)
):
    """
    저장된 키워드 파라미터 목록 조회
    """
    query = select(KeywordParameter)

    if reliable_only:
        query = query.where(KeywordParameter.is_reliable.is_(True))

    query = query.order_by(KeywordParameter.updated_at.desc())
    query = query.offset(offset).limit(limit)

    result = await db.execute(query)
    params = result.scalars().all()

    return [KeywordParameterResponse.model_validate(p) for p in params]


@router.get("/stats", response_model=ParameterStatsResponse)
async def get_parameter_stats(
    db: AsyncSession = Depends(get_db)
):
    """
    파라미터 통계 조회
    """
    # 전체 키워드 수
    total_result = await db.execute(
        select(func.count(KeywordParameter.id))
    )
    total_keywords = total_result.scalar() or 0

    # 신뢰할 수 있는 키워드 수
    reliable_result = await db.execute(
        select(func.count(KeywordParameter.id)).where(KeywordParameter.is_reliable.is_(True))
    )
    reliable_keywords = reliable_result.scalar() or 0

    # 총 API 호출 수
    api_calls_result = await db.execute(
        select(func.sum(KeywordParameter.api_call_count))
    )
    total_api_calls = api_calls_result.scalar() or 0

    # 총 캐시 히트 수
    cache_hits_result = await db.execute(
        select(func.sum(KeywordParameter.cache_hit_count))
    )
    total_cache_hits = cache_hits_result.scalar() or 0

    # 평균 샘플 수
    avg_sample_result = await db.execute(
        select(func.avg(KeywordParameter.sample_count))
    )
    avg_sample_count = avg_sample_result.scalar() or 0

    # 평균 R²
    avg_r2_result = await db.execute(
        select(func.avg(KeywordParameter.n2_r_squared)).where(
            KeywordParameter.n2_r_squared.isnot(None)
        )
    )
    avg_r_squared = avg_r2_result.scalar()

    # 캐시 히트 비율
    total_requests = total_api_calls + total_cache_hits
    cache_hit_ratio = total_cache_hits / total_requests if total_requests > 0 else 0.0

    return ParameterStatsResponse(
        total_keywords=total_keywords,
        reliable_keywords=reliable_keywords,
        unreliable_keywords=total_keywords - reliable_keywords,
        total_api_calls=total_api_calls,
        total_cache_hits=total_cache_hits,
        cache_hit_ratio=round(cache_hit_ratio, 4),
        avg_sample_count=round(avg_sample_count, 2),
        avg_r_squared=round(avg_r_squared, 4) if avg_r_squared else None,
    )


@router.get("/{keyword}", response_model=KeywordParameterResponse)
async def get_parameter(
    keyword: str,
    db: AsyncSession = Depends(get_db)
):
    """
    특정 키워드의 파라미터 조회
    """
    param = await parameter_repository.get_by_keyword(db, keyword)

    if not param:
        raise HTTPException(
            status_code=404,
            detail=f"키워드 '{keyword}'의 파라미터가 없습니다."
        )

    return KeywordParameterResponse.model_validate(param)


@router.get("/{keyword}/calculate", response_model=CalculatedIndicesResponse)
async def calculate_indices(
    keyword: str,
    rank: int = Query(..., ge=1, le=300, description="순위"),
    db: AsyncSession = Depends(get_db)
):
    """
    캐싱된 파라미터로 N1, N2, N3 자체 계산

    - 파라미터가 없거나 신뢰도가 낮으면 에러
    """
    param = await parameter_repository.get_by_keyword(db, keyword)

    if not param:
        raise HTTPException(
            status_code=404,
            detail=f"키워드 '{keyword}'의 파라미터가 없습니다."
        )

    if not formula_calculator.can_calculate(param):
        raise HTTPException(
            status_code=400,
            detail=f"키워드 '{keyword}'의 파라미터가 신뢰할 수 없습니다. (샘플 수: {param.sample_count}, R²: {param.n2_r_squared})"
        )

    indices = formula_calculator.calculate_all_indices(param, rank)

    return CalculatedIndicesResponse(
        keyword=keyword,
        rank=rank,
        n1=round(indices["n1"], 4) if indices["n1"] else None,
        n2=round(indices["n2"], 4) if indices["n2"] else None,
        n3=round(indices["n3"], 4) if indices["n3"] else None,
        is_reliable=param.is_reliable,
    )


@router.delete("/{keyword}")
async def delete_parameter(
    keyword: str,
    db: AsyncSession = Depends(get_db)
):
    """
    특정 키워드의 파라미터 삭제 (관리자용)
    """
    param = await parameter_repository.get_by_keyword(db, keyword)

    if not param:
        raise HTTPException(
            status_code=404,
            detail=f"키워드 '{keyword}'의 파라미터가 없습니다."
        )

    await db.delete(param)
    await db.commit()

    logger.info(f"Deleted parameters for keyword: {keyword}")

    return {"success": True, "message": f"키워드 '{keyword}'의 파라미터가 삭제되었습니다."}
