"""
Parameter Extractor Service
ADLOG API 응답에서 N1, N2, N3 파라미터를 추출하여 저장

- N1: 키워드별 고정 상수 (평균값)
- N2: rank와 선형 관계 (slope, intercept)
- N3: N2와 선형 관계 (slope, intercept) - 99.97% 정확도
"""
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime
from scipy import stats
import numpy as np
import logging

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.place import KeywordParameter

logger = logging.getLogger(__name__)

# 신뢰성 판단 기준
MIN_SAMPLE_COUNT = 10  # 최소 샘플 수
MIN_R_SQUARED = 0.3    # N2 회귀 최소 결정계수


class ParameterExtractor:
    """ADLOG API 응답에서 파라미터 추출"""

    def extract_n1_parameters(
        self,
        places: List[Dict[str, Any]]
    ) -> Tuple[Optional[float], Optional[float]]:
        """
        N1 파라미터 추출 (평균값 및 표준편차)

        Args:
            places: ADLOG API 응답의 places 배열

        Returns:
            (n1_constant, n1_std) 튜플
        """
        n1_values = []

        for place in places:
            raw_indices = place.get("raw_indices", {})
            n1 = raw_indices.get("n1")

            if n1 is not None and n1 > 0:
                n1_values.append(n1)

        if not n1_values:
            logger.warning("No valid N1 values found")
            return None, None

        n1_constant = float(np.mean(n1_values))
        n1_std = float(np.std(n1_values)) if len(n1_values) > 1 else 0.0

        logger.info(f"N1 extracted: mean={n1_constant:.4f}, std={n1_std:.4f}, count={len(n1_values)}")
        return n1_constant, n1_std

    def extract_n2_parameters(
        self,
        places: List[Dict[str, Any]]
    ) -> Tuple[Optional[float], Optional[float], Optional[float]]:
        """
        N2 파라미터 추출 (선형 회귀: N2 = slope * rank + intercept)

        Args:
            places: ADLOG API 응답의 places 배열

        Returns:
            (slope, intercept, r_squared) 튜플
        """
        ranks = []
        n2_values = []

        for place in places:
            rank = place.get("rank")
            raw_indices = place.get("raw_indices", {})
            n2 = raw_indices.get("n2")

            if rank is not None and n2 is not None and rank > 0:
                ranks.append(rank)
                n2_values.append(n2)

        if len(ranks) < 3:
            logger.warning(f"Not enough data points for N2 regression: {len(ranks)} points")
            return None, None, None

        try:
            # scipy.stats.linregress 사용
            slope, intercept, r_value, p_value, std_err = stats.linregress(ranks, n2_values)

            r_squared = r_value ** 2

            logger.info(
                f"N2 regression: slope={slope:.6f}, intercept={intercept:.4f}, "
                f"R²={r_squared:.4f}, count={len(ranks)}"
            )

            return float(slope), float(intercept), float(r_squared)

        except Exception as e:
            logger.error(f"N2 regression failed: {str(e)}")
            return None, None, None

    def extract_n3_parameters(
        self,
        places: List[Dict[str, Any]]
    ) -> Tuple[Optional[float], Optional[float], Optional[float]]:
        """
        N3 파라미터 추출 (선형 회귀: N3 = slope * N2 + intercept)

        N3는 N2와 선형 관계 (99.97% 정확도)

        Args:
            places: ADLOG API 응답의 places 배열

        Returns:
            (slope, intercept, r_squared) 튜플
        """
        n2_values = []
        n3_values = []

        for place in places:
            raw_indices = place.get("raw_indices", {})
            n2 = raw_indices.get("n2")
            n3 = raw_indices.get("n3")

            if n2 is not None and n3 is not None and n2 > 0:
                n2_values.append(n2)
                n3_values.append(n3)

        if len(n2_values) < 3:
            logger.warning(f"Not enough data points for N3 regression: {len(n2_values)} points")
            return None, None, None

        try:
            # scipy.stats.linregress 사용: N3 = slope * N2 + intercept
            slope, intercept, r_value, p_value, std_err = stats.linregress(n2_values, n3_values)

            r_squared = r_value ** 2

            logger.info(
                f"N3 regression: slope={slope:.6f}, intercept={intercept:.4f}, "
                f"R²={r_squared:.4f}, count={len(n2_values)}"
            )

            return float(slope), float(intercept), float(r_squared)

        except Exception as e:
            logger.error(f"N3 regression failed: {str(e)}")
            return None, None, None

    def extract_from_adlog_response(
        self,
        keyword: str,
        places: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        ADLOG API 응답에서 모든 파라미터 추출

        Args:
            keyword: 검색 키워드
            places: ADLOG API 응답의 places 배열

        Returns:
            추출된 파라미터 딕셔너리
        """
        # N1 추출
        n1_constant, n1_std = self.extract_n1_parameters(places)

        # N2 추출
        n2_slope, n2_intercept, n2_r_squared = self.extract_n2_parameters(places)

        # N3 추출 (N3 = slope * N2 + intercept)
        n3_slope, n3_intercept, n3_r_squared = self.extract_n3_parameters(places)

        # 샘플 수
        sample_count = len(places)

        # 신뢰성 판단
        is_reliable = (
            sample_count >= MIN_SAMPLE_COUNT and
            n1_constant is not None and
            n2_slope is not None and
            n2_r_squared is not None and
            n2_r_squared >= MIN_R_SQUARED and
            n3_slope is not None and
            n3_r_squared is not None
        )

        result = {
            "keyword": keyword,
            "n1_constant": n1_constant,
            "n1_std": n1_std,
            "n2_slope": n2_slope,
            "n2_intercept": n2_intercept,
            "n2_r_squared": n2_r_squared,
            "n3_slope": n3_slope,
            "n3_intercept": n3_intercept,
            "n3_r_squared": n3_r_squared,
            "sample_count": sample_count,
            "is_reliable": is_reliable,
            "last_trained_at": datetime.utcnow(),
        }

        logger.info(f"Parameters extracted for '{keyword}': reliable={is_reliable}")
        return result


class ParameterRepository:
    """KeywordParameter DB 저장소"""

    async def get_by_keyword(
        self,
        db: AsyncSession,
        keyword: str
    ) -> Optional[KeywordParameter]:
        """키워드로 파라미터 조회"""
        result = await db.execute(
            select(KeywordParameter).where(KeywordParameter.keyword == keyword)
        )
        return result.scalar_one_or_none()

    async def save_or_update(
        self,
        db: AsyncSession,
        params: Dict[str, Any]
    ) -> KeywordParameter:
        """
        파라미터 저장 또는 업데이트

        Args:
            db: DB 세션
            params: 파라미터 딕셔너리

        Returns:
            저장된 KeywordParameter 객체
        """
        keyword = params["keyword"]

        # 기존 레코드 조회
        existing = await self.get_by_keyword(db, keyword)

        if existing:
            # 기존 레코드 업데이트
            existing.n1_constant = params.get("n1_constant")
            existing.n1_std = params.get("n1_std")
            existing.n2_slope = params.get("n2_slope")
            existing.n2_intercept = params.get("n2_intercept")
            existing.n2_r_squared = params.get("n2_r_squared")
            existing.n3_slope = params.get("n3_slope")
            existing.n3_intercept = params.get("n3_intercept")
            existing.n3_r_squared = params.get("n3_r_squared")
            existing.sample_count = params.get("sample_count", 0)
            existing.last_trained_at = params.get("last_trained_at")
            existing.is_reliable = params.get("is_reliable", False)
            existing.api_call_count = (existing.api_call_count or 0) + 1
            existing.updated_at = datetime.utcnow()

            logger.info(f"Updated parameters for keyword: {keyword}")
            return existing
        else:
            # 새 레코드 생성
            new_param = KeywordParameter(
                keyword=keyword,
                n1_constant=params.get("n1_constant"),
                n1_std=params.get("n1_std"),
                n2_slope=params.get("n2_slope"),
                n2_intercept=params.get("n2_intercept"),
                n2_r_squared=params.get("n2_r_squared"),
                n3_slope=params.get("n3_slope"),
                n3_intercept=params.get("n3_intercept"),
                n3_r_squared=params.get("n3_r_squared"),
                sample_count=params.get("sample_count", 0),
                last_trained_at=params.get("last_trained_at"),
                api_call_count=1,
                cache_hit_count=0,
                is_reliable=params.get("is_reliable", False),
            )
            db.add(new_param)

            logger.info(f"Created new parameters for keyword: {keyword}")
            return new_param

    async def increment_cache_hit(
        self,
        db: AsyncSession,
        keyword: str
    ) -> None:
        """캐시 히트 카운트 증가"""
        param = await self.get_by_keyword(db, keyword)
        if param:
            param.cache_hit_count = (param.cache_hit_count or 0) + 1


# 싱글톤 인스턴스
parameter_extractor = ParameterExtractor()
parameter_repository = ParameterRepository()
