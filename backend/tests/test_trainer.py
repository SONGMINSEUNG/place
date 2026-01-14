"""
KeywordTrainer 테스트
- N1 파라미터 계산
- N2 파라미터 회귀
- 키워드 학습
- 전체 키워드 학습
"""
import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from datetime import datetime

from app.ml.trainer import KeywordTrainer, MIN_SAMPLES, MIN_R_SQUARED


@pytest.fixture
def trainer():
    """KeywordTrainer 인스턴스"""
    return KeywordTrainer()


@pytest.fixture
def mock_training_data_valid():
    """유효한 학습 데이터 (10개 이상)"""
    data_list = []
    for i in range(15):
        data = MagicMock()
        data.rank = i + 1
        data.index_n1 = 45.0 + (i * 0.1)  # N1: 약간씩 변동
        data.index_n2 = 85.0 - (i * 3.0)  # N2: 순위에 따라 감소
        data.index_n3 = 60.0 + (i * 0.5)
        data.collected_at = datetime.utcnow()
        data_list.append(data)
    return data_list


@pytest.fixture
def mock_training_data_empty():
    """빈 학습 데이터"""
    return []


@pytest.fixture
def mock_training_data_insufficient():
    """부족한 학습 데이터 (2개)"""
    data_list = []
    for i in range(2):
        data = MagicMock()
        data.rank = i + 1
        data.index_n1 = 45.0
        data.index_n2 = 80.0 - (i * 5.0)
        data.index_n3 = 60.0
        data.collected_at = datetime.utcnow()
        data_list.append(data)
    return data_list


class TestCalculateN1FromData:
    """calculate_n1_from_data 테스트"""

    def test_calculate_n1_from_data_with_valid_data(self, trainer, mock_training_data_valid):
        """유효한 데이터로 N1 계산"""
        result = trainer.calculate_n1_from_data(mock_training_data_valid)

        assert result["n1_constant"] is not None
        assert result["n1_std"] is not None
        assert result["n1_constant"] > 0
        assert result["n1_std"] >= 0
        # N1 평균값이 대략 45 근처여야 함
        assert 44.0 < result["n1_constant"] < 47.0

    def test_calculate_n1_from_data_with_empty_data(self, trainer, mock_training_data_empty):
        """빈 데이터로 N1 계산 시 None 반환"""
        result = trainer.calculate_n1_from_data(mock_training_data_empty)

        assert result["n1_constant"] is None
        assert result["n1_std"] is None

    def test_calculate_n1_from_data_with_none_values(self, trainer):
        """N1 값이 None인 데이터"""
        data_list = []
        for i in range(5):
            data = MagicMock()
            data.index_n1 = None  # N1 값 없음
            data_list.append(data)

        result = trainer.calculate_n1_from_data(data_list)

        assert result["n1_constant"] is None
        assert result["n1_std"] is None

    def test_calculate_n1_from_data_with_zero_values(self, trainer):
        """N1 값이 0 이하인 데이터 (필터링됨)"""
        data_list = []
        for i in range(5):
            data = MagicMock()
            data.index_n1 = 0  # 0은 무시됨
            data_list.append(data)

        result = trainer.calculate_n1_from_data(data_list)

        assert result["n1_constant"] is None
        assert result["n1_std"] is None


class TestCalculateN2FromData:
    """calculate_n2_from_data 테스트"""

    def test_calculate_n2_from_data_with_regression(self, trainer, mock_training_data_valid):
        """유효한 데이터로 N2 회귀 분석"""
        result = trainer.calculate_n2_from_data(mock_training_data_valid)

        assert result["n2_slope"] is not None
        assert result["n2_intercept"] is not None
        assert result["n2_r_squared"] is not None
        # 순위가 올라갈수록 N2가 감소하므로 slope는 음수
        assert result["n2_slope"] < 0
        # R-squared는 0~1 사이
        assert 0 <= result["n2_r_squared"] <= 1

    def test_calculate_n2_from_data_insufficient_samples(self, trainer, mock_training_data_insufficient):
        """샘플이 부족한 경우 (3개 미만)"""
        result = trainer.calculate_n2_from_data(mock_training_data_insufficient)

        assert result["n2_slope"] is None
        assert result["n2_intercept"] is None
        assert result["n2_r_squared"] is None

    def test_calculate_n2_from_data_empty(self, trainer, mock_training_data_empty):
        """빈 데이터로 N2 계산"""
        result = trainer.calculate_n2_from_data(mock_training_data_empty)

        assert result["n2_slope"] is None
        assert result["n2_intercept"] is None
        assert result["n2_r_squared"] is None

    def test_calculate_n2_from_data_with_none_rank(self, trainer):
        """rank가 None인 데이터 (필터링됨)"""
        data_list = []
        for i in range(5):
            data = MagicMock()
            data.rank = None  # rank 없음
            data.index_n2 = 50.0
            data_list.append(data)

        result = trainer.calculate_n2_from_data(data_list)

        assert result["n2_slope"] is None


class TestTrainKeyword:
    """train_keyword 테스트"""

    @pytest.mark.asyncio
    async def test_train_keyword_success(self, trainer, mock_training_data_valid):
        """키워드 학습 성공"""
        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = mock_training_data_valid
        mock_db.execute.return_value = mock_result

        with patch('app.ml.trainer.parameter_repository') as mock_repo:
            mock_repo.save_or_update = AsyncMock()

            result = await trainer.train_keyword(mock_db, "테스트키워드")

        assert result["keyword"] == "테스트키워드"
        assert result["success"] is True
        assert result["sample_count"] == 15
        assert result["n1_constant"] is not None
        assert result["n2_slope"] is not None

    @pytest.mark.asyncio
    async def test_train_keyword_insufficient_samples(self, trainer):
        """샘플 부족 시 실패"""
        mock_db = AsyncMock()
        mock_result = MagicMock()
        # 5개 데이터만 반환 (MIN_SAMPLES=10 미만)
        mock_result.scalars.return_value.all.return_value = [MagicMock() for _ in range(5)]
        mock_db.execute.return_value = mock_result

        result = await trainer.train_keyword(mock_db, "테스트키워드")

        assert result["keyword"] == "테스트키워드"
        assert result["success"] is False
        assert "샘플 부족" in result["error"]
        assert result["sample_count"] == 5


class TestTrainAllKeywords:
    """train_all_keywords 테스트"""

    @pytest.mark.asyncio
    async def test_train_all_keywords(self, trainer, mock_training_data_valid):
        """전체 키워드 학습"""
        mock_db = AsyncMock()

        # get_all_keywords 모킹
        keywords_result = MagicMock()
        keywords_result.scalars.return_value.all.return_value = ["키워드1", "키워드2"]

        # get_training_data 모킹
        training_result = MagicMock()
        training_result.scalars.return_value.all.return_value = mock_training_data_valid

        mock_db.execute.side_effect = [keywords_result, training_result, training_result]

        with patch('app.ml.trainer.parameter_repository') as mock_repo:
            mock_repo.save_or_update = AsyncMock()

            result = await trainer.train_all_keywords(mock_db)

        assert result["success"] is True
        assert result["total_keywords"] == 2
        assert result["trained"] >= 0
        assert result["duration_seconds"] >= 0

    @pytest.mark.asyncio
    async def test_train_all_keywords_no_keywords(self, trainer):
        """학습할 키워드가 없는 경우"""
        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []  # 키워드 없음
        mock_db.execute.return_value = mock_result

        result = await trainer.train_all_keywords(mock_db)

        assert result["success"] is True
        assert result["total_keywords"] == 0
        assert result["trained"] == 0
        assert "No keywords to train" in result.get("message", "")


class TestTrainerConfiguration:
    """Trainer 설정 테스트"""

    def test_default_min_samples(self, trainer):
        """기본 최소 샘플 수"""
        assert trainer.min_samples == MIN_SAMPLES
        assert trainer.min_samples == 10

    def test_default_min_r_squared(self, trainer):
        """기본 최소 R-squared"""
        assert trainer.min_r_squared == MIN_R_SQUARED
        assert trainer.min_r_squared == 0.3


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
