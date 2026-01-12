"""
키워드 검색량 조회 서비스
네이버 검색광고 API 또는 대안적 방법으로 실제 월간 검색량 조회
"""
import httpx
import hashlib
import hmac
import time
import base64
from typing import Optional, Dict, List
import logging
from app.core.config import settings

logger = logging.getLogger(__name__)


class KeywordVolumeService:
    """키워드 검색량 조회 서비스"""

    def __init__(self):
        # 네이버 검색광고 API 인증 정보
        self.api_key = settings.NAVER_AD_API_KEY
        self.secret_key = settings.NAVER_AD_SECRET_KEY
        self.customer_id = settings.NAVER_AD_CUSTOMER_ID
        self.base_url = "https://api.searchad.naver.com"
        # 상위 업체 캐시 (키워드 -> 데이터, 5분간 유효)
        self._competitor_cache: Dict[str, Dict] = {}
        self._cache_time: Dict[str, float] = {}

    def _generate_signature(self, timestamp: str, method: str, uri: str) -> str:
        """API 서명 생성"""
        message = f"{timestamp}.{method}.{uri}"
        signature = hmac.new(
            self.secret_key.encode('utf-8'),
            message.encode('utf-8'),
            hashlib.sha256
        ).digest()
        return base64.b64encode(signature).decode('utf-8')

    def _get_headers(self, method: str, uri: str) -> Dict[str, str]:
        """API 요청 헤더 생성"""
        timestamp = str(int(time.time() * 1000))
        signature = self._generate_signature(timestamp, method, uri)

        return {
            "X-API-KEY": self.api_key,
            "X-CUSTOMER": self.customer_id,
            "X-TIMESTAMP": timestamp,
            "X-SIGNATURE": signature,
            "Content-Type": "application/json"
        }

    async def get_keyword_volume(self, keywords: List[str]) -> Dict[str, Dict]:
        """
        키워드 검색량 조회

        Returns:
            {
                "키워드": {
                    "monthly_pc": 1000,  # PC 월간 검색량
                    "monthly_mobile": 5000,  # 모바일 월간 검색량
                    "monthly_total": 6000,  # 총 월간 검색량
                    "competition": "HIGH"  # 경쟁 정도
                }
            }
        """
        # API 키가 있으면 검색광고 API 사용
        if self.api_key and self.secret_key and self.customer_id:
            return await self._get_volume_from_ads_api(keywords)

        # API 키 없으면 추정치 반환 (DataLab 지수 기반)
        logger.warning("검색광고 API 키가 없습니다. 추정 검색량을 반환합니다.")
        return await self._estimate_volume(keywords)

    async def _get_volume_from_ads_api(self, keywords: List[str]) -> Dict[str, Dict]:
        """네이버 검색광고 API로 검색량 조회"""
        uri = "/keywordstool"
        method = "GET"

        try:
            async with httpx.AsyncClient() as client:
                results = {}

                # 한 번에 5개씩 조회 (API 제한)
                for i in range(0, len(keywords), 5):
                    batch = keywords[i:i+5]

                    response = await client.get(
                        f"{self.base_url}{uri}",
                        headers=self._get_headers(method, uri),
                        params={
                            "hintKeywords": ",".join(batch),
                            "showDetail": "1"
                        },
                        timeout=30.0
                    )

                    if response.status_code == 200:
                        data = response.json()
                        for item in data.get("keywordList", []):
                            kw = item.get("relKeyword", "")
                            if kw in batch:
                                pc = item.get("monthlyPcQcCnt", 0)
                                mobile = item.get("monthlyMobileQcCnt", 0)

                                # "< 10" 같은 문자열 처리
                                if isinstance(pc, str):
                                    pc = 10 if "< 10" in pc else int(pc.replace(",", ""))
                                if isinstance(mobile, str):
                                    mobile = 10 if "< 10" in mobile else int(mobile.replace(",", ""))

                                results[kw] = {
                                    "monthly_pc": pc,
                                    "monthly_mobile": mobile,
                                    "monthly_total": pc + mobile,
                                    "competition": item.get("compIdx", "UNKNOWN")
                                }
                    else:
                        logger.error(f"검색광고 API 오류: {response.status_code}")

                return results

        except Exception as e:
            logger.error(f"검색광고 API 호출 실패: {e}")
            return await self._estimate_volume(keywords)

    async def _estimate_volume(self, keywords: List[str]) -> Dict[str, Dict]:
        """
        DataLab 지수 기반 검색량 추정
        - 100 지수 ≈ 50,000 ~ 100,000 월간 검색량 (인기 키워드 기준)
        - 카테고리별 기준치 적용
        """
        from app.services.naver_datalab import datalab_service

        results = {}

        try:
            # DataLab에서 트렌드 조회
            if len(keywords) == 1:
                trend_data = await datalab_service.get_search_trend(keywords[0])
                if trend_data and "keywords" in trend_data:
                    kw_data = trend_data["keywords"][0]
                    avg_ratio = kw_data.get("stats", {}).get("average", 50)

                    # 추정 검색량 계산 (지수 50 기준 약 30,000)
                    estimated = int(avg_ratio * 600)  # 대략적 추정

                    results[keywords[0]] = {
                        "monthly_pc": int(estimated * 0.3),
                        "monthly_mobile": int(estimated * 0.7),
                        "monthly_total": estimated,
                        "competition": "MEDIUM",
                        "is_estimated": True
                    }
            else:
                trend_data = await datalab_service.compare_keywords(keywords)
                if trend_data and "keywords" in trend_data:
                    for kw_data in trend_data["keywords"]:
                        kw = kw_data.get("keyword", "")
                        avg_ratio = kw_data.get("stats", {}).get("average", 50)

                        estimated = int(avg_ratio * 600)

                        results[kw] = {
                            "monthly_pc": int(estimated * 0.3),
                            "monthly_mobile": int(estimated * 0.7),
                            "monthly_total": estimated,
                            "competition": "MEDIUM",
                            "is_estimated": True
                        }

        except Exception as e:
            logger.error(f"검색량 추정 실패: {e}")
            # 기본값 반환
            for kw in keywords:
                results[kw] = {
                    "monthly_pc": 0,
                    "monthly_mobile": 0,
                    "monthly_total": 0,
                    "competition": "UNKNOWN",
                    "is_estimated": True
                }

        return results


    async def _get_top_competitors_reviews(self, keyword: str) -> Dict:
        """
        키워드로 네이버 플레이스 검색해서 상위 3개 업체의 리뷰수 + 가중치 점수 가져오기
        캐시 사용 (5분간 유효)

        가중치:
        - 방문자 리뷰: 40%
        - 블로그 리뷰: 30%
        - 최신성 (최근 리뷰 비율 추정): 30%
        """
        import asyncio

        # 캐시 확인 (5분간 유효)
        cache_key = keyword
        current_time = time.time()
        if cache_key in self._competitor_cache:
            if current_time - self._cache_time.get(cache_key, 0) < 300:  # 5분
                return self._competitor_cache[cache_key]

        try:
            from app.services.naver_place import NaverPlaceService
            naver_service = NaverPlaceService()

            # 타임아웃 설정 (15초)
            try:
                places = await asyncio.wait_for(
                    naver_service.search_places(keyword, max_results=5),
                    timeout=15.0
                )
            except asyncio.TimeoutError:
                logger.warning(f"상위 업체 검색 타임아웃 ({keyword})")
                return {"avg_visitor": 0, "avg_blog": 0, "avg_total": 0, "top3": []}

            if not places:
                return {"avg_visitor": 0, "avg_blog": 0, "avg_total": 0, "top3": []}

            # 상위 3개만 사용
            top3 = places[:3]

            # 각 업체 데이터 수집
            top3_data = []
            for place in top3:
                visitor = place.get("visitor_review_count", 0) or 0
                blog = place.get("blog_review_count", 0) or 0
                save = place.get("save_count", 0) or 0
                total = visitor + blog

                # 최신성 지표: 블로그 리뷰 비율 (블로그가 최근 활동 반영)
                # 블로그 리뷰가 전체의 10% 이상이면 활발한 편
                freshness = round(blog / max(total, 1) * 100, 1)

                top3_data.append({
                    "name": place.get("name", ""),
                    "visitor": visitor,
                    "blog": blog,
                    "save": save,
                    "total": total,
                    "freshness": freshness
                })

            # 상위 3개 평균
            avg_visitor = int(sum(p["visitor"] for p in top3_data) / len(top3_data)) if top3_data else 0
            avg_blog = int(sum(p["blog"] for p in top3_data) / len(top3_data)) if top3_data else 0
            avg_save = int(sum(p["save"] for p in top3_data) / len(top3_data)) if top3_data else 0
            avg_total = int(sum(p["total"] for p in top3_data) / len(top3_data)) if top3_data else 0
            avg_freshness = round(sum(p["freshness"] for p in top3_data) / len(top3_data), 1) if top3_data else 0

            result = {
                "avg_visitor": avg_visitor,
                "avg_blog": avg_blog,
                "avg_save": avg_save,
                "avg_total": avg_total,
                "avg_freshness": avg_freshness,
                "top3": top3_data
            }

            # 캐시에 저장
            self._competitor_cache[cache_key] = result
            self._cache_time[cache_key] = current_time

            return result

        except Exception as e:
            logger.error(f"상위 업체 리뷰 조회 실패 ({keyword}): {e}")
            return {"avg_visitor": 0, "avg_blog": 0, "avg_total": 0, "top3": []}

    async def get_related_keywords(
        self,
        hint_keyword: str,
        place_name: str = "",
        limit: int = 10,
        my_visitor_reviews: int = 0,
        my_blog_reviews: int = 0
    ) -> List[Dict]:
        """
        지역 + 업종 기반 연관 키워드 + 검색량 조회
        업체명에서 지역 추출 → 근처 지역만 추천

        예: 업체 "아뜰리에 호수 홍대점", 키워드 "서울반지공방"
        → 홍대 근처(신촌, 연남, 합정) + 업종(반지공방, 커플링)
        """
        if not (self.api_key and self.secret_key and self.customer_id):
            logger.warning("검색광고 API 키가 없습니다.")
            return []

        # 근처 지역 매핑 (도보/대중교통 10-15분 거리)
        nearby_locations = {
            '홍대': ['홍대', '신촌', '연남', '합정', '망원', '상수'],
            '신촌': ['신촌', '홍대', '이대', '연남', '아현'],
            '강남': ['강남', '역삼', '신사', '논현', '선릉', '삼성'],
            '성수': ['성수', '건대', '뚝섬', '서울숲', '왕십리'],
            '건대': ['건대', '성수', '구의', '어린이대공원'],
            '잠실': ['잠실', '석촌', '송파', '방이', '삼성'],
            '이태원': ['이태원', '한남', '녹사평', '경리단길', '해방촌'],
            '명동': ['명동', '을지로', '충무로', '남대문', '회현'],
            '종로': ['종로', '광화문', '인사동', '익선동', '삼청동'],
            '여의도': ['여의도', '영등포', '당산', '선유도'],
            '해운대': ['해운대', '광안리', '센텀', '송정', '기장'],
            '서면': ['서면', '전포', '부전', '범내골'],
            '수원': ['수원', '인계동', '영통', '광교'],
        }

        # 업종별 관련 키워드 매핑
        business_keywords = {
            '반지공방': ['반지공방', '커플링', '반지만들기', '은반지', '커플링만들기'],
            '공방': ['공방', '원데이클래스', '공방체험', 'DIY체험'],
            '카페': ['카페', '브런치카페', '디저트카페', '분위기카페'],
            '맛집': ['맛집', '맛집추천', '데이트맛집', '점심맛집'],
            '네일': ['네일샵', '네일아트', '젤네일'],
            '미용실': ['미용실', '헤어샵', '머리잘하는곳'],
            '스튜디오': ['사진관', '프로필촬영', '증명사진'],
            '술집': ['술집', '이자카야', '바', '포차'],
            '고기집': ['고기집', '삼겹살', '소고기', '갈비'],
        }

        # 1. 업체명에서 지역 추출 (예: "아뜰리에 호수 홍대점" → "홍대")
        combined_text = f"{place_name} {hint_keyword}".replace(' ', '')
        found_location = None

        for main_loc in nearby_locations.keys():
            if main_loc in combined_text or f"{main_loc}점" in combined_text or f"{main_loc}역" in combined_text:
                found_location = main_loc
                break

        # 못 찾으면 키워드에서 추출
        if not found_location:
            all_locations = list(nearby_locations.keys())
            for loc in all_locations:
                if loc in combined_text:
                    found_location = loc
                    break

        # 그래도 못 찾으면 서울 전체 (홍대 기본)
        if not found_location:
            found_location = '홍대'

        # 근처 지역 가져오기
        target_locations = nearby_locations.get(found_location, [found_location])

        # 2. 키워드에서 업종 추출
        found_business = []
        for biz, related in business_keywords.items():
            if biz in combined_text:
                found_business = related
                break

        if not found_business:
            # 키워드 자체를 업종으로 사용
            found_business = [hint_keyword.split()[-1] if ' ' in hint_keyword else hint_keyword]

        # 3. 지역 + 업종 조합 키워드 생성 (근처 지역만!)
        combined_keywords = []
        for loc in target_locations:  # 근처 지역만
            for biz in found_business[:3]:  # 최대 3개 업종
                combined = f"{loc}{biz}"
                if combined not in combined_keywords and combined != hint_keyword.replace(' ', ''):
                    combined_keywords.append(combined)

        # 최대 10개 키워드만
        combined_keywords = combined_keywords[:10]

        if not combined_keywords:
            return []

        # 3. 검색량 조회
        uri = "/keywordstool"
        method = "GET"

        try:
            async with httpx.AsyncClient() as client:
                results = []

                # 5개씩 배치로 조회
                for i in range(0, len(combined_keywords), 5):
                    batch = combined_keywords[i:i+5]

                    response = await client.get(
                        f"{self.base_url}{uri}",
                        headers=self._get_headers(method, uri),
                        params={
                            "hintKeywords": ",".join(batch),
                            "showDetail": "1"
                        },
                        timeout=30.0
                    )

                    if response.status_code == 200:
                        data = response.json()

                        for item in data.get("keywordList", []):
                            kw = item.get("relKeyword", "")
                            # 조회한 키워드만 (연관 키워드 제외)
                            if kw not in batch:
                                continue

                            pc = item.get("monthlyPcQcCnt", 0)
                            mobile = item.get("monthlyMobileQcCnt", 0)

                            if isinstance(pc, str):
                                pc = 10 if "< 10" in pc else int(pc.replace(",", ""))
                            if isinstance(mobile, str):
                                mobile = 10 if "< 10" in mobile else int(mobile.replace(",", ""))

                            total = pc + mobile
                            if total > 0:
                                results.append({
                                    "keyword": kw,
                                    "monthly_pc": pc,
                                    "monthly_mobile": mobile,
                                    "monthly_total": total,
                                    "competition": item.get("compIdx", "UNKNOWN")
                                })
                    else:
                        logger.error(f"검색광고 API 오류: {response.status_code}")

                # 검색량 순 정렬
                results.sort(key=lambda x: x["monthly_total"], reverse=True)

                # 공략 가능성 분석 추가 - 실제 상위 업체 리뷰수와 비교
                # 상위 3개 키워드만 경쟁사 분석 (속도 최적화)
                my_total_reviews = my_visitor_reviews + my_blog_reviews
                analyzed_results = []

                for idx, kw in enumerate(results[:limit]):
                    # 상위 5개 키워드 실제 경쟁사 검색 (나머지는 스킵)
                    if idx < 5:
                        top_competitors = await self._get_top_competitors_reviews(kw["keyword"])
                    else:
                        top_competitors = {"avg_visitor": 0, "avg_blog": 0, "avg_total": 0, "top3": []}

                    volume = kw["monthly_total"]
                    competition = kw["competition"]

                    avg_visitor = top_competitors.get("avg_visitor", 0)
                    avg_blog = top_competitors.get("avg_blog", 0)
                    avg_total = top_competitors.get("avg_total", 0)
                    top3 = top_competitors.get("top3", [])

                    # 가중치 기반 경쟁력 계산 (합계 100%)
                    # 방문자리뷰 50% + 블로그리뷰 50%
                    # (각각 상위 평균 대비 내 비율)
                    if avg_visitor > 0:
                        visitor_ratio = min(my_visitor_reviews / avg_visitor, 2.0)  # 최대 200%
                    else:
                        visitor_ratio = 1.0

                    if avg_blog > 0:
                        blog_ratio = min(my_blog_reviews / avg_blog, 2.0)  # 최대 200%
                    else:
                        blog_ratio = 1.0

                    # 최종 경쟁력 점수 (0~200%)
                    # 방문자 50% + 블로그 50%
                    competitiveness = (visitor_ratio * 0.5 + blog_ratio * 0.5) * 100

                    # 검색량 난이도 (검색량 많을수록 경쟁 치열)
                    if volume < 500:
                        volume_difficulty = 1  # 쉬움
                    elif volume < 2000:
                        volume_difficulty = 2  # 보통
                    elif volume < 5000:
                        volume_difficulty = 3  # 어려움
                    else:
                        volume_difficulty = 4  # 매우 어려움

                    # 최종 공략 가능성 판단
                    # 경쟁력 70% 이상이면 공략 가능
                    if competitiveness >= 70:
                        if volume_difficulty <= 2:
                            chance = "높음"
                            chance_desc = f"방문자 {int(visitor_ratio*100)}% 블로그 {int(blog_ratio*100)}%"
                            chance_color = "#16a34a"
                        else:
                            chance = "중간"
                            chance_desc = f"경쟁력 OK, 검색량 높음"
                            chance_color = "#f59e0b"
                    elif competitiveness >= 30:
                        chance = "중간"
                        visitor_gap = max(0, int(avg_visitor * 0.7) - my_visitor_reviews)
                        blog_gap = max(0, int(avg_blog * 0.7) - my_blog_reviews)
                        chance_desc = f"방문자+{visitor_gap} 블로그+{blog_gap}"
                        chance_color = "#f59e0b"
                    else:
                        if avg_total > 0:
                            visitor_gap = max(0, int(avg_visitor * 0.7) - my_visitor_reviews)
                            blog_gap = max(0, int(avg_blog * 0.7) - my_blog_reviews)
                            chance = "낮음"
                            chance_desc = f"방문자+{visitor_gap} 블로그+{blog_gap} 부족"
                            chance_color = "#dc2626"
                        else:
                            chance = "중간"
                            chance_desc = "상위 업체 정보 없음"
                            chance_color = "#f59e0b"

                    kw["avg_visitor"] = avg_visitor
                    kw["avg_blog"] = avg_blog
                    kw["avg_total"] = avg_total
                    kw["top3"] = top3
                    kw["my_visitor"] = my_visitor_reviews
                    kw["my_blog"] = my_blog_reviews
                    kw["my_total"] = my_total_reviews
                    kw["visitor_ratio"] = round(visitor_ratio * 100, 1)
                    kw["blog_ratio"] = round(blog_ratio * 100, 1)
                    kw["competitiveness"] = round(competitiveness, 1)
                    kw["chance"] = chance
                    kw["chance_desc"] = chance_desc
                    kw["chance_color"] = chance_color

                    analyzed_results.append(kw)

                # 공략 가능성 높은 순으로 정렬 (chance: 높음 > 중간 > 낮음, 같으면 검색량 높은 순)
                chance_order = {"높음": 0, "중간": 1, "낮음": 2}
                analyzed_results.sort(key=lambda x: (chance_order[x["chance"]], -x["monthly_total"]))

                return analyzed_results

        except Exception as e:
            logger.error(f"연관 키워드 조회 실패: {e}")
            return []


keyword_volume_service = KeywordVolumeService()
