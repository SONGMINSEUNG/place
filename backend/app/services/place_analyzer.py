import asyncio
import math
from typing import Dict, List, Any, Optional, Tuple
from app.services.naver_place import NaverPlaceService
import logging

logger = logging.getLogger(__name__)


def calculate_correlation(x: List[float], y: List[float]) -> float:
    """피어슨 상관계수 계산"""
    n = len(x)
    if n < 3 or len(y) != n:
        return 0.0

    mean_x = sum(x) / n
    mean_y = sum(y) / n

    numerator = sum((xi - mean_x) * (yi - mean_y) for xi, yi in zip(x, y))

    sum_sq_x = sum((xi - mean_x) ** 2 for xi in x)
    sum_sq_y = sum((yi - mean_y) ** 2 for yi in y)

    denominator = math.sqrt(sum_sq_x * sum_sq_y)

    if denominator == 0:
        return 0.0

    return numerator / denominator


class PlaceAnalyzer:
    """플레이스 분석 서비스"""

    def __init__(self):
        self.naver_service = NaverPlaceService()

    def calculate_hidden_scores(
        self,
        place_data: Dict[str, Any],
        keyword: str = "",
        rank: int = None,
        total_places: int = None
    ) -> Dict[str, Any]:
        """
        히든 지수 계산 (N1, N2, N3)

        - N1: 기본 플레이스 지수 (리뷰, 저장 등 기본 지표)
        - N2: 관련성 지수 (키워드 매칭, 카테고리, 정보 완성도)
        - N3: 랭킹 지수 (해당 키워드에서의 순위 기반)
        """
        # N1: 기본 지수 (인기도 기반)
        visitor_reviews = place_data.get("visitor_review_count", 0)
        blog_reviews = place_data.get("blog_review_count", 0)
        save_count = place_data.get("save_count", 0)
        reservation_reviews = place_data.get("reservation_review_count", 0)

        # 로그 스케일로 정규화 (0~1 범위)
        import math

        def log_normalize(value: int, max_expected: int) -> float:
            if value <= 0:
                return 0.0
            return min(math.log10(value + 1) / math.log10(max_expected + 1), 1.0)

        n1_visitor = log_normalize(visitor_reviews, 10000) * 0.35
        n1_blog = log_normalize(blog_reviews, 1000) * 0.25
        n1_save = log_normalize(save_count, 5000) * 0.25
        n1_reservation = log_normalize(reservation_reviews, 500) * 0.15

        n1 = n1_visitor + n1_blog + n1_save + n1_reservation

        # N2: 관련성 지수
        n2_keyword_match = 0.0
        n2_info_complete = 0.0
        n2_category = 0.0

        # 키워드 매칭 점수
        if keyword:
            name = place_data.get("name", "").lower()
            category = place_data.get("category", "").lower()
            keywords_list = place_data.get("keywords", []) or []
            keyword_lower = keyword.lower()

            # 상호명에 키워드 포함
            if keyword_lower in name:
                n2_keyword_match += 0.4
            # 카테고리에 키워드 포함
            if keyword_lower in category:
                n2_keyword_match += 0.3
            # 대표 키워드에 포함
            if any(keyword_lower in kw.lower() for kw in keywords_list):
                n2_keyword_match += 0.3
        else:
            n2_keyword_match = 0.5  # 키워드 없으면 중간값

        # 정보 완성도 점수
        info_fields = [
            place_data.get("phone"),
            place_data.get("address") or place_data.get("road_address"),
            place_data.get("business_hours"),
            place_data.get("menu_info"),
            place_data.get("description"),
            place_data.get("thumbnail_url")
        ]
        filled_count = sum(1 for f in info_fields if f)
        n2_info_complete = filled_count / len(info_fields)

        # 카테고리 점수 (카테고리가 있으면 가산)
        if place_data.get("category"):
            n2_category = 0.8

        n2 = (n2_keyword_match * 0.5) + (n2_info_complete * 0.3) + (n2_category * 0.2)

        # N3: 랭킹 지수 (순위 기반)
        if rank and total_places:
            # 순위가 높을수록 (1에 가까울수록) 점수 높음
            n3 = max(0, 1 - (rank / min(total_places, 100)))
        else:
            n3 = 0.5  # 순위 정보 없으면 중간값

        # 종합 점수
        total_score = (n1 * 0.4) + (n2 * 0.35) + (n3 * 0.25)

        return {
            "n1": round(n1, 6),
            "n2": round(n2, 6),
            "n3": round(n3, 6),
            "total": round(total_score, 6),
            "details": {
                "n1_breakdown": {
                    "visitor_review_score": round(n1_visitor, 4),
                    "blog_review_score": round(n1_blog, 4),
                    "save_score": round(n1_save, 4),
                    "reservation_score": round(n1_reservation, 4)
                },
                "n2_breakdown": {
                    "keyword_match": round(n2_keyword_match, 4),
                    "info_completeness": round(n2_info_complete, 4),
                    "category_score": round(n2_category, 4)
                },
                "n3_breakdown": {
                    "rank": rank,
                    "total_places": total_places
                }
            },
            "raw_data": {
                "visitor_review_count": visitor_reviews,
                "blog_review_count": blog_reviews,
                "save_count": save_count,
                "reservation_review_count": reservation_reviews
            }
        }

    def generate_ai_analysis(
        self,
        hidden_scores: Dict[str, Any],
        place_data: Dict[str, Any],
        keyword: str = ""
    ) -> Dict[str, Any]:
        """
        AI 기반 분석 인사이트 생성 - adlog.kr과의 차별점
        """
        n1 = hidden_scores.get("n1", 0)
        n2 = hidden_scores.get("n2", 0)
        n3 = hidden_scores.get("n3", 0)
        details = hidden_scores.get("details", {})
        raw_data = hidden_scores.get("raw_data", {})

        insights = []
        recommendations = []
        priority_actions = []

        # N1 분석 (인기도)
        if n1 < 0.3:
            insights.append({
                "type": "warning",
                "area": "인기도",
                "message": "플레이스 인기 지표가 낮습니다. 리뷰와 저장 수를 늘려야 합니다."
            })

            # 구체적으로 뭐가 부족한지
            n1_breakdown = details.get("n1_breakdown", {})
            weakest = min(n1_breakdown.items(), key=lambda x: x[1])

            if "visitor" in weakest[0]:
                priority_actions.append({
                    "priority": 1,
                    "action": "방문자 리뷰 늘리기",
                    "method": "영수증 리뷰 이벤트 진행",
                    "target": f"현재 {raw_data.get('visitor_review_count', 0)}개 → 500개 이상 목표",
                    "impact": "N1 지수 +0.1 예상"
                })
            elif "blog" in weakest[0]:
                priority_actions.append({
                    "priority": 1,
                    "action": "블로그 리뷰 늘리기",
                    "method": "블로거 체험단 진행",
                    "target": f"현재 {raw_data.get('blog_review_count', 0)}개 → 100개 이상 목표",
                    "impact": "N1 지수 +0.08 예상"
                })
            elif "save" in weakest[0]:
                priority_actions.append({
                    "priority": 1,
                    "action": "저장하기 늘리기",
                    "method": "저장 시 할인 이벤트",
                    "target": f"현재 {raw_data.get('save_count', 0)}개 → 1000개 이상 목표",
                    "impact": "N1 지수 +0.08 예상"
                })
        elif n1 >= 0.6:
            insights.append({
                "type": "success",
                "area": "인기도",
                "message": "플레이스 인기 지표가 우수합니다!"
            })

        # N2 분석 (관련성)
        n2_breakdown = details.get("n2_breakdown", {})

        if n2_breakdown.get("keyword_match", 0) < 0.3 and keyword:
            insights.append({
                "type": "warning",
                "area": "키워드 관련성",
                "message": f"'{keyword}' 키워드와 플레이스 정보 매칭이 약합니다."
            })
            recommendations.append(f"상호명이나 대표 키워드에 '{keyword}' 관련 단어 추가 고려")

        if n2_breakdown.get("info_completeness", 0) < 0.5:
            insights.append({
                "type": "warning",
                "area": "정보 완성도",
                "message": "플레이스 기본 정보가 부족합니다."
            })

            # 뭐가 빠졌는지 체크
            missing = []
            if not place_data.get("phone"):
                missing.append("전화번호")
            if not place_data.get("business_hours"):
                missing.append("영업시간")
            if not place_data.get("menu_info"):
                missing.append("메뉴 정보")

            if missing:
                priority_actions.append({
                    "priority": 2,
                    "action": "플레이스 정보 보완",
                    "method": f"네이버 플레이스에서 {', '.join(missing)} 등록",
                    "target": "정보 완성도 100%",
                    "impact": "N2 지수 +0.15 예상"
                })

        # N3 분석 (랭킹)
        n3_breakdown = details.get("n3_breakdown", {})
        rank = n3_breakdown.get("rank")

        if rank:
            if rank <= 3:
                insights.append({
                    "type": "success",
                    "area": "키워드 순위",
                    "message": f"'{keyword}' 키워드에서 상위 노출 중입니다! ({rank}위)"
                })
            elif rank <= 10:
                insights.append({
                    "type": "info",
                    "area": "키워드 순위",
                    "message": f"'{keyword}' 키워드에서 {rank}위입니다. 조금만 더 노력하면 TOP 3 진입 가능!"
                })
            else:
                insights.append({
                    "type": "warning",
                    "area": "키워드 순위",
                    "message": f"'{keyword}' 키워드에서 {rank}위입니다. 순위 개선이 필요합니다."
                })

        # 종합 평가
        total = hidden_scores.get("total", 0)
        if total >= 0.7:
            grade = "A"
            grade_message = "매우 우수한 플레이스입니다. 현재 전략 유지하세요."
        elif total >= 0.5:
            grade = "B"
            grade_message = "양호한 상태입니다. 몇 가지 개선으로 상위권 진입 가능합니다."
        elif total >= 0.3:
            grade = "C"
            grade_message = "개선이 필요합니다. 아래 우선순위 액션을 따라주세요."
        else:
            grade = "D"
            grade_message = "집중적인 마케팅이 필요합니다. 기본기부터 쌓아야 합니다."

        # 가장 약한 영역 파악
        scores = {"N1(인기도)": n1, "N2(관련성)": n2, "N3(순위)": n3}
        weakest_area = min(scores.items(), key=lambda x: x[1])
        strongest_area = max(scores.items(), key=lambda x: x[1])

        return {
            "grade": grade,
            "grade_message": grade_message,
            "total_score": round(total * 100, 1),
            "score_breakdown": {
                "n1_인기도": round(n1 * 100, 1),
                "n2_관련성": round(n2 * 100, 1),
                "n3_순위": round(n3 * 100, 1)
            },
            "weakest_area": {
                "name": weakest_area[0],
                "score": round(weakest_area[1] * 100, 1),
                "focus": f"이 영역에 집중하세요!"
            },
            "strongest_area": {
                "name": strongest_area[0],
                "score": round(strongest_area[1] * 100, 1)
            },
            "insights": insights,
            "recommendations": recommendations,
            "priority_actions": sorted(priority_actions, key=lambda x: x["priority"])[:3],
            "summary": f"종합 {grade}등급 ({round(total*100, 1)}점). {weakest_area[0]} 영역 개선 시 순위 상승 기대."
        }

    def calculate_place_score(self, place_data: Dict[str, Any]) -> float:
        """
        플레이스 지수 계산

        가중치:
        - 방문자 리뷰: 30%
        - 블로그 리뷰: 20%
        - 저장 수: 25%
        - 예약 리뷰: 15%
        - 사진 수: 10%
        """
        weights = {
            "visitor_review": 0.30,
            "blog_review": 0.20,
            "save_count": 0.25,
            "reservation_review": 0.15,
            "photo_count": 0.10
        }

        # 정규화 기준값 (업계 평균 기준)
        benchmarks = {
            "visitor_review": 500,
            "blog_review": 100,
            "save_count": 1000,
            "reservation_review": 50,
            "photo_count": 200
        }

        metrics = {
            "visitor_review": place_data.get("visitor_review_count", 0),
            "blog_review": place_data.get("blog_review_count", 0),
            "save_count": place_data.get("save_count", 0),
            "reservation_review": place_data.get("reservation_review_count", 0),
            "photo_count": place_data.get("photo_count", 0)
        }

        score = 0
        for metric, weight in weights.items():
            value = metrics.get(metric, 0)
            benchmark = benchmarks.get(metric, 1)

            # 정규화 (0~100 범위, 최대 100 cap)
            normalized = min((value / benchmark) * 100, 100)
            score += normalized * weight

        return round(score, 2)

    def analyze_competitiveness(
        self,
        target_place: Dict[str, Any],
        competitors: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """경쟁력 분석"""
        if not competitors:
            return {"message": "경쟁사 데이터 없음"}

        target_score = self.calculate_place_score(target_place)

        # 경쟁사 점수 계산
        competitor_scores = []
        for comp in competitors:
            comp_score = self.calculate_place_score(comp)
            competitor_scores.append({
                "place_id": comp.get("place_id"),
                "name": comp.get("name"),
                "score": comp_score,
                "rank": comp.get("rank")
            })

        # 평균 및 순위
        avg_score = sum(c["score"] for c in competitor_scores) / len(competitor_scores) if competitor_scores else 0
        score_rank = sum(1 for c in competitor_scores if c["score"] > target_score) + 1

        # 지표별 비교
        metrics_comparison = self._compare_metrics(target_place, competitors)

        return {
            "target_score": target_score,
            "average_competitor_score": round(avg_score, 2),
            "score_rank": score_rank,
            "total_competitors": len(competitors),
            "metrics_comparison": metrics_comparison,
            "top_competitors": sorted(competitor_scores, key=lambda x: x["score"], reverse=True)[:10],
            "strengths": self._identify_strengths(target_place, competitors),
            "weaknesses": self._identify_weaknesses(target_place, competitors)
        }

    def _compare_metrics(
        self,
        target: Dict[str, Any],
        competitors: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """지표별 비교"""
        metrics = ["visitor_review_count", "blog_review_count", "save_count"]
        comparison = {}

        for metric in metrics:
            target_value = target.get(metric, 0)
            comp_values = [c.get(metric, 0) for c in competitors]
            avg_value = sum(comp_values) / len(comp_values) if comp_values else 0
            max_value = max(comp_values) if comp_values else 0

            comparison[metric] = {
                "target": target_value,
                "average": round(avg_value, 1),
                "max": max_value,
                "percentile": self._calculate_percentile(target_value, comp_values)
            }

        return comparison

    def _calculate_percentile(self, value: float, values: List[float]) -> int:
        """백분위 계산"""
        if not values:
            return 0
        count_below = sum(1 for v in values if v < value)
        return int((count_below / len(values)) * 100)

    def _identify_strengths(
        self,
        target: Dict[str, Any],
        competitors: List[Dict[str, Any]]
    ) -> List[str]:
        """강점 분석"""
        strengths = []
        metrics = {
            "visitor_review_count": "방문자 리뷰",
            "blog_review_count": "블로그 리뷰",
            "save_count": "저장 수"
        }

        for metric, label in metrics.items():
            target_value = target.get(metric, 0)
            comp_values = [c.get(metric, 0) for c in competitors]
            avg_value = sum(comp_values) / len(comp_values) if comp_values else 0

            if target_value > avg_value * 1.2:  # 평균보다 20% 이상 높으면 강점
                strengths.append(f"{label}가 경쟁사 평균 대비 우수합니다")

        return strengths

    def _identify_weaknesses(
        self,
        target: Dict[str, Any],
        competitors: List[Dict[str, Any]]
    ) -> List[str]:
        """약점 분석"""
        weaknesses = []
        metrics = {
            "visitor_review_count": "방문자 리뷰",
            "blog_review_count": "블로그 리뷰",
            "save_count": "저장 수"
        }

        for metric, label in metrics.items():
            target_value = target.get(metric, 0)
            comp_values = [c.get(metric, 0) for c in competitors]
            avg_value = sum(comp_values) / len(comp_values) if comp_values else 0

            if target_value < avg_value * 0.8:  # 평균보다 20% 이상 낮으면 약점
                diff = int(avg_value - target_value)
                weaknesses.append(f"{label}를 {diff}개 이상 늘리면 평균 수준에 도달합니다")

        return weaknesses

    async def find_hidden_keywords(
        self,
        place_id: str,
        place_info: Dict[str, Any],
        max_keywords: int = 20
    ) -> List[Dict[str, Any]]:
        """히든 키워드 발굴"""
        hidden_keywords = []

        # 1. 카테고리 기반 키워드 확장
        category = place_info.get("category", "")
        address = place_info.get("address", "") or place_info.get("road_address", "")

        # 지역명 추출
        location_parts = []
        if address:
            parts = address.split()
            for i, part in enumerate(parts):
                if any(suffix in part for suffix in ["시", "구", "동", "읍", "면", "리"]):
                    location_parts.append(part)
                    if i > 0:
                        location_parts.append(parts[i - 1] + " " + part)

        # 키워드 조합 생성
        keyword_candidates = []

        # 지역 + 카테고리 조합
        for loc in location_parts[:3]:
            if category:
                keyword_candidates.append(f"{loc} {category}")
            keyword_candidates.append(f"{loc} 맛집")
            keyword_candidates.append(f"{loc} 추천")

        # 카테고리 관련 키워드
        category_keywords = self._expand_category_keywords(category)
        for loc in location_parts[:2]:
            for kw in category_keywords:
                keyword_candidates.append(f"{loc} {kw}")

        # 각 키워드별 순위 체크
        for keyword in keyword_candidates[:max_keywords]:
            try:
                rank_result = await self.naver_service.get_place_rank(
                    place_id, keyword, max_search=50
                )

                if rank_result.get("rank") and rank_result["rank"] <= 20:
                    hidden_keywords.append({
                        "keyword": keyword,
                        "rank": rank_result["rank"],
                        "total_results": rank_result["total_results"],
                        "potential": self._calculate_keyword_potential(rank_result)
                    })

                await asyncio.sleep(0.5)  # Rate limiting

            except Exception as e:
                logger.error(f"Error checking keyword '{keyword}': {e}")
                continue

        # 순위순 정렬
        return sorted(hidden_keywords, key=lambda x: x["rank"])

    def _expand_category_keywords(self, category: str) -> List[str]:
        """카테고리 관련 키워드 확장"""
        category_map = {
            "음식점": ["맛집", "식당", "밥집", "점심", "저녁", "회식"],
            "카페": ["카페", "커피", "디저트", "브런치", "케이크"],
            "미용실": ["미용실", "헤어샵", "머리", "펌", "염색"],
            "병원": ["병원", "의원", "클리닉", "진료"],
            "숙박": ["호텔", "모텔", "숙소", "펜션", "숙박"],
            "술집": ["술집", "호프", "이자카야", "바", "포차"],
        }

        for key, keywords in category_map.items():
            if key in category:
                return keywords

        return ["추천", "인기", "맛집"]

    def _calculate_keyword_potential(self, rank_result: Dict) -> str:
        """키워드 잠재력 평가"""
        rank = rank_result.get("rank", 999)
        total = rank_result.get("total_results", 0)

        if rank <= 3:
            return "매우 높음"
        elif rank <= 10:
            return "높음"
        elif rank <= 20:
            return "보통"
        else:
            return "낮음"

    async def generate_report(
        self,
        place_id: str,
        keywords: List[str]
    ) -> Dict[str, Any]:
        """종합 분석 리포트 생성"""
        # 플레이스 정보 조회
        place_info = await self.naver_service.get_place_info(place_id)
        if not place_info:
            return {"error": "플레이스 정보를 찾을 수 없습니다"}

        # 플레이스 지수 계산
        place_score = self.calculate_place_score(place_info)

        # 키워드별 순위 조회
        keyword_ranks = []
        all_competitors = []

        for keyword in keywords:
            rank_result = await self.naver_service.get_place_rank(place_id, keyword)
            keyword_ranks.append({
                "keyword": keyword,
                "rank": rank_result.get("rank"),
                "total_results": rank_result.get("total_results")
            })
            all_competitors.extend(rank_result.get("competitors", []))
            await asyncio.sleep(0.3)

        # 경쟁력 분석
        competitiveness = self.analyze_competitiveness(place_info, all_competitors[:50])

        # 히든 키워드
        hidden_keywords = await self.find_hidden_keywords(place_id, place_info, max_keywords=10)

        return {
            "place_info": place_info,
            "place_score": place_score,
            "keyword_ranks": keyword_ranks,
            "competitiveness": competitiveness,
            "hidden_keywords": hidden_keywords,
            "recommendations": self._generate_recommendations(
                place_info, competitiveness, keyword_ranks
            )
        }

    def _generate_recommendations(
        self,
        place_info: Dict,
        competitiveness: Dict,
        keyword_ranks: List[Dict]
    ) -> List[str]:
        """개선 추천사항 생성"""
        recommendations = []

        # 약점 기반 추천
        for weakness in competitiveness.get("weaknesses", []):
            recommendations.append(weakness)

        # 순위 기반 추천
        for kr in keyword_ranks:
            if kr.get("rank") and kr["rank"] > 10:
                recommendations.append(
                    f"'{kr['keyword']}' 키워드에서 순위가 {kr['rank']}위입니다. "
                    f"리뷰 수 증가와 저장하기 유도를 통해 순위 개선이 가능합니다."
                )

        # 일반 추천
        if place_info.get("visitor_review_count", 0) < 100:
            recommendations.append(
                "방문자 리뷰가 부족합니다. 영수증 리뷰 이벤트를 진행해보세요."
            )

        if place_info.get("save_count", 0) < 200:
            recommendations.append(
                "저장하기 수가 부족합니다. SNS 이벤트나 할인 쿠폰 제공을 고려해보세요."
            )

        return recommendations[:5]  # 상위 5개만 반환

    async def analyze_ranking_factors(
        self,
        keyword: str,
        max_places: int = 50
    ) -> Dict[str, Any]:
        """
        키워드별 순위 영향 요소 분석

        순위와 각 지표(리뷰, 저장, 블로그) 간의 상관관계를 계산하여
        어떤 요소가 순위에 가장 큰 영향을 주는지 분석
        """
        # 키워드로 검색하여 상위 플레이스 데이터 수집
        places = await self.naver_service.search_places(keyword, max_places)

        if len(places) < 5:
            return {
                "keyword": keyword,
                "error": "분석에 필요한 데이터가 부족합니다 (최소 5개 필요)",
                "places_found": len(places)
            }

        # 순위 데이터 (1, 2, 3, ... 순서대로)
        ranks = list(range(1, len(places) + 1))

        # 각 지표별 데이터 추출
        visitor_reviews = [p.get("visitor_review_count", 0) for p in places]
        blog_reviews = [p.get("blog_review_count", 0) for p in places]
        save_counts = [p.get("save_count", 0) for p in places]

        # 역순위 (순위가 낮을수록 좋으므로, 상관관계 계산 시 역으로)
        # 순위 1이 가장 좋으므로, 역순위 = max_rank - rank + 1
        inverse_ranks = [len(places) - r + 1 for r in ranks]

        # 상관계수 계산 (역순위와 각 지표)
        corr_visitor = calculate_correlation(inverse_ranks, visitor_reviews)
        corr_blog = calculate_correlation(inverse_ranks, blog_reviews)
        corr_save = calculate_correlation(inverse_ranks, save_counts)

        # 상관계수 합계로 정규화하여 영향력 비율 계산
        total_corr = abs(corr_visitor) + abs(corr_blog) + abs(corr_save)

        if total_corr == 0:
            impact_visitor = impact_blog = impact_save = 33.3
        else:
            impact_visitor = (abs(corr_visitor) / total_corr) * 100
            impact_blog = (abs(corr_blog) / total_corr) * 100
            impact_save = (abs(corr_save) / total_corr) * 100

        # 통계 데이터
        def calc_stats(values: List[float]) -> Dict:
            if not values:
                return {"avg": 0, "min": 0, "max": 0, "median": 0}
            sorted_v = sorted(values)
            return {
                "avg": round(sum(values) / len(values), 1),
                "min": min(values),
                "max": max(values),
                "median": sorted_v[len(sorted_v) // 2]
            }

        # 상위 10위 vs 하위 플레이스 비교
        top_10 = places[:10]
        bottom = places[max(10, len(places) - 10):]

        top_avg_visitor = sum(p.get("visitor_review_count", 0) for p in top_10) / len(top_10)
        top_avg_blog = sum(p.get("blog_review_count", 0) for p in top_10) / len(top_10)
        top_avg_save = sum(p.get("save_count", 0) for p in top_10) / len(top_10)

        bottom_avg_visitor = sum(p.get("visitor_review_count", 0) for p in bottom) / len(bottom) if bottom else 0
        bottom_avg_blog = sum(p.get("blog_review_count", 0) for p in bottom) / len(bottom) if bottom else 0
        bottom_avg_save = sum(p.get("save_count", 0) for p in bottom) / len(bottom) if bottom else 0

        # 영향력 순위 결정
        factors = [
            {"name": "방문자 리뷰", "key": "visitor_review", "correlation": corr_visitor, "impact": impact_visitor},
            {"name": "블로그 리뷰", "key": "blog_review", "correlation": corr_blog, "impact": impact_blog},
            {"name": "저장수", "key": "save_count", "correlation": corr_save, "impact": impact_save},
        ]
        factors_sorted = sorted(factors, key=lambda x: x["impact"], reverse=True)

        return {
            "keyword": keyword,
            "analyzed_places": len(places),
            "factors": {
                "visitor_review": {
                    "name": "방문자 리뷰",
                    "correlation": round(corr_visitor, 3),
                    "impact_percent": round(impact_visitor, 1),
                    "stats": calc_stats(visitor_reviews),
                    "top10_avg": round(top_avg_visitor, 1),
                    "bottom_avg": round(bottom_avg_visitor, 1),
                },
                "blog_review": {
                    "name": "블로그 리뷰",
                    "correlation": round(corr_blog, 3),
                    "impact_percent": round(impact_blog, 1),
                    "stats": calc_stats(blog_reviews),
                    "top10_avg": round(top_avg_blog, 1),
                    "bottom_avg": round(bottom_avg_blog, 1),
                },
                "save_count": {
                    "name": "저장수",
                    "correlation": round(corr_save, 3),
                    "impact_percent": round(impact_save, 1),
                    "stats": calc_stats(save_counts),
                    "top10_avg": round(top_avg_save, 1),
                    "bottom_avg": round(bottom_avg_save, 1),
                }
            },
            "ranking": [
                {
                    "rank": i + 1,
                    "factor": f["name"],
                    "impact_percent": round(f["impact"], 1),
                    "correlation": round(f["correlation"], 3)
                }
                for i, f in enumerate(factors_sorted)
            ],
            "insight": self._generate_factor_insight(factors_sorted, keyword),
            "top_places": [
                {
                    "rank": i + 1,
                    "name": p.get("name", ""),
                    "place_id": p.get("place_id", ""),
                    "visitor_review_count": p.get("visitor_review_count", 0),
                    "blog_review_count": p.get("blog_review_count", 0),
                    "save_count": p.get("save_count", 0),
                }
                for i, p in enumerate(places[:10])
            ]
        }

    def _generate_factor_insight(
        self,
        factors_sorted: List[Dict],
        keyword: str
    ) -> str:
        """요소 분석 인사이트 생성 - 명확한 추천"""
        top_factor = factors_sorted[0]
        return f"'{keyword}' 키워드는 **{top_factor['name']}**에 집중하세요."

    def generate_marketing_recommendation(
        self,
        analysis_result: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        마케팅 추천 생성 - 확실한 우선순위와 구체적 목표 제시
        """
        keyword = analysis_result.get("keyword", "")
        factors = analysis_result.get("factors", {})
        ranking = analysis_result.get("ranking", [])
        top_places = analysis_result.get("top_places", [])

        if not ranking:
            return {"error": "분석 데이터 없음"}

        # 1순위 요소
        top_factor = ranking[0]
        factor_key = None
        if "방문자" in top_factor["factor"]:
            factor_key = "visitor_review"
        elif "블로그" in top_factor["factor"]:
            factor_key = "blog_review"
        else:
            factor_key = "save_count"

        factor_data = factors.get(factor_key, {})

        # 마케팅 방법 매핑
        marketing_methods = {
            "visitor_review": {
                "name": "방문자 리뷰",
                "primary_action": "영수증 리뷰 이벤트",
                "methods": [
                    "영수증 리뷰 작성 시 음료/디저트 서비스",
                    "재방문 고객 리뷰 요청 (단골 활용)",
                    "네이버 예약 후 자동 리뷰 요청 설정",
                    "직원이 계산 시 리뷰 요청 멘트"
                ],
                "cost": "낮음 (서비스 비용만)",
                "effect_time": "1-2주"
            },
            "blog_review": {
                "name": "블로그 리뷰",
                "primary_action": "블로거 체험단 진행",
                "methods": [
                    "지역 블로거 체험단 모집 (무료 식사 제공)",
                    "블로그 리뷰 작성 시 할인 쿠폰 제공",
                    "인플루언서 협찬 (팔로워 1만+ 블로거)",
                    "네이버 플레이스 블로거 체험단 신청"
                ],
                "cost": "중간 (체험단 비용)",
                "effect_time": "2-4주"
            },
            "save_count": {
                "name": "저장수",
                "primary_action": "저장하기 이벤트",
                "methods": [
                    "플레이스 저장 시 즉시 할인 (5-10%)",
                    "저장 인증 시 음료 서비스",
                    "SNS에 '저장하기' 이벤트 홍보",
                    "매장 내 저장하기 QR코드 비치"
                ],
                "cost": "낮음",
                "effect_time": "즉시-1주"
            }
        }

        method = marketing_methods.get(factor_key, marketing_methods["visitor_review"])

        # 목표 수치 계산
        top10_avg = factor_data.get("top10_avg", 0)
        current_median = factor_data.get("stats", {}).get("median", 0)

        # 우선순위 리스트 생성
        priorities = []
        for i, r in enumerate(ranking):
            fkey = None
            if "방문자" in r["factor"]:
                fkey = "visitor_review"
            elif "블로그" in r["factor"]:
                fkey = "blog_review"
            else:
                fkey = "save_count"

            priorities.append({
                "priority": i + 1,
                "factor": r["factor"],
                "impact_percent": r["impact_percent"],
                "action": marketing_methods[fkey]["primary_action"],
                "top10_avg": factors.get(fkey, {}).get("top10_avg", 0)
            })

        return {
            "keyword": keyword,
            "recommendation": {
                "do_this": method["primary_action"],
                "reason": f"'{keyword}' 키워드에서 {method['name']}이 순위에 {top_factor['impact_percent']}% 영향",
                "target": f"상위 10위 평균: {int(top10_avg)}개 → 최소 이 수준까지 늘리기",
                "how_to": method["methods"],
                "cost": method["cost"],
                "expected_time": method["effect_time"]
            },
            "priorities": priorities,
            "summary": f"1순위: {priorities[0]['action']} → 2순위: {priorities[1]['action']} → 3순위: {priorities[2]['action']}"
        }
