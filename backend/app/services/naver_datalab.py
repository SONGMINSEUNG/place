"""
네이버 데이터랩 API 서비스
검색어 트렌드 분석 기능 제공
"""
import aiohttp
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
import logging
from app.core.config import settings

logger = logging.getLogger(__name__)


class NaverDataLabService:
    """네이버 데이터랩 API 서비스"""

    def __init__(self):
        self.client_id = settings.NAVER_CLIENT_ID or ""
        self.client_secret = settings.NAVER_CLIENT_SECRET or ""
        self.base_url = "https://openapi.naver.com/v1/datalab"

    def _get_headers(self) -> Dict[str, str]:
        return {
            "X-Naver-Client-Id": self.client_id,
            "X-Naver-Client-Secret": self.client_secret,
            "Content-Type": "application/json"
        }

    async def get_search_trend(
        self,
        keywords: List[str],
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        time_unit: str = "date"
    ) -> Dict[str, Any]:
        """
        키워드 검색 트렌드 조회

        Args:
            keywords: 검색할 키워드 목록 (최대 5개)
            start_date: 시작일 (YYYY-MM-DD), 기본값 30일 전
            end_date: 종료일 (YYYY-MM-DD), 기본값 오늘
            time_unit: 시간 단위 (date: 일별, week: 주별, month: 월별)

        Returns:
            검색 트렌드 데이터
        """
        if not self.client_id or not self.client_secret:
            return {"error": "네이버 API 키가 설정되지 않았습니다"}

        # 날짜 기본값 설정
        if not end_date:
            end_date = datetime.now().strftime("%Y-%m-%d")
        if not start_date:
            start_date = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")

        # 키워드 그룹 생성 (각 키워드별로)
        keyword_groups = [
            {
                "groupName": kw,
                "keywords": [kw]
            }
            for kw in keywords[:5]  # 최대 5개
        ]

        payload = {
            "startDate": start_date,
            "endDate": end_date,
            "timeUnit": time_unit,
            "keywordGroups": keyword_groups
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.base_url}/search",
                    headers=self._get_headers(),
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=15)
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        return self._process_trend_data(data, keywords)
                    else:
                        error_text = await response.text()
                        logger.error(f"DataLab API error: {response.status} - {error_text}")
                        return {"error": f"API 오류: {response.status}"}
        except Exception as e:
            logger.error(f"DataLab API exception: {e}")
            return {"error": str(e)}

    def _process_trend_data(self, data: Dict, keywords: List[str]) -> Dict[str, Any]:
        """트렌드 데이터 가공"""
        results = data.get("results", [])

        processed = {
            "period": {
                "start": data.get("startDate"),
                "end": data.get("endDate"),
                "unit": data.get("timeUnit")
            },
            "keywords": []
        }

        for result in results:
            keyword_data = {
                "keyword": result.get("title"),
                "data": result.get("data", []),
                "stats": self._calculate_stats(result.get("data", []))
            }
            processed["keywords"].append(keyword_data)

        # 키워드 간 비교 분석
        if len(results) > 1:
            processed["comparison"] = self._compare_keywords(results)

        return processed

    def _calculate_stats(self, data: List[Dict]) -> Dict[str, Any]:
        """통계 계산"""
        if not data:
            return {}

        ratios = [d.get("ratio", 0) for d in data]

        return {
            "average": round(sum(ratios) / len(ratios), 2),
            "max": round(max(ratios), 2),
            "min": round(min(ratios), 2),
            "max_date": next((d["period"] for d in data if d.get("ratio") == max(ratios)), None),
            "min_date": next((d["period"] for d in data if d.get("ratio") == min(ratios)), None),
            "trend": self._calculate_trend(ratios)
        }

    def _calculate_trend(self, ratios: List[float]) -> str:
        """트렌드 방향 계산"""
        if len(ratios) < 2:
            return "stable"

        # 전반부와 후반부 평균 비교
        mid = len(ratios) // 2
        first_half = sum(ratios[:mid]) / mid if mid > 0 else 0
        second_half = sum(ratios[mid:]) / (len(ratios) - mid) if len(ratios) > mid else 0

        diff = second_half - first_half
        if diff > 5:
            return "rising"
        elif diff < -5:
            return "falling"
        else:
            return "stable"

    def _compare_keywords(self, results: List[Dict]) -> Dict[str, Any]:
        """키워드 간 비교"""
        comparison = {
            "ranking": [],
            "strongest": None,
            "weakest": None
        }

        # 평균 기준 랭킹
        keyword_avgs = []
        for result in results:
            data = result.get("data", [])
            if data:
                avg = sum(d.get("ratio", 0) for d in data) / len(data)
                keyword_avgs.append({
                    "keyword": result.get("title"),
                    "average": round(avg, 2)
                })

        # 정렬
        keyword_avgs.sort(key=lambda x: x["average"], reverse=True)
        comparison["ranking"] = keyword_avgs

        if keyword_avgs:
            comparison["strongest"] = keyword_avgs[0]["keyword"]
            comparison["weakest"] = keyword_avgs[-1]["keyword"]

        return comparison

    async def compare_keywords(
        self,
        keywords: List[str],
        days: int = 30
    ) -> Dict[str, Any]:
        """
        키워드 비교 분석

        여러 키워드의 검색 트렌드를 비교합니다.
        """
        end_date = datetime.now().strftime("%Y-%m-%d")
        start_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")

        return await self.get_search_trend(keywords, start_date, end_date)

    async def get_weekly_pattern(self, keyword: str) -> Dict[str, Any]:
        """
        요일별 검색 패턴 분석

        최근 4주 데이터로 요일별 평균 검색량을 분석합니다.
        """
        end_date = datetime.now().strftime("%Y-%m-%d")
        start_date = (datetime.now() - timedelta(days=28)).strftime("%Y-%m-%d")

        result = await self.get_search_trend([keyword], start_date, end_date, "date")

        if "error" in result:
            return result

        # 요일별 집계
        weekday_data = {i: [] for i in range(7)}  # 0=월, 6=일
        weekday_names = ["월", "화", "수", "목", "금", "토", "일"]

        if result.get("keywords"):
            for item in result["keywords"][0].get("data", []):
                date = datetime.strptime(item["period"], "%Y-%m-%d")
                weekday = date.weekday()
                weekday_data[weekday].append(item["ratio"])

        # 평균 계산
        pattern = []
        for i in range(7):
            if weekday_data[i]:
                avg = sum(weekday_data[i]) / len(weekday_data[i])
                pattern.append({
                    "weekday": weekday_names[i],
                    "weekday_num": i,
                    "average": round(avg, 2)
                })

        # 가장 높은/낮은 요일
        if pattern:
            pattern.sort(key=lambda x: x["average"], reverse=True)
            best_day = pattern[0]
            worst_day = pattern[-1]
        else:
            best_day = worst_day = None

        return {
            "keyword": keyword,
            "period": f"{start_date} ~ {end_date}",
            "weekly_pattern": sorted(pattern, key=lambda x: x["weekday_num"]),
            "best_day": best_day,
            "worst_day": worst_day,
            "insight": self._generate_pattern_insight(best_day, worst_day) if best_day else None
        }

    def _generate_pattern_insight(self, best_day: Dict, worst_day: Dict) -> str:
        """패턴 인사이트 생성"""
        if not best_day or not worst_day:
            return ""

        insights = []

        # 주말/주중 패턴
        weekend = ["토", "일"]
        if best_day["weekday"] in weekend:
            insights.append(f"주말({best_day['weekday']}요일)에 검색이 가장 활발합니다.")
        else:
            insights.append(f"평일({best_day['weekday']}요일)에 검색이 가장 활발합니다.")

        # 차이 분석
        diff = best_day["average"] - worst_day["average"]
        if diff > 20:
            insights.append(f"요일별 편차가 큽니다 ({worst_day['weekday']}요일 대비 {diff:.1f}% 높음).")

        return " ".join(insights)

    async def get_seasonal_trend(self, keyword: str, months: int = 12) -> Dict[str, Any]:
        """
        월별 시즌 트렌드 분석
        """
        end_date = datetime.now().strftime("%Y-%m-%d")
        start_date = (datetime.now() - timedelta(days=months * 30)).strftime("%Y-%m-%d")

        result = await self.get_search_trend([keyword], start_date, end_date, "month")

        if "error" in result:
            return result

        # 월별 데이터 가공
        monthly_data = []
        if result.get("keywords"):
            for item in result["keywords"][0].get("data", []):
                monthly_data.append({
                    "month": item["period"],
                    "ratio": item["ratio"]
                })

        # 시즌 분석
        season_analysis = self._analyze_seasonality(monthly_data)

        return {
            "keyword": keyword,
            "period": f"{start_date} ~ {end_date}",
            "monthly_data": monthly_data,
            "season_analysis": season_analysis
        }

    def _analyze_seasonality(self, monthly_data: List[Dict]) -> Dict[str, Any]:
        """시즌성 분석"""
        if len(monthly_data) < 3:
            return {"has_seasonality": False}

        ratios = [d["ratio"] for d in monthly_data]
        avg = sum(ratios) / len(ratios)

        # 변동 계수 계산
        variance = sum((r - avg) ** 2 for r in ratios) / len(ratios)
        std_dev = variance ** 0.5
        cv = (std_dev / avg) * 100 if avg > 0 else 0

        # 시즌성 판단 (변동계수가 높으면 시즌성 있음)
        has_seasonality = cv > 15

        # 피크/비수기 월 찾기
        peak_month = max(monthly_data, key=lambda x: x["ratio"])
        low_month = min(monthly_data, key=lambda x: x["ratio"])

        return {
            "has_seasonality": has_seasonality,
            "variability": round(cv, 2),
            "variability_level": "높음" if cv > 25 else "보통" if cv > 15 else "낮음",
            "peak_month": peak_month["month"],
            "peak_ratio": peak_month["ratio"],
            "low_month": low_month["month"],
            "low_ratio": low_month["ratio"]
        }


# 싱글톤 인스턴스
datalab_service = NaverDataLabService()
