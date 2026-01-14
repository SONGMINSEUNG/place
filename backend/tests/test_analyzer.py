"""
ModelAnalyzer 테스트
- 정확도 분석
- 리포트 생성
- 예측값 vs 실제값 비교
"""
import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from datetime import datetime

from app.ml.analyzer import ModelAnalyzer


@pytest.fixture
def analyzer():
    """ModelAnalyzer 인스턴스"""
    return ModelAnalyzer()


@pytest.fixture
def mock_params():
    """테스트용 KeywordParameter"""
    params = MagicMock()
    params.keyword = "테스트키워드"
    params.n1_constant = 45.0
    params.n1_std = 0.5
    params.n2_slope = -3.0
    params.n2_intercept = 85.0
    params.n2_r_squared = 0.92
    params.sample_count = 50
    params.is_reliable = True
    return params


@pytest.fixture
def mock_training_data():
    """테스트용 학습 데이터"""
    data_list = []
    for i in range(10):
        data = MagicMock()
        data.rank = i + 1
        data.place_name = f"테스트장소{i+1}"
        data.index_n1 = 45.0 + (i * 0.1)
        data.index_n2 = 82.0 - (i * 3.0)  # slope=-3, intercept=85에 가까운 값
        data.index_n3 = 60.0 + (i * 0.5)
        data.collected_at = datetime.utcnow()
        data_list.append(data)
    return data_list


class TestAnalyzeAccuracy:
    """analyze_accuracy 테스트"""

    @pytest.mark.asyncio
    async def test_analyze_accuracy_with_valid_data(self, analyzer, mock_params, mock_training_data):
        """유효한 데이터로 정확도 분석"""
        mock_db = AsyncMock()

        # training data 조회 모킹
        training_result = MagicMock()
        training_result.scalars.return_value.all.return_value = mock_training_data
        mock_db.execute.return_value = training_result

        with patch('app.ml.analyzer.parameter_repository') as mock_repo, \
             patch('app.ml.analyzer.formula_calculator') as mock_calc:
            mock_repo.get_by_keyword = AsyncMock(return_value=mock_params)
            mock_calc.can_calculate.return_value = True
            mock_calc.calculate_all_indices.return_value = {
                "n1": 45.0,
                "n2": 80.0,
                "n3": 65.0
            }

            result = await analyzer.analyze_accuracy(mock_db, "테스트키워드")

        assert result["keyword"] == "테스트키워드"
        assert result["success"] is True
        assert result["sample_count"] == 10
        assert result["is_reliable"] is True
        assert "analyzed_at" in result

    @pytest.mark.asyncio
    async def test_analyze_accuracy_with_no_params(self, analyzer):
        """파라미터가 없는 경우"""
        mock_db = AsyncMock()

        with patch('app.ml.analyzer.parameter_repository') as mock_repo:
            mock_repo.get_by_keyword = AsyncMock(return_value=None)

            result = await analyzer.analyze_accuracy(mock_db, "없는키워드")

        assert result["keyword"] == "없는키워드"
        assert result["success"] is False
        assert "파라미터가 없습니다" in result["error"]

    @pytest.mark.asyncio
    async def test_analyze_accuracy_with_unreliable_params(self, analyzer):
        """신뢰할 수 없는 파라미터"""
        mock_db = AsyncMock()
        unreliable_params = MagicMock()
        unreliable_params.is_reliable = False

        with patch('app.ml.analyzer.parameter_repository') as mock_repo, \
             patch('app.ml.analyzer.formula_calculator') as mock_calc:
            mock_repo.get_by_keyword = AsyncMock(return_value=unreliable_params)
            mock_calc.can_calculate.return_value = False

            result = await analyzer.analyze_accuracy(mock_db, "테스트키워드")

        assert result["success"] is False
        assert result["is_reliable"] is False

    @pytest.mark.asyncio
    async def test_analyze_accuracy_with_insufficient_data(self, analyzer, mock_params):
        """데이터가 부족한 경우 (3개 미만)"""
        mock_db = AsyncMock()

        # 2개 데이터만 반환
        insufficient_data = [MagicMock() for _ in range(2)]
        training_result = MagicMock()
        training_result.scalars.return_value.all.return_value = insufficient_data
        mock_db.execute.return_value = training_result

        with patch('app.ml.analyzer.parameter_repository') as mock_repo, \
             patch('app.ml.analyzer.formula_calculator') as mock_calc:
            mock_repo.get_by_keyword = AsyncMock(return_value=mock_params)
            mock_calc.can_calculate.return_value = True

            result = await analyzer.analyze_accuracy(mock_db, "테스트키워드")

        assert result["success"] is False
        assert "데이터 부족" in result["error"]


class TestCalculateMetrics:
    """_calculate_metrics 테스트"""

    def test_calculate_metrics_valid(self, analyzer):
        """유효한 데이터로 메트릭 계산"""
        actual = [100.0, 90.0, 80.0, 70.0, 60.0]
        predicted = [98.0, 88.0, 82.0, 72.0, 58.0]

        result = analyzer._calculate_metrics(actual, predicted, "N2")

        assert result is not None
        assert result["name"] == "N2"
        assert result["count"] == 5
        assert "mae" in result
        assert "rmse" in result
        assert "r_squared" in result
        assert 0 <= result["r_squared"] <= 1

    def test_calculate_metrics_insufficient_data(self, analyzer):
        """데이터 부족 시 None 반환"""
        actual = [100.0, 90.0]  # 2개만
        predicted = [98.0, 88.0]

        result = analyzer._calculate_metrics(actual, predicted, "N2")

        assert result is None

    def test_calculate_metrics_perfect_prediction(self, analyzer):
        """완벽한 예측 시 R-squared = 1"""
        actual = [100.0, 90.0, 80.0, 70.0, 60.0]
        predicted = [100.0, 90.0, 80.0, 70.0, 60.0]  # 동일

        result = analyzer._calculate_metrics(actual, predicted, "N2")

        assert result is not None
        assert result["mae"] == 0.0
        assert result["rmse"] == 0.0
        assert result["r_squared"] == 1.0


class TestGenerateReport:
    """generate_report 테스트"""

    @pytest.mark.asyncio
    async def test_generate_report(self, analyzer, mock_params, mock_training_data):
        """전체 리포트 생성"""
        mock_db = AsyncMock()

        # reliable params 조회
        params_result = MagicMock()
        params_result.scalars.return_value.all.return_value = [mock_params]

        # training data 조회
        training_result = MagicMock()
        training_result.scalars.return_value.all.return_value = mock_training_data

        mock_db.execute.side_effect = [params_result, training_result]

        with patch('app.ml.analyzer.parameter_repository') as mock_repo, \
             patch('app.ml.analyzer.formula_calculator') as mock_calc:
            mock_repo.get_by_keyword = AsyncMock(return_value=mock_params)
            mock_calc.can_calculate.return_value = True
            mock_calc.calculate_all_indices.return_value = {
                "n1": 45.0,
                "n2": 80.0,
                "n3": 65.0
            }

            result = await analyzer.generate_report(mock_db)

        assert result["success"] is True
        assert result["total_keywords"] == 1
        assert "generated_at" in result
        assert "duration_seconds" in result

    @pytest.mark.asyncio
    async def test_generate_report_no_reliable_params(self, analyzer):
        """신뢰할 수 있는 파라미터가 없는 경우"""
        mock_db = AsyncMock()

        params_result = MagicMock()
        params_result.scalars.return_value.all.return_value = []  # 없음
        mock_db.execute.return_value = params_result

        result = await analyzer.generate_report(mock_db)

        assert result["success"] is True
        assert result["total_keywords"] == 0
        assert "No reliable parameters to analyze" in result.get("message", "")


class TestGetKeywordComparison:
    """get_keyword_comparison 테스트"""

    @pytest.mark.asyncio
    async def test_get_keyword_comparison_success(self, analyzer, mock_params, mock_training_data):
        """키워드별 비교 데이터 조회 성공"""
        mock_db = AsyncMock()

        training_result = MagicMock()
        training_result.scalars.return_value.all.return_value = mock_training_data
        mock_db.execute.return_value = training_result

        with patch('app.ml.analyzer.parameter_repository') as mock_repo, \
             patch('app.ml.analyzer.formula_calculator') as mock_calc:
            mock_repo.get_by_keyword = AsyncMock(return_value=mock_params)
            mock_calc.can_calculate.return_value = True
            mock_calc.calculate_all_indices.return_value = {
                "n1": 45.0,
                "n2": 80.0,
                "n3": 65.0
            }

            result = await analyzer.get_keyword_comparison(mock_db, "테스트키워드", limit=5)

        assert result["success"] is True
        assert result["keyword"] == "테스트키워드"
        assert "comparisons" in result
        assert "parameters" in result

    @pytest.mark.asyncio
    async def test_get_keyword_comparison_no_params(self, analyzer):
        """파라미터가 없는 경우"""
        mock_db = AsyncMock()

        with patch('app.ml.analyzer.parameter_repository') as mock_repo, \
             patch('app.ml.analyzer.formula_calculator') as mock_calc:
            mock_repo.get_by_keyword = AsyncMock(return_value=None)
            mock_calc.can_calculate.return_value = False

            result = await analyzer.get_keyword_comparison(mock_db, "없는키워드")

        assert result["success"] is False
        assert "유효한 파라미터가 없습니다" in result["error"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
