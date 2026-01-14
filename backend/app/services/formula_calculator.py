"""
Formula Calculator Service
캐싱된 파라미터로 N1, N2, N3를 자체 계산

- N1: 키워드별 고정 상수
- N2: slope * rank + intercept
- N3: 2차 다항식 공식 (predictor.py와 동일)
"""
from typing import Dict, Any, Optional, List
from app.models.place import KeywordParameter
from app.ml.predictor import calculate_n3
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
            N1 값 (0-100 스케일)
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
            N2 값 (0-100 스케일)
        """
        if params.n2_slope is None or params.n2_intercept is None:
            return None

        n2 = params.n2_slope * rank + params.n2_intercept

        # 0-100 범위로 클램프
        n2 = max(0.0, min(100.0, n2))

        return n2

    def calculate_n3_from_params(
        self,
        n1: float,
        n2: float
    ) -> float:
        """
        N3 계산 (2차 다항식 공식)

        predictor.py의 calculate_n3 함수 사용
        N3 = -0.288554 + 3.350482*N1 + 0.159362*N2 + 0.438085*N1*N2
             - 3.715231*N1^2 - 0.851072*N2^2

        Args:
            n1: 키워드지수 (0-100 스케일)
            n2: 품질점수 (0-100 스케일)

        Returns:
            N3 값 (0-100 스케일)
        """
        # calculate_n3는 0-1 스케일 반환, 100 곱해서 반환
        n3 = calculate_n3(n1, n2) * 100
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
            {"n1": float, "n2": float, "n3": float}
        """
        n1 = self.calculate_n1(params)
        n2 = self.calculate_n2(params, rank)

        n3 = None
        if n1 is not None and n2 is not None:
            n3 = self.calculate_n3_from_params(n1, n2)

        return {
            "n1": n1,
            "n2": n2,
            "n3": n3,
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

        # N1, N2 파라미터가 모두 있어야 함
        has_n1 = params.n1_constant is not None
        has_n2 = (
            params.n2_slope is not None and
            params.n2_intercept is not None
        )

        # 신뢰성 있는 데이터여야 함
        is_reliable = params.is_reliable

        return has_n1 and has_n2 and is_reliable


# 싱글톤 인스턴스
formula_calculator = FormulaCalculator()
