import asyncio
import re
import json
import random
import time
import os
import hashlib
from typing import Optional, Dict, List, Any
from datetime import datetime, timedelta
from bs4 import BeautifulSoup
import logging
import urllib.parse
from playwright.async_api import async_playwright, Browser, Page
import aiohttp
from pathlib import Path

logger = logging.getLogger(__name__)

# 검색 결과 캐시 디렉토리
SEARCH_CACHE_DIR = Path(__file__).parent.parent.parent / ".cache" / "search"
SEARCH_CACHE_DIR.mkdir(parents=True, exist_ok=True)

# 순위별 예상 CTR (클릭률) - 업계 평균 기반
RANK_CTR = {
    1: 0.35,   # 1위: 35%
    2: 0.17,   # 2위: 17%
    3: 0.11,   # 3위: 11%
    4: 0.08,   # 4위: 8%
    5: 0.06,   # 5위: 6%
    6: 0.05,   # 6위: 5%
    7: 0.04,   # 7위: 4%
    8: 0.03,   # 8위: 3%
    9: 0.025,  # 9위: 2.5%
    10: 0.02,  # 10위: 2%
}

# 프록시 설정 (환경변수에서 가져옴)
# 사용 예:
#   PROXY_URL=http://username:password@proxy.brightdata.com:22225
#   또는
#   PROXY_HOST=proxy.smartproxy.com
#   PROXY_PORT=10000
#   PROXY_USER=your_username
#   PROXY_PASS=your_password
def get_proxy_config() -> Optional[Dict[str, str]]:
    """환경변수에서 프록시 설정 가져오기"""
    # 방법 1: 전체 URL
    proxy_url = os.getenv("PROXY_URL")
    if proxy_url:
        return {"url": proxy_url}

    # 방법 2: 개별 설정
    host = os.getenv("PROXY_HOST")
    port = os.getenv("PROXY_PORT")
    user = os.getenv("PROXY_USER")
    password = os.getenv("PROXY_PASS")

    if host and port:
        if user and password:
            return {"url": f"http://{user}:{password}@{host}:{port}"}
        else:
            return {"url": f"http://{host}:{port}"}

    return None

# User-Agent 목록 (로테이션용)
USER_AGENTS = [
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Safari/605.1.15",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
]

# 저장수가 공개되는 업종 (맛집, 카페 등)
FOOD_CAFE_CATEGORIES = [
    "음식점", "식당", "맛집", "카페", "베이커리", "빵집", "디저트",
    "한식", "중식", "일식", "양식", "분식", "패스트푸드", "치킨",
    "피자", "햄버거", "술집", "호프", "포차", "이자카야", "바",
    "브런치", "레스토랑", "뷔페", "고기", "삼겹살", "곱창", "족발",
    "해산물", "초밥", "라멘", "우동", "국수", "냉면", "칼국수",
]


def is_food_cafe_category(category: str) -> bool:
    """음식점/카페 카테고리인지 확인 (저장수 공개 업종)"""
    if not category:
        return False
    category_lower = category.lower()
    for food_cat in FOOD_CAFE_CATEGORIES:
        if food_cat in category_lower:
            return True
    return False


class NaverPlaceService:
    """네이버 플레이스 데이터 수집 서비스 - Playwright + 네이버 검색 사용"""

    def __init__(self):
        self._browser: Optional[Browser] = None
        self._playwright = None
        self._lock = asyncio.Lock()
        self._last_request_time = 0
        self._min_request_interval = 5.0  # 최소 5초 간격 (차단 방지)
        self._save_count_cache: Dict[str, Dict[str, Any]] = {}  # 저장수 캐시
        self._cache_ttl = 86400  # 24시간 캐시
        self._search_cache_ttl = 1800  # 검색 결과 캐시 30분 (검색 결과는 더 자주 변할 수 있음)
        self._proxy_config = get_proxy_config()  # 프록시 설정
        if self._proxy_config:
            logger.info(f"Proxy configured: {self._proxy_config['url'].split('@')[-1]}")  # 비밀번호 숨김

    def _get_search_cache_key(self, keyword: str) -> str:
        """검색 캐시 키 생성"""
        key_str = f"search:{keyword.lower().strip()}"
        return hashlib.md5(key_str.encode()).hexdigest()

    def _get_search_cache_path(self, cache_key: str) -> Path:
        """검색 캐시 파일 경로"""
        return SEARCH_CACHE_DIR / f"{cache_key}.json"

    def _get_cached_search_result(self, keyword: str) -> Optional[List[Dict[str, Any]]]:
        """검색 결과 캐시 조회 (동기 버전)"""
        cache_key = self._get_search_cache_key(keyword)
        cache_path = self._get_search_cache_path(cache_key)

        if not cache_path.exists():
            logger.info(f"Search cache MISS (not found) for: {keyword}")
            return None

        try:
            with open(cache_path, 'r', encoding='utf-8') as f:
                entry = json.load(f)

            expires_at = datetime.fromisoformat(entry["expires_at"])
            if datetime.now() > expires_at:
                # 만료된 캐시 삭제
                cache_path.unlink(missing_ok=True)
                logger.info(f"Search cache MISS (expired) for: {keyword}")
                return None

            logger.info(f"Search cache HIT for: {keyword} ({len(entry['value'])} places)")
            return entry["value"]

        except (json.JSONDecodeError, KeyError, OSError) as e:
            logger.warning(f"Corrupted search cache for {keyword}: {e}")
            try:
                cache_path.unlink(missing_ok=True)
            except OSError:
                pass
            return None

    def _set_search_cache(self, keyword: str, places: List[Dict[str, Any]]) -> None:
        """검색 결과 캐시 저장 (동기 버전)"""
        cache_key = self._get_search_cache_key(keyword)
        cache_path = self._get_search_cache_path(cache_key)

        entry = {
            "value": places,
            "expires_at": (datetime.now() + timedelta(seconds=self._search_cache_ttl)).isoformat(),
            "created_at": datetime.now().isoformat(),
            "keyword": keyword,
        }

        try:
            with open(cache_path, 'w', encoding='utf-8') as f:
                json.dump(entry, f, ensure_ascii=False, default=str)
            logger.info(f"Search cache SET for: {keyword} ({len(places)} places, TTL: {self._search_cache_ttl}s)")
        except OSError as e:
            logger.error(f"Failed to write search cache for {keyword}: {e}")

    async def _get_browser(self, force_new: bool = False) -> Optional[Browser]:
        """Playwright browser 가져오기 (프록시 지원)"""
        async with self._lock:
            need_new = force_new or self._browser is None or not self._browser.is_connected()

            if need_new:
                # 기존 브라우저 정리
                if self._browser:
                    try:
                        await self._browser.close()
                    except:
                        pass
                if self._playwright:
                    try:
                        await self._playwright.stop()
                    except:
                        pass

                try:
                    self._playwright = await async_playwright().start()

                    # 프록시 설정
                    launch_args = {
                        "headless": True,
                        "args": [
                            "--no-sandbox",
                            "--disable-dev-shm-usage",
                            "--disable-gpu",
                            "--lang=ko-KR",
                        ]
                    }

                    # 프록시가 설정되어 있으면 추가
                    if self._proxy_config:
                        proxy_url = self._proxy_config["url"]
                        # URL 파싱해서 Playwright 프록시 형식으로 변환
                        # http://user:pass@host:port -> server, username, password
                        if "@" in proxy_url:
                            # 인증 정보 포함
                            auth_part, server_part = proxy_url.rsplit("@", 1)
                            protocol = auth_part.split("://")[0] if "://" in auth_part else "http"
                            creds = auth_part.split("://")[-1]
                            if ":" in creds:
                                username, password = creds.split(":", 1)
                            else:
                                username, password = creds, ""
                            launch_args["proxy"] = {
                                "server": f"{protocol}://{server_part}",
                                "username": username,
                                "password": password,
                            }
                        else:
                            # 인증 정보 없음
                            launch_args["proxy"] = {"server": proxy_url}

                        logger.info(f"Browser using proxy: {server_part if '@' in proxy_url else proxy_url}")

                    self._browser = await self._playwright.chromium.launch(**launch_args)
                    logger.info("Playwright browser initialized")
                except Exception as e:
                    logger.error(f"Failed to initialize browser: {e}")
                    return None
        return self._browser

    async def _wait_for_rate_limit(self):
        """요청 간격 조절 (차단 방지)"""
        now = time.time()
        elapsed = now - self._last_request_time
        if elapsed < self._min_request_interval:
            wait_time = self._min_request_interval - elapsed + random.uniform(0.5, 1.5)
            logger.debug(f"Rate limiting: waiting {wait_time:.1f}s")
            await asyncio.sleep(wait_time)
        self._last_request_time = time.time()

    async def _new_page(self) -> Optional[Page]:
        """새 페이지 생성"""
        browser = await self._get_browser()
        if not browser:
            return None

        user_agent = random.choice(USER_AGENTS)
        context = await browser.new_context(
            viewport={"width": 1920, "height": 1080},
            user_agent=user_agent,
            locale="ko-KR"
        )
        return await context.new_page()

    @staticmethod
    def extract_place_id(url: str) -> Optional[str]:
        """플레이스 URL에서 ID 추출"""
        if not url:
            return None

        url = url.strip()

        # 숫자만 있으면 그대로 반환
        if url.isdigit():
            return url

        # URL에서 숫자 ID 추출 패턴들
        patterns = [
            r"/place/(\d+)",
            r"/restaurant/(\d+)",
            r"/cafe/(\d+)",
            r"/accommodation/(\d+)",
            r"/hospital/(\d+)",
            r"/beauty/(\d+)",
            r"place\.naver\.com/[^/]+/(\d+)",
            r"m\.place\.naver\.com/[^/]+/(\d+)",
            r"/(\d{8,})",
        ]

        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(1)

        # URL 전체에서 8자리 이상 연속된 숫자 찾기
        digit_match = re.search(r"(\d{8,})", url)
        if digit_match:
            return digit_match.group(1)

        return None

    async def _search_naver(self, query: str, max_results: int = 300) -> str:
        """네이버 검색 페이지 HTML 가져오기 (스크롤로 더 많은 결과 로드)"""
        await self._wait_for_rate_limit()

        page = await self._new_page()
        if not page:
            return ""

        try:
            encoded_query = urllib.parse.quote(query)
            url = f"https://search.naver.com/search.naver?where=nexearch&query={encoded_query}"

            await page.goto(url, wait_until="networkidle", timeout=20000)
            await page.wait_for_timeout(2000)

            # 스크롤로 더 많은 결과 로드
            best_html = ""
            best_count = 0
            prev_count = 0
            no_change_count = 0
            scroll_attempts = 0
            max_scroll_attempts = 15

            while scroll_attempts < max_scroll_attempts:
                # 현재 HTML에서 place ID 개수 확인
                html = await page.content()
                current_count = len(set(re.findall(r'"PlaceSummary:(\d+)', html)))
                current_count += len(set(re.findall(r'"RestaurantListSummary:(\d+)', html)))
                current_count += len(set(re.findall(r'"CafeListSummary:(\d+)', html)))
                current_count += len(set(re.findall(r'"AttractionListItem:(\d+)', html)))
                current_count += len(set(re.findall(r'"PlaceListSummary:(\d+)', html)))
                # 추가 패턴: "ID:ID":{"__typename":"Restaurant..."}
                current_count += len(set(re.findall(r'"(\d+):\d+":\{"__typename":"(?:Restaurant|Cafe|Place|Attraction)', html)))

                logger.debug(f"Scroll {scroll_attempts}: found {current_count} places")

                # 가장 많은 결과를 가진 HTML 저장
                if current_count > best_count:
                    best_count = current_count
                    best_html = html

                # 목표 도달하면 중단
                if current_count >= max_results:
                    logger.info(f"Reached target {max_results}, stopping scroll")
                    break

                # 3회 연속 변화 없으면 중단 (더 이상 로드할 데이터 없음)
                if current_count == prev_count:
                    no_change_count += 1
                    if no_change_count >= 3:
                        logger.info(f"No more results after {scroll_attempts} scrolls (best: {best_count})")
                        break
                else:
                    no_change_count = 0

                prev_count = current_count
                scroll_attempts += 1

                # 페이지 끝까지 스크롤
                await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                await page.wait_for_timeout(1200)

                # 추가 스크롤 (중간 위치에서 다시)
                await page.evaluate("window.scrollBy(0, 300)")
                await page.wait_for_timeout(500)

            # 가장 많은 결과를 가진 HTML 반환
            if best_count > 0:
                html = best_html
            else:
                html = await page.content()

            logger.info(f"Search completed with {scroll_attempts} scrolls for '{query}' (found {best_count} places)")
            return html

        except Exception as e:
            logger.error(f"Search error: {e}")
            return ""
        finally:
            try:
                await page.context.close()
            except:
                pass

    async def _search_naver_map(self, query: str, max_results: int = 100) -> List[Dict[str, Any]]:
        """네이버 모바일 지도에서 플레이스 검색 (더 많은 결과 가져오기)"""
        await self._wait_for_rate_limit()

        browser = await self._get_browser()
        if not browser:
            return []

        context = None
        try:
            # 모바일 브라우저로 접속
            context = await browser.new_context(
                viewport={"width": 390, "height": 844},
                user_agent="Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Mobile/15E148 Safari/604.1",
                locale="ko-KR"
            )
            page = await context.new_page()

            encoded_query = urllib.parse.quote(query)
            url = f"https://m.map.naver.com/search2/search.naver?query={encoded_query}"

            await page.goto(url, wait_until="networkidle", timeout=20000)
            await page.wait_for_timeout(3000)

            # 스크롤하면서 결과 수집
            all_ids = set()
            place_data_list = []
            no_change_count = 0
            prev_count = 0

            for i in range(15):  # 최대 15회 스크롤
                html = await page.content()

                # 플레이스 ID 추출
                ids = set(re.findall(r'/place/(\d{8,})', html))
                ids.update(re.findall(r'data-id="(\d{8,})"', html))
                ids.update(re.findall(r'"id":(\d{8,})', html))
                all_ids.update(ids)

                current_count = len(all_ids)
                logger.debug(f"Map scroll {i}: {current_count} IDs")

                if current_count >= max_results:
                    break

                # 3회 연속 변화 없으면 중단
                if current_count == prev_count:
                    no_change_count += 1
                    if no_change_count >= 3:
                        break
                else:
                    no_change_count = 0

                prev_count = current_count

                # 스크롤
                await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                await page.wait_for_timeout(1500)

            logger.info(f"Map search found {len(all_ids)} place IDs for '{query}'")

            # 각 ID에 대해 기본 정보 구성 (상세 정보는 나중에 보강)
            for pid in list(all_ids)[:max_results]:
                place_data_list.append({
                    "place_id": pid,
                    "name": "",
                    "category": "",
                    "address": "",
                    "road_address": "",
                    "phone": "",
                    "visitor_review_count": 0,
                    "blog_review_count": 0,
                    "reservation_review_count": 0,
                    "save_count": 0,
                    "keywords": [],
                    "menu_info": [],
                })

            return place_data_list

        except Exception as e:
            logger.error(f"Map search error: {e}")
            return []
        finally:
            try:
                if context:
                    await context.close()
            except:
                pass

    @staticmethod
    def _parse_count(value: str) -> int:
        """숫자 문자열을 정수로 변환 (콤마, ~, + 등 처리)"""
        if not value:
            return 0
        # ~100, +500 같은 형태 처리
        value = value.replace("~", "").replace("+", "").replace(",", "").strip()
        try:
            return int(value)
        except ValueError:
            return 0

    def _extract_places_from_html(self, html: str) -> List[Dict[str, Any]]:
        """HTML에서 플레이스 데이터 추출 (네이버 2024-2025 형식)"""
        results = []
        seen_ids = set()

        # 패턴 1: "TypeName:ID" 또는 "TypeName:ID:ID" 형식
        # 예: "PlaceSummary:1133548142" 또는 "RestaurantListSummary:1133548142:1133548142"
        place_patterns = [
            r'"PlaceSummary:(\d+)(?::\d+)?"\s*:\s*\{',
            r'"AttractionListItem:(\d+)(?::\d+)?"\s*:\s*\{',
            r'"AttractionAdSummary:(\d+)(?::\d+)?"\s*:\s*\{',
            r'"RestaurantListSummary:(\d+)(?::\d+)?"\s*:\s*\{',
            r'"RestaurantAdSummary:(\d+)(?::\d+)?"\s*:\s*\{',
            r'"CafeListSummary:(\d+)(?::\d+)?"\s*:\s*\{',
            r'"PlaceListSummary:(\d+)(?::\d+)?"\s*:\s*\{',
            r'"PlaceDetailBase:(\d+)(?::\d+)?"\s*:\s*\{',
        ]

        # 패턴 2: "ID:ID" 형식 + __typename (예: "1133548142:1133548142":{"__typename":"RestaurantListSummary")
        typename_pattern = r'"(\d+):(\d+)"\s*:\s*\{\s*"__typename"\s*:\s*"(Restaurant|Cafe|Place|Attraction)[A-Za-z]*"'

        # 패턴 1 처리
        for place_pattern in place_patterns:
            for match in re.finditer(place_pattern, html):
                pid = match.group(1)
                if pid in seen_ids:
                    continue

                seen_ids.add(pid)

                start = match.end() - 1
                # 객체 끝 찾기 (중괄호 균형)
                brace_count = 0
                end = start
                for i in range(start, min(start + 15000, len(html))):
                    if html[i] == '{':
                        brace_count += 1
                    elif html[i] == '}':
                        brace_count -= 1
                        if brace_count == 0:
                            end = i + 1
                            break

                obj_str = html[start:end]

                # 이름 추출 (HTML 태그 제거)
                name = ""
                name_match = re.search(r'"name"\s*:\s*"([^"]+)"', obj_str)
                if name_match:
                    name = name_match.group(1)
                    try:
                        name = json.loads(f'"{name}"')
                    except:
                        pass
                    name = re.sub(r'<[^>]+>', '', name)

                if not name:
                    continue

                # 카테고리
                category = ""
                cat_match = re.search(r'"category"\s*:\s*"([^"]+)"', obj_str)
                if cat_match:
                    category = cat_match.group(1).split(",")[0]

                # 주소
                address = ""
                addr_match = re.search(r'"address"\s*:\s*"([^"]+)"', obj_str)
                if addr_match:
                    address = addr_match.group(1)

                road_address = ""
                road_match = re.search(r'"roadAddress"\s*:\s*"([^"]+)"', obj_str)
                if road_match:
                    road_address = road_match.group(1)

                # 전화번호
                phone = ""
                phone_match = re.search(r'"(?:virtual)?[Pp]hone"\s*:\s*"([^"]+)"', obj_str)
                if phone_match:
                    phone = phone_match.group(1)

                # 방문자 리뷰 수
                visitor_review_count = 0
                visitor_match = re.search(r'"visitorReview(?:s)?(?:Total|Count)"\s*:\s*"?([0-9,]+)"?', obj_str)
                if visitor_match:
                    visitor_review_count = self._parse_count(visitor_match.group(1))

                # 블로그 리뷰 수
                blog_review_count = 0
                blog_match = re.search(r'"blogCafeReviewCount"\s*:\s*"?([0-9,]+)"?', obj_str)
                if blog_match:
                    blog_review_count = self._parse_count(blog_match.group(1))

                results.append({
                    "place_id": pid,
                    "name": name,
                    "category": category,
                    "address": address,
                    "road_address": road_address,
                    "phone": phone,
                    "visitor_review_count": visitor_review_count,
                    "blog_review_count": blog_review_count,
                    "reservation_review_count": 0,
                    "save_count": 0,
                    "keywords": [],
                    "menu_info": [],
                })

        # 패턴 2 처리: "ID:ID":{"__typename":"RestaurantListSummary"...} 형식
        for match in re.finditer(typename_pattern, html):
            pid = match.group(1)  # 첫 번째 ID 사용
            if pid in seen_ids:
                continue

            seen_ids.add(pid)

            # 매치 시작점에서 객체 찾기
            search_start = match.start()
            obj_start = html.find('{', search_start)
            if obj_start == -1:
                continue

            # 객체 끝 찾기
            brace_count = 0
            end = obj_start
            for i in range(obj_start, min(obj_start + 15000, len(html))):
                if html[i] == '{':
                    brace_count += 1
                elif html[i] == '}':
                    brace_count -= 1
                    if brace_count == 0:
                        end = i + 1
                        break

            obj_str = html[obj_start:end]

            # 이름 추출
            name = ""
            name_match = re.search(r'"name"\s*:\s*"([^"]+)"', obj_str)
            if name_match:
                name = name_match.group(1)
                try:
                    name = json.loads(f'"{name}"')
                except:
                    pass
                name = re.sub(r'<[^>]+>', '', name)

            if not name:
                continue

            # 카테고리
            category = ""
            cat_match = re.search(r'"category"\s*:\s*"([^"]+)"', obj_str)
            if cat_match:
                category = cat_match.group(1).split(",")[0]

            # 주소
            address = ""
            addr_match = re.search(r'"address"\s*:\s*"([^"]+)"', obj_str)
            if addr_match:
                address = addr_match.group(1)

            road_address = ""
            road_match = re.search(r'"roadAddress"\s*:\s*"([^"]+)"', obj_str)
            if road_match:
                road_address = road_match.group(1)

            # 전화번호
            phone = ""
            phone_match = re.search(r'"(?:virtual)?[Pp]hone"\s*:\s*"([^"]+)"', obj_str)
            if phone_match:
                phone = phone_match.group(1)

            # 방문자 리뷰 수
            visitor_review_count = 0
            visitor_match = re.search(r'"visitorReview(?:s)?(?:Total|Count)"\s*:\s*"?([0-9,]+)"?', obj_str)
            if visitor_match:
                visitor_review_count = self._parse_count(visitor_match.group(1))

            # 블로그 리뷰 수
            blog_review_count = 0
            blog_match = re.search(r'"blogCafeReviewCount"\s*:\s*"?([0-9,]+)"?', obj_str)
            if blog_match:
                blog_review_count = self._parse_count(blog_match.group(1))

            results.append({
                "place_id": pid,
                "name": name,
                "category": category,
                "address": address,
                "road_address": road_address,
                "phone": phone,
                "visitor_review_count": visitor_review_count,
                "blog_review_count": blog_review_count,
                "reservation_review_count": 0,
                "save_count": 0,
                "keywords": [],
                "menu_info": [],
            })

        logger.info(f"Extracted {len(results)} places from HTML")
        return results

    async def _get_place_name_from_detail(self, place_id: str) -> Optional[str]:
        """플레이스 상세 페이지에서 업체명 가져오기"""
        headers = {
            "User-Agent": random.choice(USER_AGENTS),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "ko-KR,ko;q=0.9",
        }

        # 프록시 URL
        proxy_url = self._proxy_config["url"] if self._proxy_config else None

        # 여러 URL 형태 시도
        urls = [
            f"https://m.place.naver.com/restaurant/{place_id}/home",
            f"https://m.place.naver.com/place/{place_id}/home",
        ]

        for url in urls:
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(
                        url,
                        headers=headers,
                        proxy=proxy_url,
                        timeout=aiohttp.ClientTimeout(total=15)
                    ) as response:
                        if response.status != 200:
                            continue

                        html = await response.text()

                        # 차단 확인
                        if "서비스 이용이 제한" in html:
                            logger.warning(f"IP blocked for {url}")
                            continue

                        # 업체명 추출
                        # 방법 1: APOLLO_STATE에서 name 추출
                        apollo_match = re.search(r'"name"\s*:\s*"([^"]+)"', html)
                        if apollo_match:
                            name = apollo_match.group(1)
                            # JSON 유니코드 디코딩
                            try:
                                name = json.loads(f'"{name}"')
                            except:
                                pass
                            if name and len(name) > 1:
                                logger.info(f"Found place name from detail page: {name}")
                                return name

                        # 방법 2: <title> 태그에서 추출
                        title_match = re.search(r'<title>([^<]+)</title>', html)
                        if title_match:
                            title = title_match.group(1)
                            # "업체명 : 네이버 플레이스" 형식에서 업체명 추출
                            if " : " in title:
                                name = title.split(" : ")[0].strip()
                                if name and len(name) > 1:
                                    return name

            except Exception as e:
                logger.debug(f"Failed to fetch name from {url}: {e}")
                continue

        return None

    async def get_place_info(self, place_id: str) -> Optional[Dict[str, Any]]:
        """플레이스 상세 정보 조회"""
        result = {
            "place_id": place_id,
            "name": "",
            "category": "",
            "address": "",
            "road_address": "",
            "phone": "",
            "visitor_review_count": 0,
            "blog_review_count": 0,
            "reservation_review_count": 0,
            "save_count": 0,
            "photo_count": 0,
            "description": "",
            "keywords": [],
            "menu_info": [],
            "business_hours": []
        }

        try:
            # 방법 1: 플레이스 상세 페이지에서 업체명 가져오기
            place_name = await self._get_place_name_from_detail(place_id)

            if place_name:
                logger.info(f"Got place name '{place_name}' for {place_id}, searching...")

                # 업체명으로 네이버 검색
                html = await self._search_naver(place_name)

                if html:
                    places = self._extract_places_from_html(html)

                    # place_id와 일치하는 결과 찾기
                    for place in places:
                        if str(place.get("place_id")) == str(place_id):
                            result.update(place)
                            logger.info(f"Found place info: {result['name']} ({place_id})")
                            break

                    # 일치하는 결과가 없으면 이름이 정확히 일치하는 것 찾기
                    if not result["name"]:
                        for place in places:
                            if place.get("name") == place_name:
                                result.update(place)
                                result["place_id"] = place_id
                                logger.info(f"Found place by name match: {result['name']} ({place_id})")
                                break

            # 방법 2: 검색 결과가 없으면 상세 페이지에서 직접 데이터 추출
            if not result["name"]:
                logger.info(f"Trying to get info directly from detail page for {place_id}")
                detail_data = await self._fetch_place_detail_full(place_id)
                if detail_data and detail_data.get("name"):
                    result.update(detail_data)

            # 메뉴 정보가 없으면 플레이스 상세 페이지에서 추가로 가져오기
            if not result.get("menu_info"):
                detail_data = await self._fetch_place_detail(place_id)
                if detail_data:
                    if detail_data.get("menu_info"):
                        result["menu_info"] = detail_data["menu_info"]
                    if detail_data.get("keywords") and not result.get("keywords"):
                        result["keywords"] = detail_data["keywords"]
                    if detail_data.get("business_hours"):
                        result["business_hours"] = detail_data["business_hours"]

        except Exception as e:
            logger.error(f"Error getting place info: {e}")

        return result

    async def _fetch_place_detail_full(self, place_id: str) -> Optional[Dict[str, Any]]:
        """플레이스 상세 페이지에서 전체 정보 추출 (aiohttp 사용)"""
        headers = {
            "User-Agent": random.choice(USER_AGENTS),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "ko-KR,ko;q=0.9",
        }

        proxy_url = self._proxy_config["url"] if self._proxy_config else None

        urls = [
            f"https://m.place.naver.com/restaurant/{place_id}/home",
            f"https://m.place.naver.com/place/{place_id}/home",
        ]

        for url in urls:
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(
                        url,
                        headers=headers,
                        proxy=proxy_url,
                        timeout=aiohttp.ClientTimeout(total=15)
                    ) as response:
                        if response.status != 200:
                            continue

                        html = await response.text()

                        if "서비스 이용이 제한" in html:
                            continue

                        result = {
                            "place_id": place_id,
                            "name": "",
                            "category": "",
                            "address": "",
                            "road_address": "",
                            "phone": "",
                            "visitor_review_count": 0,
                            "blog_review_count": 0,
                            "reservation_review_count": 0,
                            "save_count": 0,
                            "keywords": [],
                        }

                        # APOLLO_STATE에서 데이터 추출
                        # 업체명
                        name_match = re.search(r'"name"\s*:\s*"([^"]+)"', html)
                        if name_match:
                            try:
                                result["name"] = json.loads(f'"{name_match.group(1)}"')
                            except:
                                result["name"] = name_match.group(1)

                        # 카테고리
                        cat_match = re.search(r'"category"\s*:\s*"([^"]+)"', html)
                        if cat_match:
                            result["category"] = cat_match.group(1).split(",")[0]

                        # 주소
                        addr_match = re.search(r'"address"\s*:\s*"([^"]+)"', html)
                        if addr_match:
                            result["address"] = addr_match.group(1)

                        road_match = re.search(r'"roadAddress"\s*:\s*"([^"]+)"', html)
                        if road_match:
                            result["road_address"] = road_match.group(1)

                        # 전화번호
                        phone_match = re.search(r'"phone"\s*:\s*"([^"]+)"', html)
                        if phone_match:
                            result["phone"] = phone_match.group(1)

                        # 방문자 리뷰 수
                        visitor_match = re.search(r'"visitorReviewsTotal"\s*:\s*(\d+)', html)
                        if visitor_match:
                            result["visitor_review_count"] = int(visitor_match.group(1))
                        else:
                            visitor_match2 = re.search(r'"visitorReviewCount"\s*:\s*"?(\d+)"?', html)
                            if visitor_match2:
                                result["visitor_review_count"] = int(visitor_match2.group(1))

                        # 블로그 리뷰 수 (여러 패턴 시도)
                        blog_count = 0
                        # 패턴 1: og:description 메타 태그 (블로그리뷰 1,884)
                        og_match = re.search(r'블로그리뷰\s*([0-9,]+)', html)
                        if og_match:
                            blog_count = int(og_match.group(1).replace(',', ''))
                        # 패턴 2: 블로그 리뷰 텍스트 (공백 포함)
                        if blog_count == 0:
                            blog_text_match = re.search(r'블로그\s*리뷰\s*([0-9,]+)', html)
                            if blog_text_match:
                                blog_count = int(blog_text_match.group(1).replace(',', ''))
                        # 패턴 3: JSON 필드
                        if blog_count == 0:
                            blog_match = re.search(r'"blogCafeReviewCount"\s*:\s*"?([0-9,]+)"?', html)
                            if blog_match:
                                blog_count = int(blog_match.group(1).replace(',', ''))
                        result["blog_review_count"] = blog_count

                        # 저장수
                        save_match = re.search(r'"saveCount"\s*:\s*(\d+)', html)
                        if save_match:
                            result["save_count"] = int(save_match.group(1))

                        if result["name"]:
                            logger.info(f"Extracted full info from detail page: {result['name']}")
                            return result

            except Exception as e:
                logger.debug(f"Failed to fetch full detail from {url}: {e}")
                continue

        return None

    def _get_cached_save_count(self, place_id: str) -> Optional[int]:
        """캐시된 저장수 가져오기"""
        if place_id in self._save_count_cache:
            cached = self._save_count_cache[place_id]
            if time.time() - cached["time"] < self._cache_ttl:
                return cached["save_count"]
        return None

    def _cache_save_count(self, place_id: str, save_count: int):
        """저장수 캐싱"""
        self._save_count_cache[place_id] = {
            "save_count": save_count,
            "time": time.time()
        }

    async def _fetch_save_count_api(self, place_id: str) -> int:
        """aiohttp로 저장수 가져오기 시도 (가벼운 방법, 프록시 지원)"""
        headers = {
            "User-Agent": random.choice(USER_AGENTS),
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "ko-KR,ko;q=0.9",
            "Referer": f"https://m.place.naver.com/restaurant/{place_id}/home",
        }

        # 여러 API 엔드포인트 시도
        urls = [
            f"https://m.place.naver.com/restaurant/{place_id}/home",
            f"https://m.place.naver.com/place/{place_id}/home",
        ]

        # 프록시 URL (있으면)
        proxy_url = self._proxy_config["url"] if self._proxy_config else None

        for url in urls:
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(
                        url,
                        headers=headers,
                        proxy=proxy_url,
                        timeout=aiohttp.ClientTimeout(total=15)
                    ) as response:
                        if response.status == 200:
                            html = await response.text()

                            # 차단 확인
                            if "서비스 이용이 제한" in html:
                                logger.warning(f"IP blocked for {url}")
                                continue

                            # saveCount 찾기
                            save_match = re.search(r'"saveCount"\s*:\s*(\d+)', html)
                            if save_match:
                                return int(save_match.group(1))
            except Exception as e:
                logger.debug(f"API fetch failed for {url}: {e}")
                continue

        return 0

    async def _fetch_place_detail(self, place_id: str, retry: bool = True) -> Optional[Dict[str, Any]]:
        """플레이스 상세 페이지에서 저장수, 리뷰수 등 추가 정보 가져오기"""
        result = {
            "visitor_review_count": 0,
            "blog_review_count": 0,
            "save_count": 0,
            "menu_info": [],
            "keywords": [],
            "business_hours": []
        }

        # 1. 캐시 확인
        cached_save = self._get_cached_save_count(place_id)
        if cached_save is not None and cached_save > 0:
            result["save_count"] = cached_save
            logger.info(f"Using cached save_count for {place_id}: {cached_save}")
            return result

        # 2. API로 먼저 시도 (가벼움)
        await self._wait_for_rate_limit()
        api_save_count = await self._fetch_save_count_api(place_id)
        if api_save_count > 0:
            result["save_count"] = api_save_count
            self._cache_save_count(place_id, api_save_count)
            logger.info(f"Got save_count from API for {place_id}: {api_save_count}")
            return result

        # 3. Playwright로 시도
        context = None
        try:
            await self._wait_for_rate_limit()

            browser = await self._get_browser()
            if not browser:
                return result

            user_agent = random.choice(USER_AGENTS)
            context = await browser.new_context(
                viewport={"width": 1920, "height": 1080},
                user_agent=user_agent,
                locale="ko-KR",
                timezone_id="Asia/Seoul",
            )

            page = await context.new_page()

            # 봇 탐지 우회 스크립트
            await page.add_init_script("""
                Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
                Object.defineProperty(navigator, 'plugins', { get: () => [1,2,3,4,5] });
            """)

            url = f"https://m.place.naver.com/restaurant/{place_id}/home"
            await page.goto(url, wait_until="domcontentloaded", timeout=20000)
            await page.wait_for_timeout(4000)

            html = await page.content()

            # 차단 확인
            if "서비스 이용이 제한" in html:
                logger.warning(f"IP blocked when fetching detail for {place_id}")
                return result

            # __APOLLO_STATE__에서 데이터 추출
            apollo_match = re.search(r'window\.__APOLLO_STATE__\s*=\s*(\{.*?\});', html, re.DOTALL)
            if apollo_match:
                apollo_str = apollo_match.group(1)

                visitor_match = re.search(r'"visitorReviewsTotal"\s*:\s*(\d+)', apollo_str)
                if visitor_match:
                    result["visitor_review_count"] = int(visitor_match.group(1))

                blog_match = re.search(r'"(?:blog|cafe)ReviewCount"\s*:\s*"?([0-9,]+)"?', apollo_str, re.IGNORECASE)
                if blog_match:
                    result["blog_review_count"] = int(blog_match.group(1).replace(',', ''))

                save_match = re.search(r'"saveCount"\s*:\s*(\d+)', apollo_str)
                if save_match:
                    result["save_count"] = int(save_match.group(1))

            # HTML에서 저장수 패턴 찾기
            if result["save_count"] == 0:
                save_patterns = [
                    r'"saveCount"\s*:\s*(\d+)',
                    r'>저장</span>\s*<[^>]*>\s*([0-9,]+)',
                    r'저장[^<]*</[^>]+>\s*<[^>]+>\s*([0-9,]+)',
                ]
                for pattern in save_patterns:
                    save_match = re.search(pattern, html)
                    if save_match:
                        save_str = save_match.group(1).replace(",", "")
                        if save_str.isdigit() and int(save_str) > 0:
                            result["save_count"] = int(save_str)
                            break

            # 캐싱
            if result["save_count"] > 0:
                self._cache_save_count(place_id, result["save_count"])

            logger.info(f"Fetched detail for {place_id}: save={result['save_count']}")
            return result

        except Exception as e:
            logger.error(f"Error fetching place detail: {e}")
            if retry and "closed" in str(e).lower():
                logger.info("Retrying with fresh browser...")
                await self._get_browser(force_new=True)
                return await self._fetch_place_detail(place_id, retry=False)
            return result
        finally:
            try:
                if context:
                    await context.close()
            except:
                pass

    async def search_places(self, keyword: str, max_results: int = 300, enrich_blog: bool = False, force_refresh: bool = False) -> List[Dict[str, Any]]:
        """키워드로 플레이스 검색 (캐싱 적용)

        Args:
            keyword: 검색 키워드
            max_results: 최대 결과 수
            enrich_blog: 블로그 리뷰 보강 여부
            force_refresh: True면 캐시 무시하고 새로 검색
        """
        # 1. 캐시 확인 (force_refresh가 아닌 경우)
        if not force_refresh:
            cached_places = self._get_cached_search_result(keyword)
            if cached_places is not None:
                # 캐시된 결과에서 블로그 보강이 필요하면 수행
                if enrich_blog and cached_places:
                    top_places = cached_places[:min(30, max_results)]
                    top_places = await self._enrich_blog_reviews(top_places)
                    cached_places = top_places + cached_places[30:]
                return cached_places[:max_results]

        # 2. 캐시 미스: 실제 검색 수행
        places = []
        seen_ids = set()

        try:
            # 2-1. 네이버 통합 검색에서 상세 정보 포함된 결과 가져오기
            html = await self._search_naver(keyword, max_results)

            if html:
                naver_places = self._extract_places_from_html(html)
                logger.info(f"Naver search found {len(naver_places)} places for '{keyword}'")

                for place in naver_places:
                    pid = str(place.get("place_id"))
                    if pid and pid not in seen_ids:
                        seen_ids.add(pid)
                        places.append(place)

            # 2-2. 더 많은 결과가 필요하면 네이버 지도에서 추가 ID 가져오기
            if len(places) < max_results:
                map_places = await self._search_naver_map(keyword, max_results)
                logger.info(f"Map search found {len(map_places)} additional IDs for '{keyword}'")

                for place in map_places:
                    pid = str(place.get("place_id"))
                    if pid and pid not in seen_ids:
                        seen_ids.add(pid)
                        places.append(place)

            logger.info(f"Total: {len(places)} unique places for '{keyword}'")

            # 3. 캐시에 저장 (블로그 보강 전 원본 저장)
            if places:
                self._set_search_cache(keyword, places)

            # 블로그 리뷰 보강 (상위 30개만)
            if enrich_blog and places:
                top_places = places[:min(30, max_results)]
                top_places = await self._enrich_blog_reviews(top_places)
                places = top_places + places[30:]

            return places[:max_results]

        except Exception as e:
            logger.error(f"Search error: {e}")

        return places[:max_results] if places else []

    async def _enrich_place_names(self, places: List[Dict], limit: int = 50) -> List[Dict]:
        """이름이 없는 업체들의 기본 정보 보강"""
        import aiohttp

        async def fetch_place_name(place: Dict) -> Dict:
            if place.get("name"):
                return place

            place_id = place.get("place_id")
            if not place_id:
                return place

            headers = {
                "User-Agent": random.choice(USER_AGENTS),
                "Accept": "text/html",
                "Accept-Language": "ko-KR,ko;q=0.9",
            }

            urls = [
                f"https://m.place.naver.com/restaurant/{place_id}/home",
                f"https://m.place.naver.com/place/{place_id}/home",
            ]

            proxy_url = self._proxy_config["url"] if self._proxy_config else None

            for url in urls:
                try:
                    async with aiohttp.ClientSession() as session:
                        async with session.get(
                            url, headers=headers, proxy=proxy_url,
                            timeout=aiohttp.ClientTimeout(total=10)
                        ) as resp:
                            if resp.status != 200:
                                continue
                            html = await resp.text()

                            if "서비스 이용이 제한" in html:
                                continue

                            # 이름 추출
                            name_match = re.search(r'"name"\s*:\s*"([^"]+)"', html)
                            if name_match:
                                try:
                                    place["name"] = json.loads(f'"{name_match.group(1)}"')
                                except:
                                    place["name"] = name_match.group(1)

                            # 카테고리
                            cat_match = re.search(r'"category"\s*:\s*"([^"]+)"', html)
                            if cat_match:
                                place["category"] = cat_match.group(1).split(",")[0]

                            # 방문자 리뷰
                            visitor_match = re.search(r'"visitorReviewsTotal"\s*:\s*(\d+)', html)
                            if visitor_match:
                                place["visitor_review_count"] = int(visitor_match.group(1))

                            # 블로그 리뷰
                            blog_match = re.search(r'블로그리뷰\s*([0-9,]+)', html)
                            if blog_match:
                                place["blog_review_count"] = int(blog_match.group(1).replace(',', ''))

                            if place.get("name"):
                                logger.debug(f"Enriched place name: {place['name']}")
                                return place

                except Exception as e:
                    logger.debug(f"Failed to enrich {place_id}: {e}")
                    continue

            return place

        # 이름 없는 업체들만 필터링 (최대 limit개)
        places_to_enrich = [p for p in places if not p.get("name")][:limit]
        places_with_name = [p for p in places if p.get("name")]

        if places_to_enrich:
            # 병렬로 처리 (최대 10개씩)
            enriched = []
            batch_size = 10
            for i in range(0, len(places_to_enrich), batch_size):
                batch = places_to_enrich[i:i+batch_size]
                results = await asyncio.gather(*[fetch_place_name(p) for p in batch])
                enriched.extend(results)
                if i + batch_size < len(places_to_enrich):
                    await asyncio.sleep(0.5)  # 차단 방지

            # 결합: 이름 있는 것 + 보강된 것 + 나머지
            remaining = [p for p in places if not p.get("name")][limit:]
            return places_with_name + enriched + remaining

        return places

    async def get_place_rank(
        self,
        place_id: str,
        keyword: str,
        max_search: int = 300,
        traffic_count: Optional[int] = None  # 내 업체 유입수 (사용자 입력)
    ) -> Dict[str, Any]:
        """특정 플레이스의 키워드 검색 순위 조회"""
        # 순위 조회 시에는 블로그 보강 건너뜀 (아래에서 별도로 보강)
        search_results = await self.search_places(keyword, max_search, enrich_blog=False)

        # 이름이 없는 업체들 정보 보강 (상위 50개)
        search_results = await self._enrich_place_names(search_results, limit=50)

        # 상위 30개 업체 데이터 보강
        top_places = search_results[:30]

        # 블로그 리뷰가 0인 업체들은 상세 페이지에서 가져오기
        top_places = await self._enrich_blog_reviews(top_places)

        # 최신성(최근 1주일 리뷰 수) 수집
        top_places = await self._enrich_freshness(top_places)

        search_results = top_places + search_results[30:]

        result = {
            "place_id": place_id,
            "keyword": keyword,
            "rank": None,
            "total_results": len(search_results),
            "competitors": [],
            "target_place": None
        }

        for idx, place in enumerate(search_results):
            place_data = {
                "rank": idx + 1,
                **place
            }

            if str(place.get("place_id")) == str(place_id):
                result["rank"] = idx + 1
                result["target_place"] = place_data

            # 전체 업체를 경쟁사로 저장 (순위권 밖 매장도 확인 가능)
            result["competitors"].append(place_data)

        # 키워드별 요소 분석 추가
        if len(search_results) >= 3:
            result["analysis"] = self._analyze_keyword_factors(
                search_results,
                place_id,
                traffic_count=traffic_count  # 유입수 전달
            )
        else:
            result["analysis"] = None

        return result

    async def _enrich_blog_reviews(self, places: List[Dict]) -> List[Dict]:
        """블로그 리뷰가 0인 업체들의 상세 정보 보강"""
        import aiohttp

        async def fetch_blog_count(place: Dict) -> Dict:
            if place.get("blog_review_count", 0) > 0:
                return place

            place_id = place.get("place_id")
            if not place_id:
                return place

            headers = {
                "User-Agent": random.choice(USER_AGENTS),
                "Accept": "text/html",
                "Accept-Language": "ko-KR,ko;q=0.9",
            }

            urls = [
                f"https://m.place.naver.com/place/{place_id}/home",
                f"https://m.place.naver.com/restaurant/{place_id}/home",
            ]

            proxy_url = self._proxy_config["url"] if self._proxy_config else None

            for url in urls:
                try:
                    async with aiohttp.ClientSession() as session:
                        async with session.get(
                            url, headers=headers, proxy=proxy_url,
                            timeout=aiohttp.ClientTimeout(total=10)
                        ) as resp:
                            if resp.status != 200:
                                continue
                            html = await resp.text()

                            if "서비스 이용이 제한" in html:
                                continue

                            # 블로그 리뷰 파싱
                            blog_count = 0
                            # 패턴 1: og:description (블로그리뷰 1,884 또는 블로그리뷰 55)
                            og_match = re.search(r'블로그리뷰\s*([0-9,]+)', html)
                            if og_match:
                                blog_count = int(og_match.group(1).replace(',', ''))
                            # 패턴 2: 블로그 리뷰 (공백 포함)
                            if blog_count == 0:
                                blog_match = re.search(r'블로그\s*리뷰\s*([0-9,]+)', html)
                                if blog_match:
                                    blog_count = int(blog_match.group(1).replace(',', ''))
                            # 패턴 3: JSON 필드
                            if blog_count == 0:
                                json_match = re.search(r'"blogCafeReviewCount"\s*:\s*"?([0-9,]+)"?', html)
                                if json_match:
                                    blog_count = int(json_match.group(1).replace(',', ''))

                            if blog_count > 0:
                                place["blog_review_count"] = blog_count
                                logger.debug(f"Enriched blog count for {place.get('name')}: {blog_count}")
                                return place
                except Exception as e:
                    logger.debug(f"Failed to enrich {place_id}: {e}")
                    continue

            return place

        # 병렬로 처리 (최대 10개씩)
        enriched = []
        batch_size = 10
        for i in range(0, len(places), batch_size):
            batch = places[i:i+batch_size]
            results = await asyncio.gather(*[fetch_blog_count(p) for p in batch])
            enriched.extend(results)

        return enriched

    async def _enrich_freshness(self, places: List[Dict]) -> List[Dict]:
        """각 업체의 최신성(최근 1주일 리뷰 수) 수집 - HTML 파싱 방식"""
        import aiohttp
        from datetime import datetime, timedelta

        async def fetch_freshness(place: Dict) -> Dict:
            place_id = place.get("place_id")
            if not place_id:
                place["freshness_count"] = 0
                return place

            headers = {
                "User-Agent": random.choice(USER_AGENTS),
                "Accept": "text/html,application/xhtml+xml",
                "Accept-Language": "ko-KR,ko;q=0.9",
            }

            # 리뷰 페이지 URL
            urls = [
                f"https://m.place.naver.com/restaurant/{place_id}/review/visitor",
                f"https://m.place.naver.com/place/{place_id}/review/visitor",
            ]

            proxy_url = self._proxy_config["url"] if self._proxy_config else None
            week_count = 0

            for url in urls:
                try:
                    async with aiohttp.ClientSession() as session:
                        async with session.get(
                            url, headers=headers, proxy=proxy_url,
                            timeout=aiohttp.ClientTimeout(total=10)
                        ) as resp:
                            if resp.status != 200:
                                continue

                            html = await resp.text()

                            if "서비스 이용이 제한" in html:
                                continue

                            # 방법 1: 리뷰 ID에서 날짜 추출 (MongoDB ObjectId)
                            # 리뷰 ID 패턴: "id":"6761..." (24자리 hex)
                            review_ids = re.findall(r'"id"\s*:\s*"([a-f0-9]{24})"', html)

                            today = datetime.now()
                            week_ago = today - timedelta(days=7)

                            for rid in review_ids[:30]:  # 최근 30개만
                                try:
                                    # ObjectId의 처음 8자리는 Unix timestamp (초)
                                    timestamp = int(rid[:8], 16)
                                    review_date = datetime.fromtimestamp(timestamp)
                                    if review_date >= week_ago:
                                        week_count += 1
                                except:
                                    pass

                            # 방법 2: 날짜 텍스트 파싱 (fallback)
                            if week_count == 0:
                                # "n일 전", "오늘", "어제" 패턴
                                today_count = len(re.findall(r'오늘|방금', html))
                                yesterday_count = len(re.findall(r'어제', html))
                                days_ago = re.findall(r'(\d+)일\s*전', html)

                                week_count = today_count + yesterday_count
                                for d in days_ago:
                                    if int(d) <= 7:
                                        week_count += 1

                            if week_count > 0:
                                break

                except Exception as e:
                    logger.debug(f"Failed to fetch freshness for {place_id}: {e}")
                    continue

            place["freshness_count"] = week_count
            logger.debug(f"Freshness for {place.get('name')}: {week_count}")
            return place

        # 병렬로 처리 (최대 5개씩 - 속도 조절)
        enriched = []
        batch_size = 5
        for i in range(0, len(places), batch_size):
            batch = places[i:i+batch_size]
            results = await asyncio.gather(*[fetch_freshness(p) for p in batch])
            enriched.extend(results)
            if i + batch_size < len(places):
                await asyncio.sleep(0.5)  # 차단 방지

        return enriched

    def _extract_review_date_from_id(self, review_id: str) -> Optional[datetime]:
        """MongoDB ObjectId에서 날짜 추출"""
        try:
            if len(review_id) >= 8:
                timestamp = int(review_id[:8], 16)
                return datetime.fromtimestamp(timestamp)
        except:
            pass
        return None

    def _calculate_review_freshness(self, reviews: List[Dict]) -> Dict[str, Any]:
        """리뷰 최신성 계산"""
        if not reviews:
            return {"week_ratio": 0, "month_ratio": 0, "total": 0}

        today = datetime.now()
        week_count = 0
        month_count = 0
        total = 0

        for review in reviews:
            review_id = review.get("review_id", "")
            date = self._extract_review_date_from_id(review_id)
            if date:
                total += 1
                days_ago = (today - date).days
                if days_ago <= 7:
                    week_count += 1
                if days_ago <= 30:
                    month_count += 1

        return {
            "week_count": week_count,
            "month_count": month_count,
            "total": total,
            "week_ratio": round(week_count / total * 100, 1) if total > 0 else 0,
            "month_ratio": round(month_count / total * 100, 1) if total > 0 else 0,
        }

    def _get_relative_ctr(self, rank: int) -> float:
        """순위별 상대적 CTR 반환 (1위 대비)"""
        if rank <= 0:
            return 0
        rank1_ctr = RANK_CTR.get(1, 0.35)
        rank_ctr = RANK_CTR.get(rank, 0.02 / rank if rank > 10 else 0.02)
        return rank_ctr / rank1_ctr  # 1위 대비 비율

    def _analyze_keyword_factors(
        self,
        places: List[Dict],
        target_place_id: str,
        traffic_count: Optional[int] = None  # 내 업체 유입수 (사용자 입력)
    ) -> Dict[str, Any]:
        """
        키워드별 순위 요소 분석 - 상관관계 기반 가중치 역산

        4가지 가중치:
        1. 방문자 리뷰 (측정 가능)
        2. 블로그 리뷰 (측정 가능)
        3. 최신성 (측정 가능 - 최근 1주일 리뷰 수)
        4. 히든 (저장수 + 유입수, 측정 불가 → 역산)
        """
        analysis = {
            "factor_weights": {
                "visitor_review": 0,
                "blog_review": 0,
                "freshness": 0,
                "hidden": 0,  # 유입수
            },
            "place_data": [],  # 각 업체별 데이터
            "ranking_explanation": "",
            "target_analysis": None,
            "recommendations": [],
            "user_traffic_count": traffic_count,  # 사용자 입력 유입수
        }

        try:
            top_places = places[:30]  # 30개까지 분석 (통계적 유의성 향상)
            n = len(top_places)

            if n < 3:
                return analysis

            # ========== Step 1: 기초 데이터 수집 ==========
            place_data = []

            # 첫 번째 업체 카테고리로 업종 판단 (맛집/카페 vs 기타)
            first_category = top_places[0].get("category", "") if top_places else ""
            is_food_cafe = is_food_cafe_category(first_category)

            for i, place in enumerate(top_places):
                rank = i + 1
                visitor = place.get("visitor_review_count", 0)
                blog = place.get("blog_review_count", 0)
                freshness = place.get("freshness_count", 0)  # 최근 1주일 리뷰 수
                category = place.get("category", "")
                save_count = place.get("save_count", 0) if is_food_cafe else 0  # 맛집/카페만 저장수 사용

                place_data.append({
                    "place_id": place.get("place_id"),
                    "name": place.get("name"),
                    "rank": rank,
                    "category": category,
                    "visitor_review_count": visitor,
                    "blog_review_count": blog,
                    "freshness_count": freshness,
                    "save_count": save_count,  # 저장수 (맛집/카페만)
                })

            # 업종 정보 저장
            analysis["is_food_cafe"] = is_food_cafe

            # ========== Step 2: 각 지표별 순위 계산 ==========
            def assign_ranks(data, key):
                """해당 지표 기준 순위 부여"""
                sorted_data = sorted(data, key=lambda x: x[key], reverse=True)
                for r, pd in enumerate(sorted_data, 1):
                    for orig in data:
                        if orig["place_id"] == pd["place_id"]:
                            orig[f"{key}_rank"] = r
                            break

            assign_ranks(place_data, "visitor_review_count")
            assign_ranks(place_data, "blog_review_count")
            assign_ranks(place_data, "freshness_count")
            if is_food_cafe:
                assign_ranks(place_data, "save_count")  # 맛집/카페만 저장수 순위

            # ========== Step 3: 스피어만 상관계수 계산 ==========
            def calc_spearman(data, value_key, rank_key):
                """순위 상관계수 계산 (스피어만)"""
                n = len(data)
                if n < 3:
                    return 0

                # 모든 값이 같으면 상관관계 없음 (0)
                values = [pd[value_key] for pd in data]
                if len(set(values)) == 1:
                    return 0

                sum_d2 = sum((pd["rank"] - pd[rank_key]) ** 2 for pd in data)
                rho = 1 - (6 * sum_d2) / (n * (n**2 - 1))
                return rho  # -1 ~ 1 범위

            visitor_corr = calc_spearman(place_data, "visitor_review_count", "visitor_review_count_rank")
            blog_corr = calc_spearman(place_data, "blog_review_count", "blog_review_count_rank")
            freshness_corr = calc_spearman(place_data, "freshness_count", "freshness_count_rank")
            save_corr = calc_spearman(place_data, "save_count", "save_count_rank") if is_food_cafe else 0

            # ========== Step 4: 상관계수 → 가중치 변환 ==========
            # 양의 상관관계만 가중치로 사용 (음수면 최소값)
            # 상관계수가 높을수록 해당 요소가 순위에 영향을 많이 줌
            MIN_WEIGHT = 0.05  # 최소 5%
            MIN_HIDDEN = 0.10  # 히든(유입수) 최소 10%

            # 최소값을 먼저 적용한 후 합계 계산
            visitor_raw = max(MIN_WEIGHT, max(0, visitor_corr))
            blog_raw = max(MIN_WEIGHT, max(0, blog_corr))
            freshness_raw = max(MIN_WEIGHT, max(0, freshness_corr))

            if is_food_cafe:
                # 맛집/카페: 저장수 포함 (측정 가능)
                save_raw = max(MIN_WEIGHT, max(0, save_corr))
                measurable_total = visitor_raw + blog_raw + freshness_raw + save_raw
            else:
                # 기타 업종: 저장수 제외
                save_raw = 0
                measurable_total = visitor_raw + blog_raw + freshness_raw

            # 히든(유입수) = 나머지 (최소 10%)
            hidden_raw = max(MIN_HIDDEN, 1 - measurable_total)

            # 합계가 1을 초과하면 측정 가능한 요소들을 비례 조정
            total = measurable_total + hidden_raw
            if total > 1:
                scale = (1 - hidden_raw) / measurable_total
                visitor_raw *= scale
                blog_raw *= scale
                freshness_raw *= scale
                if is_food_cafe:
                    save_raw *= scale

            # 가중치로 변환 (합계 = 100%)
            visitor_weight = visitor_raw * 100
            blog_weight = blog_raw * 100
            freshness_weight = freshness_raw * 100
            save_weight = save_raw * 100 if is_food_cafe else 0
            hidden_weight = hidden_raw * 100  # 유입수 (사용자 입력 필요)

            analysis["factor_weights"] = {
                "visitor_review": round(visitor_weight, 1),
                "blog_review": round(blog_weight, 1),
                "freshness": round(freshness_weight, 1),
                "save_count": round(save_weight, 1),  # 맛집/카페만 사용
                "hidden": round(hidden_weight, 1),  # 유입수
            }

            weights = analysis["factor_weights"]

            # ========== Step 5: 각 업체별 점수 계산 ==========
            # 각 항목별 최대값 기준 (순위 1위가 아닌, 해당 항목 최대값)
            max_visitor = max((pd["visitor_review_count"] for pd in place_data), default=1) or 1
            max_blog = max((pd["blog_review_count"] for pd in place_data), default=1) or 1
            max_freshness = max((pd["freshness_count"] for pd in place_data), default=1) or 1
            max_save = max((pd["save_count"] for pd in place_data), default=1) or 1 if is_food_cafe else 1

            for pd in place_data:
                # 각 요소별 비율 = 내 값 / 해당 항목 최대값
                visitor_ratio = pd["visitor_review_count"] / max_visitor
                blog_ratio = pd["blog_review_count"] / max_blog
                freshness_ratio = pd["freshness_count"] / max_freshness

                # 기여 점수 = 비율 × 가중치
                pd["visitor_contribution"] = round(visitor_ratio * weights["visitor_review"], 1)
                pd["blog_contribution"] = round(blog_ratio * weights["blog_review"], 1)
                pd["freshness_contribution"] = round(freshness_ratio * weights["freshness"], 1)

                # 저장수 기여 (맛집/카페만)
                if is_food_cafe:
                    save_ratio = pd["save_count"] / max_save if max_save > 0 else 0
                    pd["save_contribution"] = round(save_ratio * weights["save_count"], 1)
                    pd["save_score"] = round(save_ratio * 100, 1)
                else:
                    save_ratio = 0
                    pd["save_contribution"] = 0
                    pd["save_score"] = 0

                # 측정 가능한 기여 합계
                pd["visible_score"] = round(
                    pd["visitor_contribution"] +
                    pd["blog_contribution"] +
                    pd["freshness_contribution"] +
                    pd["save_contribution"],
                    1
                )

                # 히든 기여: 순위 기반 역산
                # 순위 1위 = 히든 만점, 순위에 따라 선형 감소
                hidden_ratio = 1 - (pd["rank"] - 1) / max(n - 1, 1)
                pd["hidden_contribution"] = round(hidden_ratio * weights["hidden"], 1)

                # 총점 = 측정 가능 점수 + 히든 점수
                pd["total_score"] = round(pd["visible_score"] + pd["hidden_contribution"], 1)

                # 요소별 100점 만점 기준 점수
                pd["visitor_score"] = round(visitor_ratio * 100, 1)
                pd["blog_score"] = round(blog_ratio * 100, 1)
                pd["freshness_score"] = round(freshness_ratio * 100, 1)
                pd["hidden_score"] = round(hidden_ratio * 100, 1)

            # place_data 저장
            analysis["place_data"] = place_data

            # ========== Step 6: 키워드 특성 설명 ==========
            factor_names = {
                "visitor_review": "방문자 리뷰",
                "blog_review": "블로그 리뷰",
                "freshness": "최신성(1주일 내 리뷰)",
                "hidden": "히든(저장수+유입수)",
            }

            sorted_weights = sorted(weights.items(), key=lambda x: x[1], reverse=True)
            top_factor = sorted_weights[0]

            if top_factor[1] >= 35:
                analysis["ranking_explanation"] = f"이 키워드는 '{factor_names[top_factor[0]]}'이 {top_factor[1]}%로 가장 중요합니다."
            else:
                top2 = sorted_weights[:2]
                analysis["ranking_explanation"] = f"여러 요소가 영향을 미칩니다: {factor_names[top2[0][0]]} {top2[0][1]}%, {factor_names[top2[1][0]]} {top2[1][1]}%"

            # 상관계수 정보 추가
            analysis["correlations"] = {
                "visitor_review": round(visitor_corr, 3),
                "blog_review": round(blog_corr, 3),
                "freshness": round(freshness_corr, 3),
                "save_count": round(save_corr, 3) if is_food_cafe else 0,
            }

            # ========== Step 7: 타겟 업체 분석 ==========
            target_idx = None
            for i, pd in enumerate(place_data):
                if str(pd["place_id"]) == str(target_place_id):
                    target_idx = i
                    break

            if target_idx is not None:
                target = place_data[target_idx]

                # 각 항목 최대값 대비 필요 개수 계산
                needed_for_max = {
                    "visitor_review": max(0, max_visitor - target["visitor_review_count"]),
                    "blog_review": max(0, max_blog - target["blog_review_count"]),
                    "freshness": max(0, max_freshness - target["freshness_count"]),
                }
                if is_food_cafe:
                    needed_for_max["save_count"] = max(0, max_save - target["save_count"])

                # 유입수 역산 (사용자가 유입수 입력한 경우)
                estimated_first_traffic = None
                traffic_gap = None
                if traffic_count and traffic_count > 0 and hidden_weight > 0:
                    # 순위 기반 추정: 순위가 낮을수록 1위보다 유입수가 적다고 가정
                    # 2위면 1위의 약 85%, 3위면 70% 등으로 추정
                    if target["rank"] == 1:
                        estimated_first_traffic = traffic_count
                        traffic_gap = 0
                    else:
                        # 순위 기반 비율 (1위=100%, 순위마다 약 15% 감소 가정)
                        rank_ratio = max(0.3, 1 - (target["rank"] - 1) * 0.15)
                        estimated_first_traffic = int(traffic_count / rank_ratio)
                        traffic_gap = estimated_first_traffic - traffic_count

                        # 히든 점수가 있으면 더 정확한 추정 가능
                        if target["hidden_score"] > 10:
                            # hidden_score 기반 추정
                            estimated_first_traffic_by_score = int(traffic_count * (100 / target["hidden_score"]))
                            # 두 추정의 평균 사용 (더 안정적)
                            estimated_first_traffic = int((estimated_first_traffic + estimated_first_traffic_by_score) / 2)
                            traffic_gap = estimated_first_traffic - traffic_count

                # ========== 최적의 방안 계산 ==========
                optimal_strategy = None
                if target["rank"] > 1:
                    # 각 요소별 효율성 계산 (1개당 얻는 점수)
                    efficiency_data = []

                    # 방문자 리뷰
                    if max_visitor > 0 and needed_for_max["visitor_review"] > 0:
                        points_per_unit = weights["visitor_review"] / max_visitor
                        potential_gain = needed_for_max["visitor_review"] * points_per_unit
                        efficiency_data.append({
                            "factor": "visitor_review",
                            "name": "방문자 리뷰",
                            "unit": "개",
                            "points_per_unit": points_per_unit,
                            "gap": needed_for_max["visitor_review"],
                            "potential_gain": potential_gain,
                            "action": "영수증 리뷰 요청 + 리뷰 이벤트"
                        })

                    # 블로그 리뷰
                    if max_blog > 0 and needed_for_max["blog_review"] > 0:
                        points_per_unit = weights["blog_review"] / max_blog
                        potential_gain = needed_for_max["blog_review"] * points_per_unit
                        efficiency_data.append({
                            "factor": "blog_review",
                            "name": "블로그 리뷰",
                            "unit": "개",
                            "points_per_unit": points_per_unit,
                            "gap": needed_for_max["blog_review"],
                            "potential_gain": potential_gain,
                            "action": "블로그 체험단 + 인플루언서 협업"
                        })

                    # 최신성
                    if max_freshness > 0 and needed_for_max["freshness"] > 0:
                        points_per_unit = weights["freshness"] / max_freshness
                        potential_gain = needed_for_max["freshness"] * points_per_unit
                        efficiency_data.append({
                            "factor": "freshness",
                            "name": "최신 리뷰(1주일 내)",
                            "unit": "개",
                            "points_per_unit": points_per_unit,
                            "gap": needed_for_max["freshness"],
                            "potential_gain": potential_gain,
                            "action": "최근 방문 고객에게 리뷰 요청"
                        })

                    # 유입수 (사용자가 입력한 경우)
                    if traffic_gap and traffic_gap > 0 and estimated_first_traffic:
                        points_per_unit = weights["hidden"] / estimated_first_traffic
                        potential_gain = traffic_gap * points_per_unit
                        efficiency_data.append({
                            "factor": "hidden",
                            "name": "유입수",
                            "unit": "회",
                            "points_per_unit": points_per_unit,
                            "gap": traffic_gap,
                            "potential_gain": potential_gain,
                            "action": "네이버 광고 + SNS 홍보 + 저장 이벤트"
                        })

                    # 실현 가능성 × 가중치 기준으로 정렬
                    # 1. 유입수(hidden): 광고/SNS로 컨트롤 가능 + 가중치 높음
                    # 2. 최신성: 최근 고객에게 요청하면 빠름
                    # 3. 블로그: 체험단으로 가능
                    # 4. 방문자 리뷰: 가장 어려움 (실제 고객 필요)
                    controllability_order = {
                        "hidden": 1,      # 가장 컨트롤 쉬움 (광고/SNS)
                        "freshness": 2,   # 빠른 효과
                        "blog_review": 3, # 체험단 가능
                        "visitor_review": 4  # 가장 어려움
                    }

                    if efficiency_data:
                        # 컨트롤 가능성 순으로 정렬 (같으면 가중치 높은 순)
                        efficiency_data.sort(key=lambda x: (
                            controllability_order.get(x["factor"], 5),
                            -x["potential_gain"]  # 같은 우선순위면 잠재 점수 높은 순
                        ))

                        # 1위 점수 가져오기
                        first_place_score = next((pd["total_score"] for pd in place_data if pd["rank"] == 1), 100)

                        # 1위까지 필요한 점수 (1위 점수 - 내 점수 + 약간의 마진)
                        gap_to_first = round(first_place_score - target["total_score"] + 0.1, 1)

                        # 효율 높은 순서대로 조합해서 1위 달성 방안 계산
                        import math
                        optimal_actions = []
                        remaining_gap = gap_to_first
                        total_gain = 0

                        for factor in efficiency_data:
                            if remaining_gap <= 0:
                                break

                            max_gain = factor["potential_gain"]  # 이 요소로 얻을 수 있는 최대 점수

                            if max_gain <= 0:
                                continue

                            if max_gain >= remaining_gap:
                                # 이 요소만으로 남은 점수 채울 수 있음
                                needed_units = math.ceil(remaining_gap / factor["points_per_unit"])
                                actual_gain = round(needed_units * factor["points_per_unit"], 1)
                                optimal_actions.append({
                                    "factor": factor["factor"],
                                    "name": factor["name"],
                                    "unit": factor["unit"],
                                    "needed": needed_units,
                                    "gain": actual_gain,
                                    "action": factor["action"]
                                })
                                total_gain += actual_gain
                                remaining_gap = 0
                            else:
                                # 이 요소 전부 사용해도 부족
                                optimal_actions.append({
                                    "factor": factor["factor"],
                                    "name": factor["name"],
                                    "unit": factor["unit"],
                                    "needed": factor["gap"],
                                    "gain": round(max_gain, 1),
                                    "action": factor["action"]
                                })
                                total_gain += max_gain
                                remaining_gap -= max_gain

                        # 메시지 생성
                        if optimal_actions:
                            action_texts = [f"{a['name']} {a['needed']:,}{a['unit']}" for a in optimal_actions]
                            if remaining_gap <= 0:
                                message = "1위가 되려면: " + " + ".join(action_texts)
                                achievable = True
                            else:
                                message = "측정 가능한 요소로 " + " + ".join(action_texts) + f" (추가로 히든 {remaining_gap:.1f}점 필요)"
                                achievable = False
                        else:
                            message = "이미 최고 수준입니다"
                            achievable = True

                        # 각 항목별로 "이 항목만으로 1등 이기려면 몇 개 필요한지" 계산
                        efficiency_with_first = []
                        for e in efficiency_data:
                            ppu = e["points_per_unit"]
                            potential_gain = e["potential_gain"]  # 이 항목 최대로 올리면 얻는 점수
                            max_available = e["gap"]  # 최대로 올릴 수 있는 개수

                            # 이 항목만으로 1등 이기려면 필요한 개수
                            needed_to_beat = math.ceil(gap_to_first / ppu) if ppu > 0 else None

                            # 이 항목으로 1등 달성 가능? (potential_gain >= gap_to_first)
                            can_beat_alone = potential_gain >= gap_to_first

                            # 실제 추천 개수: 1등 이기려면 필요한 개수 (단, 최대 개수를 넘지 않음)
                            if can_beat_alone and needed_to_beat:
                                recommended = min(needed_to_beat, max_available)
                                expected_gain = round(recommended * ppu, 1)
                            else:
                                recommended = max_available
                                expected_gain = round(potential_gain, 1)

                            efficiency_with_first.append({
                                "name": e["name"],
                                "factor": e["factor"],
                                "unit": e["unit"],
                                "points_per_unit": round(ppu, 4),
                                "gap_to_max": max_available,  # 최대로 올릴 수 있는 개수
                                "needed_to_beat_first": recommended,  # 추천 개수
                                "expected_gain": expected_gain,  # 추천 개수 달성 시 얻는 점수
                                "potential_gain": round(potential_gain, 1),  # 최대로 올리면 얻는 점수
                                "can_beat_alone": can_beat_alone,  # 이 항목만으로 1등 달성 가능?
                                "action": e["action"]
                            })

                        optimal_strategy = {
                            "current_score": target["total_score"],
                            "target_score": first_place_score,
                            "gap": gap_to_first,
                            "actions": optimal_actions,
                            "total_expected_gain": round(total_gain, 1),
                            "remaining_gap": round(max(0, remaining_gap), 1),
                            "achievable": achievable,
                            "message": message,
                            "efficiency_rank": efficiency_with_first
                        }

                target_analysis = {
                    "rank": target["rank"],
                    "total_places": n,
                    "total_score": target["total_score"],
                    # 요소별 점수 (100점 만점)
                    "scores": {
                        "visitor_review": target["visitor_score"],
                        "blog_review": target["blog_score"],
                        "freshness": target["freshness_score"],
                        "save_count": target.get("save_score", 0),
                        "hidden": target["hidden_score"],
                    },
                    # 요소별 기여도 (가중치 적용된 점수, 합=총점)
                    "contributions": {
                        "visitor_review": target["visitor_contribution"],
                        "blog_review": target["blog_contribution"],
                        "freshness": target["freshness_contribution"],
                        "save_count": target.get("save_contribution", 0),
                        "hidden": target["hidden_contribution"],
                    },
                    # 현재 개수
                    "counts": {
                        "visitor_review": target["visitor_review_count"],
                        "blog_review": target["blog_review_count"],
                        "freshness": target["freshness_count"],
                        "save_count": target.get("save_count", 0),
                    },
                    # 각 항목 최대값 (만점 기준)
                    "max_counts": {
                        "visitor_review": max_visitor,
                        "blog_review": max_blog,
                        "freshness": max_freshness,
                        "save_count": max_save if is_food_cafe else 0,
                    },
                    # 최대값까지 필요한 개수
                    "needed_for_max": needed_for_max,
                    # 유입수 관련 (사용자 입력 시)
                    "user_traffic_count": traffic_count,
                    "estimated_first_traffic": estimated_first_traffic,
                    "traffic_gap": traffic_gap,
                    "is_first": target["rank"] == 1,
                    "optimal_strategy": optimal_strategy,
                    "comparison_above": [],
                    "comparison_below": [],
                }

                # 상위 업체와 비교
                if target["rank"] > 1:
                    for i in range(target_idx - 1, max(-1, target_idx - 3), -1):
                        above = place_data[i]
                        target_analysis["comparison_above"].append({
                            "rank": above["rank"],
                            "name": above["name"],
                            "place_id": above["place_id"],
                            "scores": {
                                "visitor_review": above["visitor_score"],
                                "blog_review": above["blog_score"],
                                "freshness": above["freshness_score"],
                                "hidden": above["hidden_score"],
                            },
                            "counts": {
                                "visitor_review": above["visitor_review_count"],
                                "blog_review": above["blog_review_count"],
                                "freshness": above["freshness_count"],
                            },
                            "diff": {
                                "visitor_review": above["visitor_review_count"] - target["visitor_review_count"],
                                "blog_review": above["blog_review_count"] - target["blog_review_count"],
                                "freshness": above["freshness_count"] - target["freshness_count"],
                                "visitor_score": round(above["visitor_score"] - target["visitor_score"], 1),
                                "blog_score": round(above["blog_score"] - target["blog_score"], 1),
                                "freshness_score": round(above["freshness_score"] - target["freshness_score"], 1),
                                "hidden_score": round(above["hidden_score"] - target["hidden_score"], 1),
                            }
                        })

                # 하위 업체와 비교
                for i in range(target_idx + 1, min(target_idx + 3, len(place_data))):
                    below = place_data[i]
                    target_analysis["comparison_below"].append({
                        "rank": below["rank"],
                        "name": below["name"],
                        "place_id": below["place_id"],
                        "scores": {
                            "visitor_review": below["visitor_score"],
                            "blog_review": below["blog_score"],
                            "freshness": below["freshness_score"],
                            "hidden": below["hidden_score"],
                        },
                        "counts": {
                            "visitor_review": below["visitor_review_count"],
                            "blog_review": below["blog_review_count"],
                            "freshness": below["freshness_count"],
                        },
                        "diff": {
                            "visitor_review": target["visitor_review_count"] - below["visitor_review_count"],
                            "blog_review": target["blog_review_count"] - below["blog_review_count"],
                            "freshness": target["freshness_count"] - below["freshness_count"],
                        }
                    })

                analysis["target_analysis"] = target_analysis

                # ========== Step 8: 액션 플랜 생성 ==========
                recs = []

                if target["rank"] > 1 and target_analysis["comparison_above"]:
                    above = target_analysis["comparison_above"][0]
                    diff = above["diff"]

                    # 각 요소별 차이 분석
                    gaps = []
                    if diff["visitor_score"] > 5:
                        gaps.append(("visitor_review", diff["visitor_score"], diff["visitor_review"]))
                    if diff["blog_score"] > 5:
                        gaps.append(("blog_review", diff["blog_score"], diff["blog_review"]))
                    if diff["freshness_score"] > 5:
                        gaps.append(("freshness", diff["freshness_score"], diff["freshness"]))
                    if diff["hidden_score"] > 5:
                        gaps.append(("hidden", diff["hidden_score"], None))

                    # 가중치 높은 순으로 정렬
                    gaps.sort(key=lambda x: weights.get(x[0], 0) * x[1], reverse=True)

                    # 가장 높은 가중치 요소 찾기
                    max_weight_factor = max(weights.items(), key=lambda x: x[1])
                    max_factor_name = factor_names[max_weight_factor[0]]
                    max_factor_weight = max_weight_factor[1]

                    # 히든이 가장 중요한 경우 (가중치 40% 이상)
                    if max_weight_factor[0] == "hidden" and max_factor_weight >= 40:
                        recs.append({
                            "type": "hidden",
                            "priority": "critical",
                            "title": f"히든(저장수/유입수)이 가장 중요!",
                            "message": f"이 키워드는 히든 가중치가 {max_factor_weight}%로 가장 높습니다. 저장수와 유입수를 늘리는 게 순위 상승의 핵심입니다.",
                            "action": "저장 이벤트 + 네이버 광고 + SNS/블로그 홍보로 유입 증가"
                        })
                        # 측정 가능한 요소 중 gap이 있으면 추가 추천
                        if len(gaps) > 0:
                            top_gap = gaps[0]
                            if top_gap[0] != "hidden":
                                factor_name = factor_names[top_gap[0]]
                                recs.append({
                                    "type": "summary",
                                    "priority": "high",
                                    "title": f"추가로 '{factor_name}'도 개선",
                                    "message": f"1위와 {factor_name}에서 {top_gap[1]:.0f}점 차이. 가중치: {weights[top_gap[0]]}%",
                                    "action": self._get_action_plan(top_gap[0])
                                })
                    else:
                        # 측정 가능한 요소가 가장 중요한 경우
                        if len(gaps) > 0:
                            top_gap = gaps[0]
                            factor_name = factor_names[top_gap[0]]
                            recs.append({
                                "type": "summary",
                                "priority": "critical",
                                "title": f"'{factor_name}' 개선 필요",
                                "message": f"{above['rank']}위와 {factor_name}에서 {top_gap[1]:.0f}점 차이. 이 키워드에서 {factor_name} 가중치: {weights[top_gap[0]]}%",
                                "action": self._get_action_plan(top_gap[0])
                            })
                        else:
                            recs.append({
                                "type": "summary",
                                "priority": "info",
                                "title": "1위와 거의 동등한 수준",
                                "message": f"측정 가능한 지표에서 {above['rank']}위와 큰 차이가 없습니다.",
                                "action": "현재 상태 유지, 리뷰 관리 지속"
                            })

                    # 세부 액션 플랜
                    for gap in gaps[:3]:
                        factor_key = gap[0]
                        score_gap = gap[1]
                        count_gap = gap[2]

                        action_detail = {
                            "type": factor_key,
                            "priority": "high" if score_gap > 15 else "medium",
                            "title": f"{factor_names[factor_key]} 개선",
                            "score_gap": score_gap,
                            "weight": weights[factor_key],
                        }

                        if factor_key == "visitor_review":
                            action_detail["message"] = f"방문자 리뷰 {count_gap:,}개 부족"
                            action_detail["action"] = "영수증 리뷰 요청 + 리뷰 이벤트"
                        elif factor_key == "blog_review":
                            action_detail["message"] = f"블로그 리뷰 {count_gap:,}개 부족"
                            action_detail["action"] = "블로그 체험단 + 인플루언서 협업"
                        elif factor_key == "freshness":
                            action_detail["message"] = f"최근 1주일 리뷰 {count_gap:,}개 부족"
                            action_detail["action"] = "최근 방문 고객 리뷰 요청 + 이벤트"
                        elif factor_key == "hidden":
                            action_detail["message"] = f"히든 점수(저장수/유입수) 부족"
                            action_detail["action"] = "저장 이벤트 + 네이버 광고 + SNS 홍보"

                        recs.append(action_detail)

                analysis["recommendations"] = recs

        except Exception as e:
            logger.error(f"Analysis error: {e}")
            import traceback
            logger.error(traceback.format_exc())

        return analysis

    def _get_action_plan(self, factor: str) -> str:
        """요소별 기본 액션 플랜"""
        plans = {
            "visitor_review": "영수증 리뷰 요청 + 리뷰 이벤트",
            "blog_review": "블로그 체험단 + 인플루언서 협업",
            "freshness": "최근 방문 고객 리뷰 요청 + 정기 이벤트",
            "hidden": "저장 이벤트 + 네이버 광고 + SNS 홍보",
        }
        return plans.get(factor, "")

    async def get_visitor_reviews(
        self,
        place_id: str,
        limit: int = 20
    ) -> List[Dict[str, Any]]:
        """
        방문자 리뷰 목록 조회 (requests 사용)

        날짜, 예약/일반 구분, 리뷰 내용을 가져옵니다.
        """
        reviews = []

        try:
            headers = {
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
                "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            }

            url = f"https://m.place.naver.com/restaurant/{place_id}/review/visitor"

            # 프록시 URL (있으면)
            proxy_url = self._proxy_config["url"] if self._proxy_config else None

            async with aiohttp.ClientSession() as session:
                async with session.get(
                    url,
                    headers=headers,
                    proxy=proxy_url,
                    timeout=aiohttp.ClientTimeout(total=15)
                ) as response:
                    if response.status != 200:
                        logger.warning(f"Failed to fetch reviews: status {response.status}")
                        return []

                    html = await response.text()

            if len(html) < 50000:
                logger.warning(f"Review page HTML too small: {len(html)} chars")
                return []

            # VisitorReview 객체에서 추출
            # 패턴: "VisitorReview:xxx:true":{ ... "reviewId":"...", "body":"...", ... }
            vr_pattern = r'"VisitorReview:([^"]+)":\s*\{'

            for match in re.finditer(vr_pattern, html):
                if len(reviews) >= limit:
                    break

                vr_id = match.group(1)
                start = match.end() - 1  # { 위치

                # 중괄호 균형으로 객체 끝 찾기
                brace_count = 0
                end = start
                for i in range(start, min(start + 5000, len(html))):
                    if html[i] == '{':
                        brace_count += 1
                    elif html[i] == '}':
                        brace_count -= 1
                        if brace_count == 0:
                            end = i + 1
                            break

                obj_str = html[start:end]

                # 필드 추출
                body_match = re.search(r'"body":"([^"]+)"', obj_str)
                review_id_match = re.search(r'"reviewId":"([^"]+)"', obj_str)

                if body_match:
                    body = body_match.group(1)
                    # JSON 유니코드 이스케이프 디코딩
                    try:
                        body = json.loads(f'"{body}"')
                    except:
                        pass

                    # 리뷰 내용이 너무 짧으면 제외
                    if len(body) < 10:
                        continue

                    review_data = {
                        "review_id": review_id_match.group(1) if review_id_match else vr_id,
                        "content": body[:300],  # 300자로 제한
                        "type": "방문자",
                    }

                    reviews.append(review_data)

            # 날짜 정보 추출 (createdString 형태: "10.24.금")
            created_strings = re.findall(r'"createdString":"([^"]+)"', html)
            for i, review in enumerate(reviews):
                if i < len(created_strings):
                    try:
                        date_str = json.loads(f'"{created_strings[i]}"')
                        review["date"] = date_str
                    except:
                        review["date"] = created_strings[i]
                else:
                    review["date"] = ""

            logger.info(f"Found {len(reviews)} visitor reviews for {place_id}")

        except Exception as e:
            logger.error(f"Error getting visitor reviews: {e}")

        return reviews

    async def get_blog_reviews(
        self,
        place_id: str,
        limit: int = 20
    ) -> List[Dict[str, Any]]:
        """
        블로그 리뷰 목록 조회 (requests 사용)

        블로거명, 날짜, 제목, 링크를 가져옵니다.
        방문자 리뷰 페이지에서 블로그 리뷰 정보도 함께 가져옵니다.
        """
        reviews = []

        try:
            headers = {
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
                "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            }

            # 방문자 리뷰 페이지에서 블로그 리뷰 정보도 포함됨
            url = f"https://m.place.naver.com/restaurant/{place_id}/review/visitor"

            # 프록시 URL (있으면)
            proxy_url = self._proxy_config["url"] if self._proxy_config else None

            async with aiohttp.ClientSession() as session:
                async with session.get(
                    url,
                    headers=headers,
                    proxy=proxy_url,
                    timeout=aiohttp.ClientTimeout(total=15)
                ) as response:
                    if response.status != 200:
                        logger.warning(f"Failed to fetch blog reviews: status {response.status}")
                        return []

                    html = await response.text()

            if len(html) < 50000:
                logger.warning(f"Review page HTML too small for blog: {len(html)} chars")
                return []

            # FsasReview:blog 패턴으로 블로그 리뷰 추출
            # 형태: "FsasReview:blog_블로거명_포스트ID_제목":{ ... }
            blog_pattern = r'"FsasReview:blog_([^"]+)":\s*\{'

            for match in re.finditer(blog_pattern, html):
                if len(reviews) >= limit:
                    break

                blog_id = match.group(1)
                start = match.end() - 1  # { 위치

                # 객체 시작 주변에서 필드 추출 (중괄호 균형 대신 직접 패턴 매칭)
                # 시작 위치에서 1000자 범위 내에서 필드 찾기
                context = html[start:start + 1500]

                # 필드 추출
                name_match = re.search(r'"name":"([^"]+)"', context)
                url_match = re.search(r'"url":"([^"]+)"', context)
                type_match = re.search(r'"typeName":"([^"]+)"', context)

                # blog_id에서 정보 추출 (블로거명_포스트ID_제목)
                parts = blog_id.split("_", 2)
                author = parts[0] if len(parts) > 0 else ""
                post_id = parts[1] if len(parts) > 1 else ""
                title = parts[2] if len(parts) > 2 else ""

                # JSON 디코딩
                try:
                    author = json.loads(f'"{author}"')
                    title = json.loads(f'"{title}"')
                except:
                    pass

                # URL 디코딩 - \u002F는 / 로 인코딩됨
                blog_url = ""
                if url_match:
                    url_str = url_match.group(1)
                    # JSON 유니코드 디코딩
                    try:
                        blog_url = json.loads(f'"{url_str}"')
                    except:
                        blog_url = url_str.replace("\\u002F", "/").replace("\\", "")

                review_type = "블로그"
                if type_match:
                    type_name = type_match.group(1)
                    if "체험" in type_name:
                        review_type = "블로그체험단"

                reviews.append({
                    "title": title[:100] if title else "",
                    "author": author,
                    "post_id": post_id,
                    "url": blog_url,
                    "type": review_type,
                })

            logger.info(f"Found {len(reviews)} blog reviews for {place_id}")

        except Exception as e:
            logger.error(f"Error getting blog reviews: {e}")

        return reviews

    async def close(self):
        """브라우저 종료"""
        if self._browser:
            try:
                await self._browser.close()
            except:
                pass
        if self._playwright:
            try:
                await self._playwright.stop()
            except:
                pass
