"""
ML Predictor Service
점수 예측 및 시뮬레이션 계산

N3 = f(N1, N2) 공식 (분석 결과 기반)
Type A: N3 = -0.255112*N1 - 0.137087*N2 + 0.932150*N1*N2 + 0.381767
"""
from typing import Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)


def calculate_n3(n1: float, n2: float) -> float:
    """
    N1, N2로 N3 계산

    Args:
        n1: 키워드지수 (0-1 스케일)
        n2: 품질점수 (0-1 스케일)

    Returns:
        N3 종합경쟁력 (0-1 스케일)
    """
    # N1, N2를 0-1 스케일로 변환 (100점 만점 -> 0-1)
    n1_scaled = n1 / 100.0 if n1 > 1 else n1
    n2_scaled = n2 / 100.0 if n2 > 1 else n2

    n3 = -0.255112 * n1_scaled - 0.137087 * n2_scaled + 0.932150 * n1_scaled * n2_scaled + 0.381767

    # 0-1 범위로 클램프
    n3 = max(0.0, min(1.0, n3))

    return n3


def calculate_n3_change(n1: float, current_n2: float, predicted_n2: float) -> float:
    """
    N2 변화에 따른 N3 변화량 계산

    Args:
        n1: 키워드지수 (0-100 스케일)
        current_n2: 현재 품질점수 (0-100 스케일)
        predicted_n2: 예측 품질점수 (0-100 스케일)

    Returns:
        N3 변화량 (0-100 스케일)
    """
    current_n3 = calculate_n3(n1, current_n2)
    predicted_n3 = calculate_n3(n1, predicted_n2)

    # 100점 스케일로 반환
    return (predicted_n3 - current_n3) * 100


class PredictionService:
    """점수 예측 및 시뮬레이션 서비스"""

    # 기본 계수 (학습 전 초기값)
    # 실제로는 DB의 model_features 테이블에서 로드
    DEFAULT_COEFFICIENTS = {
        "inflow": 0.000234,        # 유입수 1명당 효과
        "reservation": 0.000912,   # 예약수 1건당 효과
        "blog_review": 0.002143,   # 블로그 리뷰 1개당 효과
        "visit_review": 0.000598,  # 방문자 리뷰 1개당 효과
    }

    # 추천 전략 기본 수량
    RECOMMENDED_AMOUNTS = {
        "inflow": {"amount": 100, "unit": "명"},
        "reservation": {"amount": 20, "unit": "건"},
        "blog_review": {"amount": 15, "unit": "개"},
        "visit_review": {"amount": 50, "unit": "개"},
    }

    def __init__(self):
        self.coefficients = self.DEFAULT_COEFFICIENTS.copy()
        self.model_loaded = False

    def load_model(self, coefficients: Optional[Dict[str, float]] = None):
        """모델 계수 로드"""
        if coefficients:
            self.coefficients.update(coefficients)
            self.model_loaded = True
            logger.info("Model coefficients loaded")

    def calculate_effect(
        self,
        feature: str,
        amount: int
    ) -> float:
        """
        특정 항목의 점수 효과 계산

        Args:
            feature: 항목명 (inflow, reservation, blog_review, visit_review)
            amount: 증가량

        Returns:
            예상 점수 증가량 (소수점 4자리)
        """
        coef = self.coefficients.get(feature, 0)
        effect = amount * coef * 100  # N2 스케일 → 0-100 스케일
        return round(effect, 4)

    def simulate(
        self,
        current_score: float,
        inputs: Dict[str, int],
        n1: Optional[float] = None,
        current_n3_actual: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        시뮬레이션 실행

        Args:
            current_score: 현재 품질점수 (N2)
            inputs: {inflow: 150, reservation: 25, blog_review: 10, visit_review: 30}
            n1: 현재 키워드지수 (N3 계산용, 없으면 N3 계산 안함)
            current_n3_actual: 실제 API에서 받아온 현재 N3 값 (0-100 스케일)

        Returns:
            시뮬레이션 결과 (N2 및 N3 변화량 포함)
        """
        effects = {}
        total_effect = 0.0

        for feature, amount in inputs.items():
            if feature in self.coefficients and amount > 0:
                effect = self.calculate_effect(feature, amount)
                effects[feature] = {
                    "amount": amount,
                    "effect": effect
                }
                total_effect += effect

        predicted_score = round(current_score + total_effect, 4)

        result = {
            "current_score": current_score,
            "effects": effects,
            "total_effect": round(total_effect, 4),
            "predicted_score": predicted_score,
        }

        # N1이 제공되면 N3 변화량도 계산
        if n1 is not None:
            # 현재 N3: 실제 API 값이 있으면 사용, 없으면 공식으로 계산
            if current_n3_actual is not None:
                current_n3 = current_n3_actual  # 실제 API 값 사용 (이미 0-100 스케일)
            else:
                current_n3 = calculate_n3(n1, current_score) * 100  # 공식으로 계산

            # 예측 N3: N2 증가분에 비례하여 N3도 증가한다고 가정
            # N2 변화에 따른 N3 변화 비율 계산
            current_n3_calc = calculate_n3(n1, current_score) * 100
            predicted_n3_calc = calculate_n3(n1, predicted_score) * 100
            n3_change_ratio = predicted_n3_calc - current_n3_calc

            # 실제 현재 N3에 변화량 적용
            predicted_n3 = current_n3 + n3_change_ratio
            n3_change = n3_change_ratio

            result["current_n3"] = round(current_n3, 4)
            result["predicted_n3"] = round(predicted_n3, 4)
            result["n3_change"] = round(n3_change, 4)

        return result

    def generate_recommendations(
        self,
        current_score: float,
        target_score: Optional[float] = None,
        current_n1: Optional[float] = None
    ) -> list:
        """
        마케팅 제언 생성

        Args:
            current_score: 현재 품질점수 (N2)
            target_score: 목표 점수 (1위 점수)
            current_n1: 현재 키워드지수 (N3 효과 계산용)

        Returns:
            추천 전략 리스트 (N3 상승 효과 포함)
        """
        recommendations = []

        for feature, info in self.RECOMMENDED_AMOUNTS.items():
            amount = info["amount"]
            unit = info["unit"]
            effect = self.calculate_effect(feature, amount)

            # 한글 타입명 변환
            type_names = {
                "inflow": "유입수",
                "reservation": "예약수",
                "blog_review": "블로그리뷰",
                "visit_review": "방문자리뷰",
            }

            rec = {
                "type": type_names.get(feature, feature),
                "amount": amount,
                "unit": unit,
                "effect": effect,
                "description": f"N2(품질점수) +{effect:.2f}점 상승",
            }

            # N1이 있으면 N3 효과도 계산
            if current_n1 is not None:
                predicted_score = current_score + effect
                current_n3 = calculate_n3(current_n1, current_score) * 100
                predicted_n3 = calculate_n3(current_n1, predicted_score) * 100
                n3_effect = predicted_n3 - current_n3
                rec["n3_effect"] = round(n3_effect, 4)
                rec["description"] = f"N3(경쟁력) +{n3_effect:.2f}점 상승 → 순위 상승 기대"

            recommendations.append(rec)

        # 효과 높은 순으로 정렬
        recommendations.sort(key=lambda x: x["effect"], reverse=True)

        return recommendations

    def estimate_rank(
        self,
        predicted_score: float,
        competitors: list,
        use_n3: bool = False,
        my_n1: Optional[float] = None
    ) -> int:
        """
        예상 순위 계산 (N3 기준)

        Args:
            predicted_score: 예측 품질점수 (N2)
            competitors: 경쟁사 목록 (scores 포함)
            use_n3: N3 기준으로 순위 계산 여부
            my_n1: 내 키워드지수 (N3 계산용)

        Returns:
            예상 순위
        """
        if use_n3 and my_n1 is not None:
            # N3 기준으로 순위 계산
            my_predicted_n3 = calculate_n3(my_n1, predicted_score) * 100

            # 경쟁사들의 N3 점수 목록
            competitor_n3_scores = []
            for c in competitors:
                c_n1 = c.get("scores", {}).get("keyword_score", 0)
                c_n2 = c.get("scores", {}).get("quality_score", 0)
                c_n3 = calculate_n3(c_n1, c_n2) * 100
                competitor_n3_scores.append(c_n3)

            # 내 예측 N3도 추가
            all_n3_scores = competitor_n3_scores + [my_predicted_n3]

            # 내림차순 정렬 후 순위 찾기
            all_n3_scores.sort(reverse=True)
            rank = all_n3_scores.index(my_predicted_n3) + 1
        else:
            # 기존 N2 기준 순위 계산
            scores = [c.get("scores", {}).get("quality_score", 0) for c in competitors]
            scores.append(predicted_score)

            # 내림차순 정렬 후 순위 찾기
            scores.sort(reverse=True)
            rank = scores.index(predicted_score) + 1

        return rank


# 싱글톤 인스턴스
predictor = PredictionService()
