"""
Score Converter Service
N1, N2, N3를 자체 점수 체계로 변환 (원본 값 * 137)

- 자체 점수 체계: ADLOG 원본 * 137
- 소수점 끝자리까지 유지하여 업체 간 미세 변동 확인 가능
- 예: N2 = 0.267000 → 36.579점, N3 = 0.369452 → 50.614724점
"""
from typing import Dict, Any

SCORE_MULTIPLIER = 137


class ScoreConverter:
    """ADLOG 지수를 자체 점수로 변환 (* 137)"""

    @staticmethod
    def convert_n2_to_quality_score(n2: float) -> float:
        """N2 → 품질점수"""
        if n2 >= 1.5:
            return n2 * (SCORE_MULTIPLIER / 100)
        return n2 * SCORE_MULTIPLIER

    @staticmethod
    def convert_n1_to_keyword_score(n1: float) -> float:
        """N1 → 키워드지수"""
        if n1 >= 1.5:
            return n1 * (SCORE_MULTIPLIER / 100)
        return n1 * SCORE_MULTIPLIER

    @staticmethod
    def convert_n3_to_competition_score(n3: float) -> float:
        """N3 → 종합경쟁력"""
        if n3 >= 1.5:
            return n3 * (SCORE_MULTIPLIER / 100)
        return n3 * SCORE_MULTIPLIER

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
        return target_score - my_score

    @staticmethod
    def quality_score_to_n2(quality_score: float) -> float:
        """품질점수 → N2 역변환 (시뮬레이션용)"""
        return quality_score / SCORE_MULTIPLIER

    @staticmethod
    def get_raw_indices(n1: float, n2: float, n3: float) -> Dict[str, float]:
        """원본 지수 반환 (디버깅/표시용)"""
        return {
            "n1": n1,
            "n2": n2,
            "n3": n3,
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
                "score_change": place.get("changes", {}).get("n2_change", 0) * SCORE_MULTIPLIER,
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
