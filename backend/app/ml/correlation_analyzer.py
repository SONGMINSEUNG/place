"""
Correlation Analyzer
사용자 활동과 순위 변화 간의 상관관계 분석 모듈

시계열 데이터를 기반으로:
- 블로그 리뷰 → 순위 변화 패턴
- 방문자 리뷰 → 순위 변화 패턴
- 저장수 → 순위 변화 패턴
- 유입수 → 순위 변화 패턴
등을 분석합니다.
"""
from typing import List, Dict, Optional, Tuple
from datetime import datetime, date, timedelta
from dataclasses import dataclass
import numpy as np
from scipy import stats
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession
import logging

from app.models.place import UserActivityLog

logger = logging.getLogger(__name__)


@dataclass
class ActivityEffect:
    """활동 효과 데이터"""
    activity_type: str
    sample_count: int
    total_amount: int

    # 상관계수
    correlation_rank_1d: Optional[float] = None
    correlation_rank_7d: Optional[float] = None
    correlation_n3_1d: Optional[float] = None
    correlation_n3_7d: Optional[float] = None

    # p-values
    p_value_rank_1d: Optional[float] = None
    p_value_rank_7d: Optional[float] = None
    p_value_n3_1d: Optional[float] = None
    p_value_n3_7d: Optional[float] = None

    # 평균 효과
    avg_rank_change_1d: Optional[float] = None
    avg_rank_change_7d: Optional[float] = None
    avg_n3_change_1d: Optional[float] = None
    avg_n3_change_7d: Optional[float] = None

    # 예측 공식 계수 (y = ax + b)
    rank_1d_slope: Optional[float] = None
    rank_1d_intercept: Optional[float] = None
    rank_7d_slope: Optional[float] = None
    rank_7d_intercept: Optional[float] = None


@dataclass
class KeywordAnalysisResult:
    """키워드별 분석 결과"""
    keyword: str
    sample_count: int
    activity_effects: List[ActivityEffect]
    best_activity_1d: Optional[str] = None
    best_activity_7d: Optional[str] = None
    recommendation: Optional[str] = None


class CorrelationAnalyzer:
    """
    사용자 활동-순위 상관관계 분석기

    시계열 데이터를 분석하여:
    1. 각 활동 유형별 순위 변화 상관관계 계산
    2. 활동량 vs 순위 변화 회귀분석
    3. 키워드별 최적 마케팅 전략 도출
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def analyze_all(
        self,
        keyword: Optional[str] = None,
        days: int = 90,
        min_samples: int = 5
    ) -> Dict:
        """
        전체 활동 상관관계 분석

        Args:
            keyword: 특정 키워드로 필터링 (None이면 전체)
            days: 분석할 기간 (일)
            min_samples: 최소 샘플 수

        Returns:
            분석 결과 딕셔너리
        """
        since_date = date.today() - timedelta(days=days)

        query = select(UserActivityLog).where(
            and_(
                UserActivityLog.activity_date >= since_date,
                UserActivityLog.rank_before.isnot(None),
            )
        )

        if keyword:
            query = query.where(UserActivityLog.keyword == keyword)

        result = await self.db.execute(query)
        logs = result.scalars().all()

        if len(logs) < min_samples:
            return {
                "success": False,
                "error": f"분석을 위한 데이터가 부족합니다. 최소 {min_samples}개 필요, 현재 {len(logs)}개",
                "sample_count": len(logs),
            }

        # 활동 유형별 분석
        effects = []

        # 블로그 리뷰
        blog_effect = self._analyze_activity(logs, "blog_review_added", "블로그 리뷰")
        if blog_effect:
            effects.append(blog_effect)

        # 방문자 리뷰
        visit_effect = self._analyze_activity(logs, "visit_review_added", "방문자 리뷰")
        if visit_effect:
            effects.append(visit_effect)

        # 저장수
        save_effect = self._analyze_activity(logs, "save_added", "저장수")
        if save_effect:
            effects.append(save_effect)

        # 유입수
        inflow_effect = self._analyze_activity(logs, "inflow_added", "유입수")
        if inflow_effect:
            effects.append(inflow_effect)

        # 최적 활동 찾기
        best_1d = self._find_best_activity(effects, "avg_rank_change_1d")
        best_7d = self._find_best_activity(effects, "avg_rank_change_7d")

        # 추천 문구 생성
        recommendation = self._generate_recommendation(effects, best_1d, best_7d)

        return {
            "success": True,
            "keyword": keyword,
            "period_days": days,
            "total_samples": len(logs),
            "samples_with_d1": len([l for l in logs if l.rank_after_1d is not None]),
            "samples_with_d7": len([l for l in logs if l.rank_after_7d is not None]),
            "effects": [self._effect_to_dict(e) for e in effects],
            "best_activity_1d": best_1d,
            "best_activity_7d": best_7d,
            "recommendation": recommendation,
            "analysis_date": datetime.now().isoformat(),
        }

    async def analyze_by_keyword(
        self,
        days: int = 90,
        min_samples: int = 3
    ) -> List[KeywordAnalysisResult]:
        """
        키워드별 분석

        Returns:
            키워드별 분석 결과 리스트
        """
        since_date = date.today() - timedelta(days=days)

        query = select(UserActivityLog).where(
            and_(
                UserActivityLog.activity_date >= since_date,
                UserActivityLog.rank_before.isnot(None),
            )
        )

        result = await self.db.execute(query)
        logs = result.scalars().all()

        # 키워드별 그룹핑
        keyword_logs: Dict[str, List] = {}
        for log in logs:
            if log.keyword not in keyword_logs:
                keyword_logs[log.keyword] = []
            keyword_logs[log.keyword].append(log)

        results = []
        for keyword, kw_logs in keyword_logs.items():
            if len(kw_logs) < min_samples:
                continue

            effects = []

            blog_effect = self._analyze_activity(kw_logs, "blog_review_added", "블로그 리뷰")
            if blog_effect:
                effects.append(blog_effect)

            visit_effect = self._analyze_activity(kw_logs, "visit_review_added", "방문자 리뷰")
            if visit_effect:
                effects.append(visit_effect)

            save_effect = self._analyze_activity(kw_logs, "save_added", "저장수")
            if save_effect:
                effects.append(save_effect)

            inflow_effect = self._analyze_activity(kw_logs, "inflow_added", "유입수")
            if inflow_effect:
                effects.append(inflow_effect)

            if effects:
                best_1d = self._find_best_activity(effects, "avg_rank_change_1d")
                best_7d = self._find_best_activity(effects, "avg_rank_change_7d")
                recommendation = self._generate_recommendation(effects, best_1d, best_7d)

                results.append(KeywordAnalysisResult(
                    keyword=keyword,
                    sample_count=len(kw_logs),
                    activity_effects=effects,
                    best_activity_1d=best_1d,
                    best_activity_7d=best_7d,
                    recommendation=recommendation,
                ))

        return results

    def predict_rank_change(
        self,
        effect: ActivityEffect,
        amount: int,
        days: int = 1
    ) -> Optional[float]:
        """
        활동량 기반 순위 변화 예측

        Args:
            effect: 활동 효과 데이터
            amount: 예상 활동량
            days: 1일 후 or 7일 후

        Returns:
            예상 순위 변화 (양수 = 상승)
        """
        if days == 1:
            if effect.rank_1d_slope is not None and effect.rank_1d_intercept is not None:
                return effect.rank_1d_slope * amount + effect.rank_1d_intercept
        elif days == 7:
            if effect.rank_7d_slope is not None and effect.rank_7d_intercept is not None:
                return effect.rank_7d_slope * amount + effect.rank_7d_intercept

        return None

    def _analyze_activity(
        self,
        logs: List[UserActivityLog],
        field_name: str,
        activity_name: str
    ) -> Optional[ActivityEffect]:
        """단일 활동 유형 분석"""

        # 해당 활동이 있는 로그만 필터링
        active_logs = [l for l in logs if getattr(l, field_name) > 0]

        if len(active_logs) < 2:
            return None

        amounts = [getattr(l, field_name) for l in active_logs]
        total_amount = sum(amounts)

        # D+1 순위 변화 분석
        rank_changes_1d = []
        amounts_1d = []
        for log in active_logs:
            if log.rank_before is not None and log.rank_after_1d is not None:
                change = log.rank_before - log.rank_after_1d  # 양수 = 상승
                rank_changes_1d.append(change)
                amounts_1d.append(getattr(log, field_name))

        # D+7 순위 변화 분석
        rank_changes_7d = []
        amounts_7d = []
        for log in active_logs:
            if log.rank_before is not None and log.rank_after_7d is not None:
                change = log.rank_before - log.rank_after_7d
                rank_changes_7d.append(change)
                amounts_7d.append(getattr(log, field_name))

        # N3 변화 분석
        n3_changes_1d = []
        n3_changes_7d = []
        for log in active_logs:
            if log.n3_before is not None and log.n3_after_1d is not None:
                n3_changes_1d.append(log.n3_after_1d - log.n3_before)
            if log.n3_before is not None and log.n3_after_7d is not None:
                n3_changes_7d.append(log.n3_after_7d - log.n3_before)

        effect = ActivityEffect(
            activity_type=activity_name,
            sample_count=len(active_logs),
            total_amount=total_amount,
        )

        # D+1 상관관계 및 회귀분석
        if len(amounts_1d) >= 3:
            corr, p_val = self._safe_pearsonr(amounts_1d, rank_changes_1d)
            effect.correlation_rank_1d = corr
            effect.p_value_rank_1d = p_val
            effect.avg_rank_change_1d = np.mean(rank_changes_1d)

            # 회귀분석
            slope, intercept = self._linear_regression(amounts_1d, rank_changes_1d)
            effect.rank_1d_slope = slope
            effect.rank_1d_intercept = intercept

        # D+7 상관관계 및 회귀분석
        if len(amounts_7d) >= 3:
            corr, p_val = self._safe_pearsonr(amounts_7d, rank_changes_7d)
            effect.correlation_rank_7d = corr
            effect.p_value_rank_7d = p_val
            effect.avg_rank_change_7d = np.mean(rank_changes_7d)

            slope, intercept = self._linear_regression(amounts_7d, rank_changes_7d)
            effect.rank_7d_slope = slope
            effect.rank_7d_intercept = intercept

        # N3 상관관계
        if len(n3_changes_1d) >= 3:
            corr, p_val = self._safe_pearsonr(amounts_1d[:len(n3_changes_1d)], n3_changes_1d)
            effect.correlation_n3_1d = corr
            effect.p_value_n3_1d = p_val
            effect.avg_n3_change_1d = np.mean(n3_changes_1d)

        if len(n3_changes_7d) >= 3:
            corr, p_val = self._safe_pearsonr(amounts_7d[:len(n3_changes_7d)], n3_changes_7d)
            effect.correlation_n3_7d = corr
            effect.p_value_n3_7d = p_val
            effect.avg_n3_change_7d = np.mean(n3_changes_7d)

        return effect

    def _safe_pearsonr(self, x: List[float], y: List[float]) -> Tuple[Optional[float], Optional[float]]:
        """안전한 피어슨 상관계수 계산"""
        try:
            if len(x) < 3 or len(y) < 3:
                return None, None
            corr, p_val = stats.pearsonr(x, y)
            return round(corr, 4), round(p_val, 4)
        except Exception:
            return None, None

    def _linear_regression(self, x: List[float], y: List[float]) -> Tuple[Optional[float], Optional[float]]:
        """선형 회귀분석"""
        try:
            if len(x) < 2:
                return None, None
            slope, intercept, _, _, _ = stats.linregress(x, y)
            return round(slope, 4), round(intercept, 4)
        except Exception:
            return None, None

    def _find_best_activity(
        self,
        effects: List[ActivityEffect],
        metric: str
    ) -> Optional[str]:
        """가장 효과적인 활동 찾기"""
        best_value = None
        best_activity = None

        for effect in effects:
            value = getattr(effect, metric)
            if value is not None:
                if best_value is None or value > best_value:
                    best_value = value
                    best_activity = effect.activity_type

        return best_activity

    def _generate_recommendation(
        self,
        effects: List[ActivityEffect],
        best_1d: Optional[str],
        best_7d: Optional[str]
    ) -> str:
        """추천 문구 생성"""
        parts = []

        # 유의미한 상관관계 찾기
        significant_effects = []
        for effect in effects:
            if effect.p_value_rank_1d is not None and effect.p_value_rank_1d < 0.05:
                if effect.correlation_rank_1d is not None and effect.correlation_rank_1d > 0.3:
                    significant_effects.append((effect.activity_type, "1일 후", effect.correlation_rank_1d))
            if effect.p_value_rank_7d is not None and effect.p_value_rank_7d < 0.05:
                if effect.correlation_rank_7d is not None and effect.correlation_rank_7d > 0.3:
                    significant_effects.append((effect.activity_type, "7일 후", effect.correlation_rank_7d))

        if significant_effects:
            for activity, period, corr in significant_effects:
                parts.append(f"{activity}와 {period} 순위 상승 간에 유의미한 상관관계가 있습니다 (r={corr:.2f}).")

        if best_1d:
            for effect in effects:
                if effect.activity_type == best_1d and effect.avg_rank_change_1d is not None:
                    if effect.avg_rank_change_1d > 0:
                        parts.append(f"단기적으로는 {best_1d} 활동이 평균 {effect.avg_rank_change_1d:.1f}순위 상승 효과를 보입니다.")

        if best_7d and best_7d != best_1d:
            for effect in effects:
                if effect.activity_type == best_7d and effect.avg_rank_change_7d is not None:
                    if effect.avg_rank_change_7d > 0:
                        parts.append(f"장기적으로는 {best_7d} 활동이 평균 {effect.avg_rank_change_7d:.1f}순위 상승 효과를 보입니다.")

        if not parts:
            return "아직 충분한 데이터가 수집되지 않아 유의미한 패턴을 발견하지 못했습니다. 지속적인 활동 기록이 필요합니다."

        return " ".join(parts)

    def _effect_to_dict(self, effect: ActivityEffect) -> dict:
        """ActivityEffect를 딕셔너리로 변환"""
        return {
            "activity_type": effect.activity_type,
            "sample_count": effect.sample_count,
            "total_amount": effect.total_amount,
            "correlation_rank_1d": effect.correlation_rank_1d,
            "correlation_rank_7d": effect.correlation_rank_7d,
            "correlation_n3_1d": effect.correlation_n3_1d,
            "correlation_n3_7d": effect.correlation_n3_7d,
            "p_value_rank_1d": effect.p_value_rank_1d,
            "p_value_rank_7d": effect.p_value_rank_7d,
            "avg_rank_change_1d": effect.avg_rank_change_1d,
            "avg_rank_change_7d": effect.avg_rank_change_7d,
            "avg_n3_change_1d": effect.avg_n3_change_1d,
            "avg_n3_change_7d": effect.avg_n3_change_7d,
            "prediction_formula_1d": f"순위변화 = {effect.rank_1d_slope:.4f} * 활동량 + {effect.rank_1d_intercept:.4f}"
                if effect.rank_1d_slope is not None else None,
            "prediction_formula_7d": f"순위변화 = {effect.rank_7d_slope:.4f} * 활동량 + {effect.rank_7d_intercept:.4f}"
                if effect.rank_7d_slope is not None else None,
        }


# 싱글톤 인스턴스 생성을 위한 팩토리 함수
async def get_correlation_analyzer(db: AsyncSession) -> CorrelationAnalyzer:
    """CorrelationAnalyzer 인스턴스 생성"""
    return CorrelationAnalyzer(db)
