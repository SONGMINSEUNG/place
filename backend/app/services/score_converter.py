"""
Score Converter Service
N1, N2, N3를 단순 변환 (원본 값 * 100)

수정 사항:
- 키워드마다 N2, N3 범위가 다르므로 고정 범위 변환 제거
- 단순히 원본 값 * 100으로 변환 (마이너스 값 방지)
- 예: N2 = 0.267 → 26.7점, N3 = 0.368 → 36.8점
"""
from typing import Dict, Any


class ScoreConverter:
    """ADLOG 지수를 0-100 점수로 변환 (단순 변환)"""

    @staticmethod
    def convert_n2_to_quality_score(n2: float) -> float:
        """
        N2 → 품질점수 (단순 변환)

        공식: N2 * 100

        예시:
        - N2 = 0.267000 → 26.7000점
        - N2 = 0.558677 → 55.8677점
        """
        score = n2 * 100
        return round(score, 4)

    @staticmethod
    def convert_n1_to_keyword_score(n1: float) -> float:
        """
        N1 → 키워드지수 (단순 변환)

        공식: N1 * 100
        예시: 0.366894 → 36.6894점
        """
        return round(n1 * 100, 4)

    @staticmethod
    def convert_n3_to_competition_score(n3: float) -> float:
        """
        N3 → 종합경쟁력 (단순 변환)

        공식: N3 * 100
        N3는 순위 결정 지수, N3 내림차순 = 순위

        예시: 0.368945 → 36.8945점
        """
        score = n3 * 100
        return round(score, 4)

    @staticmethod
    def convert_all(n1: float, n2: float, n3: float) -> Dict[str, float]:
        """모든 지수를 한번에 변환"""
        return {
            "quality_score": ScoreConverter.convert_n2_to_quality_score(n2),
            "keyword_score": ScoreConverter.convert_n1_to_keyword_score(n1),
            "competition_score": ScoreConverter.convert_n3_to_competition_score(n3),
        }

    @staticmethod
    def calculate_gap(my_score: float, target_score: float) -> float:
        """점수 차이 계산"""
        return round(target_score - my_score, 4)

    @staticmethod
    def quality_score_to_n2(quality_score: float) -> float:
        """품질점수 → N2 역변환 (시뮬레이션용)"""
        n2 = quality_score / 100
        return round(n2, 6)

    @staticmethod
    def get_raw_indices(n1: float, n2: float, n3: float) -> Dict[str, float]:
        """원본 지수 반환 (디버깅/표시용)"""
        return {
            "n1": round(n1, 6),
            "n2": round(n2, 6),
            "n3": round(n3, 6),
        }


class PlaceDataTransformer:
    """업체 데이터 전체 변환"""

    @staticmethod
    def transform_place(place: Dict[str, Any]) -> Dict[str, Any]:
        """단일 업체 데이터 변환"""
        raw = place.get("raw_indices", {})
        n1 = raw.get("n1", 0)
        n2 = raw.get("n2", 0)
        n3 = raw.get("n3", 0)

        scores = ScoreConverter.convert_all(n1, n2, n3)

        return {
            "place_id": place.get("place_id"),
            "name": place.get("name"),
            "rank": place.get("rank"),
            "scores": scores,
            "raw_indices": ScoreConverter.get_raw_indices(n1, n2, n3),
            "metrics": place.get("metrics"),
            "changes": {
                "rank_change": place.get("changes", {}).get("rank_change", 0),
                "score_change": round(
                    place.get("changes", {}).get("n2_change", 0) * 100, 4
                ),
            }
        }

    @staticmethod
    def transform_all_places(places: list) -> list:
        """모든 업체 데이터 변환"""
        return [PlaceDataTransformer.transform_place(p) for p in places]

    @staticmethod
    def find_rank_1(places: list) -> Dict[str, Any]:
        """1위 업체 찾기"""
        for place in places:
            if place.get("rank") == 1:
                return place
        return places[0] if places else None


# 싱글톤 인스턴스
score_converter = ScoreConverter()
place_transformer = PlaceDataTransformer()
