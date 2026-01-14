"""
Formula Calculator 테스트
- N1 계산
- N2 회귀
- N3 계산: predictor.py와 일치 검증
"""
import pytest
from unittest.mock import MagicMock
from app.services.formula_calculator import FormulaCalculator
from app.ml.predictor import calculate_n3


@pytest.fixture
def calculator():
    return FormulaCalculator()


@pytest.fixture
def mock_params():
    """테스트용 모의 KeywordParameter"""
    params = MagicMock()
    params.keyword = "테스트키워드"
    params.n1_constant = 45.0
    params.n1_std = 0.5
    params.n2_slope = -5.0
    params.n2_intercept = 85.0
    params.n2_r_squared = 0.95
    params.sample_count = 50
    params.is_reliable = True
    return params


@pytest.fixture
def unreliable_params():
    """신뢰성 없는 파라미터"""
    params = MagicMock()
    params.keyword = "신뢰없음"
    params.n1_constant = None
    params.n1_std = None
    params.n2_slope = None
    params.n2_intercept = None
    params.n2_r_squared = None
    params.sample_count = 3
    params.is_reliable = False
    return params


class TestFormulaCalculator:
    """FormulaCalculator 테스트"""

    def test_calculate_n1(self, calculator, mock_params):
        """N1 계산 테스트"""
        n1 = calculator.calculate_n1(mock_params)

        assert n1 == 45.0

    def test_calculate_n2(self, calculator, mock_params):
        """N2 계산 테스트"""
        # N2 = -5.0 * rank + 85.0
        n2_rank1 = calculator.calculate_n2(mock_params, 1)
        n2_rank5 = calculator.calculate_n2(mock_params, 5)
        n2_rank10 = calculator.calculate_n2(mock_params, 10)

        assert n2_rank1 == 80.0  # -5*1 + 85 = 80
        assert n2_rank5 == 60.0  # -5*5 + 85 = 60
        assert n2_rank10 == 35.0  # -5*10 + 85 = 35

    def test_calculate_n2_clamping(self, calculator, mock_params):
        """N2 범위 클램핑 테스트"""
        # 아주 높은 순위로 음수가 나와야 할 때
        mock_params.n2_intercept = 50.0  # 낮은 intercept

        n2 = calculator.calculate_n2(mock_params, 100)  # -5*100 + 50 = -450

        # 0 이하가 되면 0으로 클램프
        assert n2 == 0.0

    def test_calculate_n3(self, calculator):
        """N3 계산 테스트"""
        # predictor.py의 공식과 동일한지 확인
        n3 = calculator.calculate_n3_from_params(45.0, 70.0)

        assert 0 <= n3 <= 100
        # 2차 다항식 공식으로 계산된 값이 유효한 범위인지만 확인
        assert n3 >= 0

    def test_calculate_n3_matches_predictor(self, calculator):
        """N3 계산이 predictor.py의 calculate_n3와 일치하는지 검증"""
        test_cases = [
            (45.0, 70.0),
            (30.0, 50.0),
            (60.0, 80.0),
            (10.0, 20.0),
            (90.0, 95.0),
        ]

        for n1, n2 in test_cases:
            # formula_calculator의 결과
            fc_n3 = calculator.calculate_n3_from_params(n1, n2)

            # predictor의 calculate_n3 직접 호출 (0-1 스케일 반환)
            pred_n3 = calculate_n3(n1, n2) * 100

            # 두 값이 일치해야 함 (부동소수점 오차 허용)
            assert abs(fc_n3 - pred_n3) < 0.0001, \
                f"N1={n1}, N2={n2}: FormulaCalculator={fc_n3}, Predictor={pred_n3}"

    def test_calculate_n3_edge_cases(self, calculator):
        """N3 계산 경계값 테스트"""
        # 최소값 테스트
        n3_min = calculator.calculate_n3_from_params(0, 0)
        assert 0 <= n3_min <= 100

        # 최대값 테스트
        n3_max = calculator.calculate_n3_from_params(100, 100)
        assert 0 <= n3_max <= 100

        # N1만 높은 경우
        n3_high_n1 = calculator.calculate_n3_from_params(90, 10)
        assert 0 <= n3_high_n1 <= 100

        # N2만 높은 경우
        n3_high_n2 = calculator.calculate_n3_from_params(10, 90)
        assert 0 <= n3_high_n2 <= 100

    def test_calculate_all_indices(self, calculator, mock_params):
        """전체 지수 계산 테스트"""
        indices = calculator.calculate_all_indices(mock_params, 3)

        assert indices["n1"] == 45.0
        assert indices["n2"] == 70.0  # -5*3 + 85 = 70
        assert indices["n3"] is not None
        assert 0 <= indices["n3"] <= 100

    def test_can_calculate_true(self, calculator, mock_params):
        """자체 계산 가능 여부 - True"""
        result = calculator.can_calculate(mock_params)
        assert result == True

    def test_can_calculate_false_no_params(self, calculator):
        """자체 계산 가능 여부 - 파라미터 없음"""
        result = calculator.can_calculate(None)
        assert result == False

    def test_can_calculate_false_unreliable(self, calculator, unreliable_params):
        """자체 계산 가능 여부 - 신뢰성 없음"""
        result = calculator.can_calculate(unreliable_params)
        assert result == False

    def test_generate_calculated_places(self, calculator, mock_params):
        """여러 순위 일괄 계산 테스트"""
        ranks = [1, 5, 10, 20, 50]
        results = calculator.generate_calculated_places(mock_params, ranks)

        assert len(results) == 5

        for i, result in enumerate(results):
            assert result["rank"] == ranks[i]
            assert result["n1"] == 45.0
            assert result["n2"] is not None
            assert result["n3"] is not None

        # 순위가 높을수록 N2는 낮아져야 함
        assert results[0]["n2"] > results[4]["n2"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
