"""
Activity API
사용자 마케팅 활동 로그 및 효과 분석 엔드포인트
"""
from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime, date, timedelta
from typing import List, Optional
from pydantic import BaseModel, Field
import numpy as np
from scipy import stats

from app.models.place import UserActivityLog
from app.services.adlog_proxy import adlog_service, AdlogApiError
from app.core.database import get_db
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/activity")


# ===========================================
# Request/Response Schemas
# ===========================================

class ActivityLogRequest(BaseModel):
    """활동 기록 요청"""
    keyword: str = Field(..., description="검색 키워드")
    place_id: Optional[str] = Field(None, description="플레이스 ID")
    place_name: Optional[str] = Field(None, description="업체명")
    activity_date: Optional[date] = Field(None, description="활동 날짜 (기본: 오늘)")
    blog_review_added: int = Field(0, ge=0, description="추가한 블로그 리뷰 수")
    visit_review_added: int = Field(0, ge=0, description="추가한 방문자 리뷰 수")
    save_added: int = Field(0, ge=0, description="증가한 저장수")
    inflow_added: int = Field(0, ge=0, description="증가한 유입수")


class ActivityLogResponse(BaseModel):
    """활동 기록 응답"""
    success: bool
    log_id: int
    keyword: str
    place_name: Optional[str]
    activity_date: date
    blog_review_added: int
    visit_review_added: int
    save_added: int
    inflow_added: int
    rank_before: Optional[int]
    n3_before: Optional[float]
    created_at: datetime


class ActivityHistoryItem(BaseModel):
    """활동 히스토리 항목"""
    id: int
    keyword: str
    place_name: Optional[str]
    activity_date: date
    blog_review_added: int
    visit_review_added: int
    save_added: int
    inflow_added: int
    rank_before: Optional[int]
    n3_before: Optional[float]
    rank_after_1d: Optional[int]
    n3_after_1d: Optional[float]
    rank_after_7d: Optional[int]
    n3_after_7d: Optional[float]
    rank_change_1d: Optional[int] = None
    rank_change_7d: Optional[int] = None
    created_at: datetime


class ActivityHistoryResponse(BaseModel):
    """활동 히스토리 응답"""
    total: int
    data: List[ActivityHistoryItem]


class EffectByActivity(BaseModel):
    """활동별 효과"""
    activity_type: str
    total_added: int
    sample_count: int
    avg_rank_change_1d: Optional[float]
    avg_rank_change_7d: Optional[float]
    avg_n3_change_1d: Optional[float]
    avg_n3_change_7d: Optional[float]


class EffectAnalysisResponse(BaseModel):
    """효과 분석 응답"""
    total_logs: int
    logs_with_result: int
    effects: List[EffectByActivity]
    interpretation: str
    analysis_date: datetime


# ===========================================
# API Endpoints
# ===========================================

@router.post("/log", response_model=ActivityLogResponse)
async def log_activity(
    request: ActivityLogRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    사용자 마케팅 활동 기록 API

    오늘 수행한 마케팅 활동을 기록합니다:
    - 블로그 리뷰 작성/의뢰
    - 방문자 리뷰 유도
    - 저장수 증가 활동
    - 유입수 증가 활동

    기록 시점의 순위/N3 점수도 함께 저장하여 효과 분석에 활용합니다.
    """
    try:
        activity_date = request.activity_date or date.today()

        # 현재 순위/지수 가져오기
        rank_before = None
        n1_before = None
        n2_before = None
        n3_before = None

        try:
            raw_data = await adlog_service.fetch_keyword_analysis(request.keyword)
            places = raw_data.get("places", [])

            for place in places:
                place_match = False
                if request.place_id and place.get("place_id") == request.place_id:
                    place_match = True
                elif request.place_name and request.place_name.lower() in place.get("name", "").lower():
                    place_match = True

                if place_match:
                    raw_indices = place.get("raw_indices", {})
                    rank_before = place.get("rank")
                    n1_before = raw_indices.get("n1")
                    n2_before = raw_indices.get("n2")
                    n3_before = raw_indices.get("n3")
                    break

        except AdlogApiError as e:
            logger.warning(f"ADLOG API error while fetching current data: {str(e)}")

        # 활동 로그 저장
        activity_log = UserActivityLog(
            keyword=request.keyword,
            place_id=request.place_id,
            place_name=request.place_name,
            activity_date=activity_date,
            blog_review_added=request.blog_review_added,
            visit_review_added=request.visit_review_added,
            save_added=request.save_added,
            inflow_added=request.inflow_added,
            rank_before=rank_before,
            n1_before=n1_before,
            n2_before=n2_before,
            n3_before=n3_before,
        )

        db.add(activity_log)
        await db.commit()
        await db.refresh(activity_log)

        logger.info(f"Activity logged: keyword={request.keyword}, date={activity_date}")

        return ActivityLogResponse(
            success=True,
            log_id=activity_log.id,
            keyword=activity_log.keyword,
            place_name=activity_log.place_name,
            activity_date=activity_log.activity_date,
            blog_review_added=activity_log.blog_review_added,
            visit_review_added=activity_log.visit_review_added,
            save_added=activity_log.save_added,
            inflow_added=activity_log.inflow_added,
            rank_before=activity_log.rank_before,
            n3_before=activity_log.n3_before,
            created_at=activity_log.created_at,
        )

    except Exception as e:
        logger.error(f"Error logging activity: {str(e)}")
        raise HTTPException(status_code=500, detail="활동 기록 중 오류가 발생했습니다.")


@router.get("/history", response_model=ActivityHistoryResponse)
async def get_activity_history(
    keyword: Optional[str] = None,
    place_id: Optional[str] = None,
    days: int = 30,
    limit: int = 100,
    db: AsyncSession = Depends(get_db)
):
    """
    활동 히스토리 조회 API

    기록된 마케팅 활동과 그 결과(D+1, D+7 순위 변화)를 조회합니다.
    """
    try:
        since_date = date.today() - timedelta(days=days)

        query = select(UserActivityLog).where(
            UserActivityLog.activity_date >= since_date
        ).order_by(UserActivityLog.activity_date.desc()).limit(limit)

        if keyword:
            query = query.where(UserActivityLog.keyword == keyword)
        if place_id:
            query = query.where(UserActivityLog.place_id == place_id)

        result = await db.execute(query)
        logs = result.scalars().all()

        history_items = []
        for log in logs:
            rank_change_1d = None
            rank_change_7d = None

            if log.rank_before is not None:
                if log.rank_after_1d is not None:
                    rank_change_1d = log.rank_before - log.rank_after_1d  # 양수면 순위 상승
                if log.rank_after_7d is not None:
                    rank_change_7d = log.rank_before - log.rank_after_7d

            history_items.append(ActivityHistoryItem(
                id=log.id,
                keyword=log.keyword,
                place_name=log.place_name,
                activity_date=log.activity_date,
                blog_review_added=log.blog_review_added,
                visit_review_added=log.visit_review_added,
                save_added=log.save_added,
                inflow_added=log.inflow_added,
                rank_before=log.rank_before,
                n3_before=log.n3_before,
                rank_after_1d=log.rank_after_1d,
                n3_after_1d=log.n3_after_1d,
                rank_after_7d=log.rank_after_7d,
                n3_after_7d=log.n3_after_7d,
                rank_change_1d=rank_change_1d,
                rank_change_7d=rank_change_7d,
                created_at=log.created_at,
            ))

        return ActivityHistoryResponse(
            total=len(history_items),
            data=history_items,
        )

    except Exception as e:
        logger.error(f"Error fetching activity history: {str(e)}")
        raise HTTPException(status_code=500, detail="히스토리 조회 중 오류가 발생했습니다.")


@router.get("/effect-analysis", response_model=EffectAnalysisResponse)
async def get_effect_analysis(
    keyword: Optional[str] = None,
    days: int = 90,
    db: AsyncSession = Depends(get_db)
):
    """
    활동별 효과 분석 API

    수집된 활동 데이터를 바탕으로 각 마케팅 활동이
    순위/N3 점수에 미치는 영향을 분석합니다.
    """
    try:
        since_date = date.today() - timedelta(days=days)

        query = select(UserActivityLog).where(
            and_(
                UserActivityLog.activity_date >= since_date,
                UserActivityLog.rank_before.isnot(None),
            )
        )

        if keyword:
            query = query.where(UserActivityLog.keyword == keyword)

        result = await db.execute(query)
        logs = result.scalars().all()

        total_logs = len(logs)
        logs_with_result = len([l for l in logs if l.rank_after_1d is not None or l.rank_after_7d is not None])

        # 활동 유형별 효과 계산
        effects = []

        # 블로그 리뷰 효과
        blog_logs = [l for l in logs if l.blog_review_added > 0]
        if blog_logs:
            blog_effect = _calculate_activity_effect(blog_logs, "blog_review_added")
            blog_effect["activity_type"] = "블로그 리뷰"
            effects.append(EffectByActivity(**blog_effect))

        # 방문자 리뷰 효과
        visit_logs = [l for l in logs if l.visit_review_added > 0]
        if visit_logs:
            visit_effect = _calculate_activity_effect(visit_logs, "visit_review_added")
            visit_effect["activity_type"] = "방문자 리뷰"
            effects.append(EffectByActivity(**visit_effect))

        # 저장수 효과
        save_logs = [l for l in logs if l.save_added > 0]
        if save_logs:
            save_effect = _calculate_activity_effect(save_logs, "save_added")
            save_effect["activity_type"] = "저장수"
            effects.append(EffectByActivity(**save_effect))

        # 유입수 효과
        inflow_logs = [l for l in logs if l.inflow_added > 0]
        if inflow_logs:
            inflow_effect = _calculate_activity_effect(inflow_logs, "inflow_added")
            inflow_effect["activity_type"] = "유입수"
            effects.append(EffectByActivity(**inflow_effect))

        # 해석 생성
        interpretation = _generate_interpretation(effects, logs_with_result)

        return EffectAnalysisResponse(
            total_logs=total_logs,
            logs_with_result=logs_with_result,
            effects=effects,
            interpretation=interpretation,
            analysis_date=datetime.now(),
        )

    except Exception as e:
        logger.error(f"Error in effect analysis: {str(e)}")
        raise HTTPException(status_code=500, detail="효과 분석 중 오류가 발생했습니다.")


@router.post("/update-results")
async def update_activity_results(
    db: AsyncSession = Depends(get_db)
):
    """
    D+1, D+7 결과 업데이트 (배치용)

    기록된 활동의 결과를 업데이트합니다.
    - D+1: 활동일 기준 1일 후 순위/N3
    - D+7: 활동일 기준 7일 후 순위/N3
    """
    try:
        today = date.today()
        updated_count = 0

        # D+1 업데이트 대상 조회 (어제 활동, 아직 D+1 미측정)
        d1_target_date = today - timedelta(days=1)
        d1_query = select(UserActivityLog).where(
            and_(
                UserActivityLog.activity_date == d1_target_date,
                UserActivityLog.rank_after_1d.is_(None),
            )
        )

        result = await db.execute(d1_query)
        d1_logs = result.scalars().all()

        for log in d1_logs:
            try:
                raw_data = await adlog_service.fetch_keyword_analysis(log.keyword)
                places = raw_data.get("places", [])

                for place in places:
                    place_match = False
                    if log.place_id and place.get("place_id") == log.place_id:
                        place_match = True
                    elif log.place_name and log.place_name.lower() in place.get("name", "").lower():
                        place_match = True

                    if place_match:
                        raw_indices = place.get("raw_indices", {})
                        log.rank_after_1d = place.get("rank")
                        log.n3_after_1d = raw_indices.get("n3")
                        log.measured_at_1d = datetime.now()
                        updated_count += 1
                        break

            except AdlogApiError:
                pass

        # D+7 업데이트 대상 조회 (7일 전 활동, 아직 D+7 미측정)
        d7_target_date = today - timedelta(days=7)
        d7_query = select(UserActivityLog).where(
            and_(
                UserActivityLog.activity_date == d7_target_date,
                UserActivityLog.rank_after_7d.is_(None),
            )
        )

        result = await db.execute(d7_query)
        d7_logs = result.scalars().all()

        for log in d7_logs:
            try:
                raw_data = await adlog_service.fetch_keyword_analysis(log.keyword)
                places = raw_data.get("places", [])

                for place in places:
                    place_match = False
                    if log.place_id and place.get("place_id") == log.place_id:
                        place_match = True
                    elif log.place_name and log.place_name.lower() in place.get("name", "").lower():
                        place_match = True

                    if place_match:
                        raw_indices = place.get("raw_indices", {})
                        log.rank_after_7d = place.get("rank")
                        log.n3_after_7d = raw_indices.get("n3")
                        log.measured_at_7d = datetime.now()
                        updated_count += 1
                        break

            except AdlogApiError:
                pass

        await db.commit()

        return {
            "success": True,
            "updated_count": updated_count,
            "d1_processed": len(d1_logs),
            "d7_processed": len(d7_logs),
        }

    except Exception as e:
        logger.error(f"Error updating activity results: {str(e)}")
        raise HTTPException(status_code=500, detail="결과 업데이트 중 오류가 발생했습니다.")


# ===========================================
# Helper Functions
# ===========================================

def _calculate_activity_effect(logs: List[UserActivityLog], field_name: str) -> dict:
    """활동별 효과 계산"""
    total_added = sum(getattr(log, field_name) for log in logs)
    sample_count = len(logs)

    # D+1 순위 변화 (양수 = 순위 상승)
    rank_changes_1d = []
    n3_changes_1d = []
    for log in logs:
        if log.rank_before is not None and log.rank_after_1d is not None:
            rank_changes_1d.append(log.rank_before - log.rank_after_1d)
        if log.n3_before is not None and log.n3_after_1d is not None:
            n3_changes_1d.append(log.n3_after_1d - log.n3_before)

    # D+7 순위 변화
    rank_changes_7d = []
    n3_changes_7d = []
    for log in logs:
        if log.rank_before is not None and log.rank_after_7d is not None:
            rank_changes_7d.append(log.rank_before - log.rank_after_7d)
        if log.n3_before is not None and log.n3_after_7d is not None:
            n3_changes_7d.append(log.n3_after_7d - log.n3_before)

    return {
        "total_added": total_added,
        "sample_count": sample_count,
        "avg_rank_change_1d": round(np.mean(rank_changes_1d), 2) if rank_changes_1d else None,
        "avg_rank_change_7d": round(np.mean(rank_changes_7d), 2) if rank_changes_7d else None,
        "avg_n3_change_1d": round(np.mean(n3_changes_1d), 4) if n3_changes_1d else None,
        "avg_n3_change_7d": round(np.mean(n3_changes_7d), 4) if n3_changes_7d else None,
    }


def _generate_interpretation(effects: List[EffectByActivity], logs_with_result: int) -> str:
    """분석 결과 해석 생성"""
    if logs_with_result < 5:
        return f"아직 결과가 측정된 데이터가 부족합니다 ({logs_with_result}개). 더 많은 활동을 기록하고 D+1, D+7 결과가 누적되면 정확한 분석이 가능합니다."

    interpretations = []

    # 가장 효과적인 활동 찾기
    best_effect_1d = None
    best_activity_1d = None

    for effect in effects:
        if effect.avg_rank_change_1d is not None:
            if best_effect_1d is None or effect.avg_rank_change_1d > best_effect_1d:
                best_effect_1d = effect.avg_rank_change_1d
                best_activity_1d = effect.activity_type

    if best_activity_1d and best_effect_1d is not None:
        if best_effect_1d > 0:
            interpretations.append(f"{best_activity_1d} 활동이 가장 효과적입니다 (평균 {best_effect_1d:.1f}순위 상승).")
        elif best_effect_1d < 0:
            interpretations.append(f"현재 데이터에서는 단기 순위 상승이 관찰되지 않았습니다.")

    # D+7 장기 효과
    best_effect_7d = None
    best_activity_7d = None

    for effect in effects:
        if effect.avg_rank_change_7d is not None:
            if best_effect_7d is None or effect.avg_rank_change_7d > best_effect_7d:
                best_effect_7d = effect.avg_rank_change_7d
                best_activity_7d = effect.activity_type

    if best_activity_7d and best_effect_7d is not None and best_effect_7d > 0:
        interpretations.append(f"7일 후 기준으로는 {best_activity_7d}가 평균 {best_effect_7d:.1f}순위 상승 효과를 보입니다.")

    if not interpretations:
        return "아직 충분한 데이터가 수집되지 않았습니다. 지속적인 활동 기록으로 패턴을 분석해보세요."

    return " ".join(interpretations)
