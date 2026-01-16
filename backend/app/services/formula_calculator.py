"""
Formula Calculator Service
캐싱된 파라미터로 N1, N2, N3를 자체 계산

- N1: 키워드별 고정 상수
- N2: slope * rank + intercept
- N3: slope * N2 + intercept (선형 공식, 99.97% 정확도)
"""
from typing import Dict, Any, Optional, List
from app.models.place import KeywordParameter
import logging

logger = logging.getLogger(__name__)


class FormulaCalculator:
    """캐싱된 파라미터로 지수 계산"""

    def calculate_n1(
        self,
        params: KeywordParameter
    ) -> Optional[float]:
        """
        N1 계산 (키워드별 상수)

        Args:
            params: 키워드 파라미터

        Returns:
            N1 값 (0-1 스케일)
        """
        if params.n1_constant is None:
            return None
        return params.n1_constant

    def calculate_n2(
        self,
        params: KeywordParameter,
        rank: int
    ) -> Optional[float]:
        """
        N2 계산 (선형 회귀)

        N2 = slope * rank + intercept

        Args:
            params: 키워드 파라미터
            rank: 순위

        Returns:
            N2 값 (0-1 스케일, 표시용으로 100 곱해서 사용)
        """
        if params.n2_slope is None or params.n2_intercept is None:
            return None

        n2 = params.n2_slope * rank + params.n2_intercept

        # 0-1 범위로 클램프
        n2 = max(0.0, min(1.0, n2))

        return n2

    def calculate_n3_from_params(
        self,
        params: KeywordParameter,
        n2: float
    ) -> Optional[float]:
        """
        N3 계산 (선형 공식, 99.97% 정확도)

        N3 = n3_slope * N2 + n3_intercept

        Args:
            params: 키워드 파라미터 (n3_slope, n3_intercept 포함)
            n2: 품질점수 (0-1 스케일)

        Returns:
            N3 값 (0-1 스케일)
        """
        if params.n3_slope is None or params.n3_intercept is None:
            return None

        n3 = params.n3_slope * n2 + params.n3_intercept

        # 0-1 범위로 클램프
        n3 = max(0.0, min(1.0, n3))

        return n3

    def calculate_all_indices(
        self,
        params: KeywordParameter,
        rank: int
    ) -> Dict[str, Optional[float]]:
        """
        모든 지수 계산

        Args:
            params: 키워드 파라미터
            rank: 순위

        Returns:
            {"n1": float, "n2": float, "n3": float} (0-100 스케일로 변환하여 반환)
        """
        # N1은 이미 0-1 스케일
        n1_raw = self.calculate_n1(params)
        # N2도 0-1 스케일
        n2_raw = self.calculate_n2(params, rank)

        n3_raw = None
        if n2_raw is not None:
            # N3 = n3_slope * N2 + n3_intercept (0-1 스케일)
            n3_raw = self.calculate_n3_from_params(params, n2_raw)

        # 0-100 스케일로 변환하여 반환
        return {
            "n1": n1_raw * 100 if n1_raw is not None else None,
            "n2": n2_raw * 100 if n2_raw is not None else None,
            "n3": n3_raw * 100 if n3_raw is not None else None,
        }

    def generate_calculated_places(
        self,
        params: KeywordParameter,
        ranks: List[int]
    ) -> List[Dict[str, Any]]:
        """
        여러 순위에 대한 지수 일괄 계산

        Args:
            params: 키워드 파라미터
            ranks: 순위 리스트

        Returns:
            [{"rank": int, "n1": float, "n2": float, "n3": float}, ...]
        """
        results = []

        for rank in ranks:
            indices = self.calculate_all_indices(params, rank)
            results.append({
                "rank": rank,
                **indices,
            })

        return results

    def can_calculate(
        self,
        params: Optional[KeywordParameter]
    ) -> bool:
        """
        자체 계산 가능 여부 확인

        Args:
            params: 키워드 파라미터

        Returns:
            자체 계산 가능 여부
        """
        if params is None:
            return False

        # N1, N2, N3 파라미터가 모두 있어야 함
        has_n1 = params.n1_constant is not None
        has_n2 = (
            params.n2_slope is not None and
            params.n2_intercept is not None
        )
        has_n3 = (
            params.n3_slope is not None and
            params.n3_intercept is not None
        )

        # 신뢰성 있는 데이터여야 함
        is_reliable = params.is_reliable

        return has_n1 and has_n2 and has_n3 and is_reliable


# 싱글톤 인스턴스
formula_calculator = FormulaCalculator()
