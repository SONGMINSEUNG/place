"""
Parameter Extractor 테스트
"""
import pytest
from app.services.parameter_extractor import ParameterExtractor


@pytest.fixture
def extractor():
    return ParameterExtractor()


@pytest.fixture
def sample_places():
    """테스트용 샘플 places 데이터"""
    return [
        {
            "place_id": "1",
            "name": "테스트 업체 1",
            "rank": 1,
            "raw_indices": {"n1": 45.2, "n2": 78.5, "n3": 65.0},
            "metrics": {"blog_count": 100, "visit_count": 500, "save_count": 200}
        },
        {
            "place_id": "2",
            "name": "테스트 업체 2",
            "rank": 2,
            "raw_indices": {"n1": 44.8, "n2": 72.3, "n3": 60.0},
            "metrics": {"blog_count": 80, "visit_count": 400, "save_count": 150}
        },
        {
            "place_id": "3",
            "name": "테스트 업체 3",
            "rank": 3,
            "raw_indices": {"n1": 45.0, "n2": 68.1, "n3": 55.0},
            "metrics": {"blog_count": 60, "visit_count": 300, "save_count": 100}
        },
        {
            "place_id": "4",
            "name": "테스트 업체 4",
            "rank": 4,
            "raw_indices": {"n1": 45.5, "n2": 62.0, "n3": 50.0},
            "metrics": {"blog_count": 40, "visit_count": 200, "save_count": 80}
        },
        {
            "place_id": "5",
            "name": "테스트 업체 5",
            "rank": 5,
            "raw_indices": {"n1": 44.9, "n2": 55.8, "n3": 45.0},
            "metrics": {"blog_count": 20, "visit_count": 100, "save_count": 50}
        },
    ]


class TestParameterExtractor:
    """ParameterExtractor 테스트"""

    def test_extract_n1_parameters(self, extractor, sample_places):
        """N1 파라미터 추출 테스트"""
        n1_constant, n1_std = extractor.extract_n1_parameters(sample_places)

        assert n1_constant is not None
        assert n1_std is not None
        assert 44.0 < n1_constant < 46.0  # 대략 45 근처
        assert n1_std >= 0

    def test_extract_n1_parameters_empty(self, extractor):
        """빈 데이터 N1 추출 테스트"""
        n1_constant, n1_std = extractor.extract_n1_parameters([])

        assert n1_constant is None
        assert n1_std is None

    def test_extract_n2_parameters(self, extractor, sample_places):
        """N2 파라미터 추출 테스트"""
        slope, intercept, r_squared = extractor.extract_n2_parameters(sample_places)

        assert slope is not None
        assert intercept is not None
        assert r_squared is not None

        # N2는 rank가 증가하면 감소해야 함 (음의 기울기)
        assert slope < 0

        # R² 는 0-1 사이
        assert 0 <= r_squared <= 1

    def test_extract_n2_parameters_insufficient_data(self, extractor):
        """데이터 부족 시 N2 추출 테스트"""
        places = [
            {"rank": 1, "raw_indices": {"n2": 80}},
            {"rank": 2, "raw_indices": {"n2": 70}},
        ]

        slope, intercept, r_squared = extractor.extract_n2_parameters(places)

        # 데이터가 3개 미만이면 None 반환
        assert slope is None
        assert intercept is None
        assert r_squared is None

    def test_extract_from_adlog_response(self, extractor, sample_places):
        """전체 파라미터 추출 테스트"""
        result = extractor.extract_from_adlog_response("테스트키워드", sample_places)

        assert result["keyword"] == "테스트키워드"
        assert result["n1_constant"] is not None
        assert result["n2_slope"] is not None
        assert result["n2_intercept"] is not None
        assert result["sample_count"] == 5
        assert result["last_trained_at"] is not None

    def test_reliability_check(self, extractor):
        """신뢰성 체크 테스트"""
        # 10개 이상의 샘플로 신뢰성 있는 데이터 생성
        places = []
        for i in range(15):
            places.append({
                "place_id": str(i+1),
                "name": f"테스트 업체 {i+1}",
                "rank": i+1,
                "raw_indices": {"n1": 45.0 + (i * 0.1), "n2": 80 - (i * 2), "n3": 70 - i},
            })

        result = extractor.extract_from_adlog_response("신뢰성테스트", places)

        # 샘플 수가 10개 이상이고 R²가 충분히 높으면 신뢰할 수 있음
        assert result["sample_count"] >= 10
        assert result["is_reliable"] == True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
