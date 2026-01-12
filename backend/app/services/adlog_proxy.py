"""
ADLOG API Proxy Service
ADLOG API를 숨기고 우리 서비스로 변환하는 프록시
캐싱 및 Rate Limiting 적용
프록시 로테이션 지원
"""
import httpx
import os
import re
import json
import asyncio
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from app.core.config import settings
from app.core.cache import adlog_cache, adlog_rate_limiter, adlog_hourly_limiter
from app.core.database import AsyncSessionLocal
from app.models.place import AdlogTrainingData
import logging

logger = logging.getLogger(__name__)


def parse_int_safe(value: Any) -> Optional[int]:
    """
    문자열에서 숫자가 아닌 문자를 제거하고 int로 변환
    "2,000+" -> 2000, "14▲" -> 14, "-5▼" -> -5
    변환 실패 시 None 반환
    """
    if value is None:
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)

    try:
        # 문자열로 변환
        str_value = str(value).strip()
        if not str_value:
            return None

        # 부호 처리
        is_negative = str_value.startswith('-') or '▼' in str_value

        # 숫자와 소수점만 남기기 (콤마, +, ▲, ▼ 등 제거)
        cleaned = re.sub(r'[^\d.]', '', str_value)

        if not cleaned:
            return None

        # float로 변환 후 int로
        result = int(float(cleaned))
        return -result if is_negative else result
    except (ValueError, TypeError):
        return None


def parse_float_safe(value: Any) -> float:
    """
    문자열에서 숫자가 아닌 문자를 제거하고 float로 변환
    변환 실패 시 0.0 반환
    """
    if value is None:
        return 0.0
    if isinstance(value, (int, float)):
        return float(value)

    try:
        str_value = str(value).strip()
        if not str_value:
            return 0.0

        # 부호 처리
        is_negative = str_value.startswith('-') or '▼' in str_value

        # 숫자와 소수점만 남기기
        cleaned = re.sub(r'[^\d.]', '', str_value)

        if not cleaned:
            return 0.0

        result = float(cleaned)
        return -result if is_negative else result
    except (ValueError, TypeError):
        return 0.0


def get_adlog_proxy_list() -> List[Dict[str, Any]]:
    """
    ADLOG API용 프록시 목록 가져오기

    환경변수:
    - ADLOG_PROXY_LIST: JSON 형식의 프록시 목록
      예: '[{"url": "http://1.2.3.4:8080", "name": "US"}, {"url": "http://5.6.7.8:3128", "name": "SG"}]'
    - ADLOG_PROXY_URL: 단일 프록시 (하위 호환성)
    - PROXY_URL: 공용 프록시 (하위 호환성)

    Returns:
        프록시 정보 리스트 [{"url": str, "name": str}, ...]
    """
    proxies = []

    # 방법 1: JSON 프록시 목록 (권장)
    proxy_list_json = os.getenv("ADLOG_PROXY_LIST")
    if proxy_list_json:
        try:
            parsed = json.loads(proxy_list_json)
            if isinstance(parsed, list):
                for p in parsed:
                    if isinstance(p, dict) and "url" in p:
                        proxies.append({
                            "url": p["url"],
                            "name": p.get("name", p["url"].split("//")[-1].split(":")[0])
                        })
                    elif isinstance(p, str):
                        proxies.append({
                            "url": p,
                            "name": p.split("//")[-1].split(":")[0]
                        })
                if proxies:
                    return proxies
        except json.JSONDecodeError:
            logger.warning("ADLOG_PROXY_LIST is not valid JSON, falling back to single proxy")

    # 방법 2: ADLOG 전용 프록시 URL (하위 호환)
    adlog_proxy_url = os.getenv("ADLOG_PROXY_URL")
    if adlog_proxy_url:
        proxies.append({
            "url": adlog_proxy_url,
            "name": adlog_proxy_url.split("//")[-1].split(":")[0]
        })

    # 방법 3: 공용 프록시 URL (하위 호환)
    proxy_url = os.getenv("PROXY_URL")
    if proxy_url and proxy_url not in [p["url"] for p in proxies]:
        proxies.append({
            "url": proxy_url,
            "name": proxy_url.split("//")[-1].split(":")[0]
        })

    # 방법 4: 개별 설정으로 URL 조합
    host = os.getenv("PROXY_HOST")
    port = os.getenv("PROXY_PORT")
    user = os.getenv("PROXY_USER")
    password = os.getenv("PROXY_PASS")

    if host and port:
        if user and password:
            url = f"http://{user}:{password}@{host}:{port}"
        else:
            url = f"http://{host}:{port}"
        if url not in [p["url"] for p in proxies]:
            proxies.append({"url": url, "name": host})

    return proxies


class ProxyRotator:
    """
    프록시 로테이션 관리자
    - 여러 프록시를 순환하며 사용
    - 실패한 프록시 자동 제외 (일정 시간 후 복구)
    - Rate limit 걸린 프록시 자동 전환
    """

    def __init__(self, proxies: List[Dict[str, Any]], cooldown_minutes: int = 30):
        """
        Args:
            proxies: 프록시 정보 리스트 [{"url": str, "name": str}, ...]
            cooldown_minutes: 실패한 프록시 재시도까지 대기 시간 (분)
        """
        self._proxies = proxies
        self._cooldown_minutes = cooldown_minutes
        self._current_index = 0
        self._failed_proxies: Dict[str, datetime] = {}  # url -> 실패 시간
        self._rate_limited_proxies: Dict[str, datetime] = {}  # url -> rate limit 시간
        self._lock = asyncio.Lock()

        if proxies:
            safe_list = [self._safe_proxy_name(p["url"]) for p in proxies]
            logger.info(f"ProxyRotator initialized with {len(proxies)} proxies: {safe_list}")
        else:
            logger.warning("ProxyRotator initialized with NO proxies - direct connection will be used")

    def _safe_proxy_name(self, url: str) -> str:
        """로그에 안전한 프록시 이름 (비밀번호 제거)"""
        if "@" in url:
            return url.split("@")[-1]
        return url.split("//")[-1] if "//" in url else url

    def _is_proxy_available(self, proxy_url: str) -> bool:
        """프록시가 사용 가능한지 확인"""
        now = datetime.now()

        # 실패 쿨다운 확인
        if proxy_url in self._failed_proxies:
            failed_time = self._failed_proxies[proxy_url]
            if now < failed_time + timedelta(minutes=self._cooldown_minutes):
                return False
            else:
                # 쿨다운 완료 - 복구
                del self._failed_proxies[proxy_url]
                logger.info(f"Proxy recovered from failure cooldown: {self._safe_proxy_name(proxy_url)}")

        # Rate limit 쿨다운 확인 (더 긴 대기 시간)
        if proxy_url in self._rate_limited_proxies:
            rate_limit_time = self._rate_limited_proxies[proxy_url]
            # Rate limit은 다음 날까지 대기
            next_day = (rate_limit_time + timedelta(days=1)).replace(
                hour=0, minute=0, second=0, microsecond=0
            )
            if now < next_day:
                return False
            else:
                # 다음 날이 됨 - 복구
                del self._rate_limited_proxies[proxy_url]
                logger.info(f"Proxy recovered from rate limit: {self._safe_proxy_name(proxy_url)}")

        return True

    def get_available_proxies(self) -> List[Dict[str, Any]]:
        """사용 가능한 프록시 목록"""
        return [p for p in self._proxies if self._is_proxy_available(p["url"])]

    async def get_next_proxy(self) -> Optional[Dict[str, Any]]:
        """
        다음 사용 가능한 프록시 반환

        Returns:
            프록시 정보 {"url": str, "name": str} 또는 None (모든 프록시 사용 불가)
        """
        async with self._lock:
            available = self.get_available_proxies()

            if not available:
                logger.warning("No available proxies - all are in cooldown or rate limited")
                return None

            # 라운드 로빈
            self._current_index = self._current_index % len(available)
            proxy = available[self._current_index]
            self._current_index = (self._current_index + 1) % len(available)

            return proxy

    async def mark_failed(self, proxy_url: str, reason: str = "unknown") -> None:
        """프록시를 실패로 표시 (쿨다운 적용)"""
        async with self._lock:
            self._failed_proxies[proxy_url] = datetime.now()
            logger.warning(
                f"Proxy marked as failed: {self._safe_proxy_name(proxy_url)} "
                f"(reason: {reason}, cooldown: {self._cooldown_minutes}min)"
            )

    async def mark_rate_limited(self, proxy_url: str) -> None:
        """프록시를 rate limit으로 표시 (다음 날까지 대기)"""
        async with self._lock:
            self._rate_limited_proxies[proxy_url] = datetime.now()
            logger.warning(
                f"Proxy marked as rate limited: {self._safe_proxy_name(proxy_url)} "
                f"(will retry after midnight)"
            )

    async def reset_proxy(self, proxy_url: str) -> None:
        """프록시 상태 초기화 (수동 복구용)"""
        async with self._lock:
            if proxy_url in self._failed_proxies:
                del self._failed_proxies[proxy_url]
            if proxy_url in self._rate_limited_proxies:
                del self._rate_limited_proxies[proxy_url]
            logger.info(f"Proxy manually reset: {self._safe_proxy_name(proxy_url)}")

    async def reset_all(self) -> None:
        """모든 프록시 상태 초기화"""
        async with self._lock:
            self._failed_proxies.clear()
            self._rate_limited_proxies.clear()
            self._current_index = 0
            logger.info("All proxies reset")

    def get_status(self) -> Dict[str, Any]:
        """프록시 상태 정보"""
        now = datetime.now()

        status = {
            "total_proxies": len(self._proxies),
            "available_count": len(self.get_available_proxies()),
            "proxies": []
        }

        for proxy in self._proxies:
            url = proxy["url"]
            proxy_status = {
                "name": proxy["name"],
                "url_masked": self._safe_proxy_name(url),
                "status": "available"
            }

            if url in self._rate_limited_proxies:
                rate_limit_time = self._rate_limited_proxies[url]
                next_day = (rate_limit_time + timedelta(days=1)).replace(
                    hour=0, minute=0, second=0, microsecond=0
                )
                proxy_status["status"] = "rate_limited"
                proxy_status["available_at"] = next_day.isoformat()
            elif url in self._failed_proxies:
                failed_time = self._failed_proxies[url]
                available_at = failed_time + timedelta(minutes=self._cooldown_minutes)
                proxy_status["status"] = "failed"
                proxy_status["available_at"] = available_at.isoformat()

            status["proxies"].append(proxy_status)

        return status

# 학습 데이터 보관 기간 (일)
TRAINING_DATA_RETENTION_DAYS = 30


class AdlogApiError(Exception):
    """ADLOG API 관련 에러"""
    pass


class AdlogRateLimitError(AdlogApiError):
    """ADLOG API 일일 제한 초과 에러"""
    pass


class AdlogProxyService:
    """
    ADLOG API를 완전히 숨기는 프록시 서비스
    - 캐싱 + Rate Limiting 적용
    - 프록시 로테이션 지원
    """

    def __init__(self):
        self._base_url = settings.ADLOG_API_URL
        self._timeout = 15.0  # 프록시 사용 시 타임아웃 증가
        self._cache = adlog_cache
        self._rate_limiter = adlog_rate_limiter
        self._hourly_limiter = adlog_hourly_limiter
        # API 제한 상태 추적 (전역 - 모든 프록시가 실패한 경우)
        self._all_proxies_rate_limited = False
        self._all_proxies_rate_limit_reset_time: Optional[datetime] = None
        # 프록시 로테이션 설정
        proxy_list = get_adlog_proxy_list()
        self._proxy_rotator = ProxyRotator(proxy_list, cooldown_minutes=30)
        # 최대 재시도 횟수 (프록시 개수 또는 3 중 큰 값)
        self._max_retries = max(len(proxy_list), 3) if proxy_list else 1

    def _sanitize_keyword(self, keyword: str) -> str:
        """키워드 입력 검증 및 정제"""
        keyword = keyword.strip()
        # XSS, Injection 방지
        keyword = re.sub(r'[<>"\';]', '', keyword)
        if len(keyword) > 50:
            keyword = keyword[:50]
        return keyword

    def _get_cache_key(self, keyword: str) -> str:
        """캐시 키 생성"""
        return self._cache._make_key("adlog_keyword", keyword.lower())

    def _check_all_proxies_rate_limit_reset(self) -> None:
        """모든 프록시 rate limit 상태 리셋 확인"""
        if self._all_proxies_rate_limited and self._all_proxies_rate_limit_reset_time:
            if datetime.now() > self._all_proxies_rate_limit_reset_time:
                logger.info("All proxies rate limit reset - resetting rotator")
                self._all_proxies_rate_limited = False
                self._all_proxies_rate_limit_reset_time = None

    async def fetch_keyword_analysis(self, keyword: str, force_refresh: bool = False) -> Dict[str, Any]:
        """
        키워드 분석 데이터 조회 (캐싱 + 프록시 로테이션 적용)

        Args:
            keyword: 검색 키워드 (예: "홍대맛집")
            force_refresh: True면 캐시 무시하고 새로 조회

        Returns:
            변환된 분석 데이터
        """
        keyword = self._sanitize_keyword(keyword)
        cache_key = self._get_cache_key(keyword)

        # 1. 캐시 확인 (force_refresh가 아닌 경우)
        if not force_refresh:
            cached_result = await self._cache.get(cache_key)
            if cached_result is not None:
                logger.info(f"Cache HIT for keyword: {keyword}")
                return cached_result

        # 2. 모든 프록시 rate limit 상태 확인
        self._check_all_proxies_rate_limit_reset()
        if self._all_proxies_rate_limited:
            remaining_time = ""
            if self._all_proxies_rate_limit_reset_time:
                remaining = (self._all_proxies_rate_limit_reset_time - datetime.now()).total_seconds()
                remaining_hours = int(remaining // 3600)
                remaining_mins = int((remaining % 3600) // 60)
                remaining_time = f" (약 {remaining_hours}시간 {remaining_mins}분 후 리셋 예정)"
            logger.warning(f"All proxies rate limited{remaining_time}")
            raise AdlogRateLimitError(
                f"모든 프록시가 일일 제한에 도달했습니다.{remaining_time} 잠시 후 다시 시도해주세요."
            )

        # 3. Rate Limiting 확인
        if not await self._rate_limiter.acquire():
            logger.warning("Rate limit exceeded (per minute)")
            raise AdlogApiError("요청이 너무 많습니다. 잠시 후 다시 시도해주세요.")

        if not await self._hourly_limiter.acquire():
            logger.warning("Rate limit exceeded (per hour)")
            raise AdlogApiError("시간당 요청 제한에 도달했습니다. 잠시 후 다시 시도해주세요.")

        # 4. 프록시 로테이션으로 API 호출 (재시도 포함)
        last_error = None
        tried_proxies = set()

        for attempt in range(self._max_retries):
            # 다음 프록시 가져오기
            proxy_info = await self._proxy_rotator.get_next_proxy()

            if proxy_info is None:
                # 사용 가능한 프록시 없음
                if not tried_proxies:
                    # 프록시 없이 직접 연결 시도
                    logger.warning("No proxies available, trying direct connection")
                    proxy_url = None
                    proxy_name = "direct"
                else:
                    # 모든 프록시 시도 완료
                    break
            else:
                proxy_url = proxy_info["url"]
                proxy_name = proxy_info["name"]

                # 이미 시도한 프록시는 건너뛰기
                if proxy_url in tried_proxies:
                    continue

            tried_proxies.add(proxy_url or "direct")

            try:
                result = await self._call_api_with_proxy(keyword, proxy_url, proxy_name)

                # 성공 - 캐싱
                await self._cache.set(cache_key, result, ttl=86400)
                logger.info(f"Cached result for keyword: {keyword} (TTL: 86400s)")

                return result

            except AdlogRateLimitError as e:
                # Rate limit - 해당 프록시 표시하고 다음으로
                if proxy_url:
                    await self._proxy_rotator.mark_rate_limited(proxy_url)
                last_error = e
                logger.warning(f"Proxy {proxy_name} hit rate limit, trying next...")
                continue

            except (httpx.TimeoutException, httpx.ConnectError, httpx.ProxyError) as e:
                # 연결 실패 - 해당 프록시 표시하고 다음으로
                if proxy_url:
                    await self._proxy_rotator.mark_failed(proxy_url, str(type(e).__name__))
                last_error = e
                logger.warning(f"Proxy {proxy_name} failed ({type(e).__name__}), trying next...")
                continue

            except httpx.HTTPStatusError as e:
                # HTTP 에러
                if proxy_url:
                    await self._proxy_rotator.mark_failed(proxy_url, f"HTTP {e.response.status_code}")
                last_error = e
                logger.warning(f"Proxy {proxy_name} HTTP error ({e.response.status_code}), trying next...")
                continue

            except Exception as e:
                last_error = e
                logger.error(f"Unexpected error with proxy {proxy_name}: {str(e)}")
                if proxy_url:
                    await self._proxy_rotator.mark_failed(proxy_url, "unknown")
                continue

        # 모든 프록시 실패
        available_proxies = self._proxy_rotator.get_available_proxies()
        if not available_proxies:
            # 모든 프록시가 rate limited
            self._all_proxies_rate_limited = True
            now = datetime.now()
            self._all_proxies_rate_limit_reset_time = (now + timedelta(days=1)).replace(
                hour=0, minute=0, second=0, microsecond=0
            )
            logger.error("All proxies exhausted - rate limited until midnight")
            raise AdlogRateLimitError(
                "모든 프록시가 일일 제한에 도달했습니다. 내일 다시 시도해주세요."
            )

        # 일시적 실패
        logger.error(f"All proxy attempts failed for keyword: {keyword}")
        if isinstance(last_error, AdlogRateLimitError):
            raise last_error
        raise AdlogApiError("분석 서비스 연결에 실패했습니다. 잠시 후 다시 시도해주세요.")

    async def _call_api_with_proxy(
        self,
        keyword: str,
        proxy_url: Optional[str],
        proxy_name: str
    ) -> Dict[str, Any]:
        """
        특정 프록시로 ADLOG API 호출

        Args:
            keyword: 검색 키워드
            proxy_url: 프록시 URL (None이면 직접 연결)
            proxy_name: 프록시 이름 (로깅용)

        Returns:
            변환된 분석 데이터

        Raises:
            AdlogRateLimitError: API rate limit 도달
            httpx 예외들: 연결 실패
        """
        logger.info(f"Calling ADLOG API for keyword: {keyword} (proxy: {proxy_name})")

        client_kwargs = {
            "timeout": self._timeout,
        }
        if proxy_url:
            client_kwargs["proxy"] = proxy_url

        async with httpx.AsyncClient(**client_kwargs) as client:
            response = await client.post(
                self._base_url,
                json={"query": keyword},
                headers={"Content-Type": "application/json"},
            )
            response.raise_for_status()
            raw_data = response.json()

            # Rate limit 응답 확인
            if raw_data.get("code") == "2000":
                logger.warning(f"ADLOG rate limit response via proxy {proxy_name}")
                raise AdlogRateLimitError(
                    f"프록시 {proxy_name}의 일일 제한에 도달했습니다."
                )

            # 응답 변환
            result = self._transform_response(raw_data, keyword)

            # 딥러닝 학습용 DB 저장 (백그라운드, 에러 무시)
            try:
                await self._save_training_data(keyword, raw_data)
            except Exception as e:
                logger.debug(f"Training data save failed: {e}")

            logger.info(f"Successfully fetched data via proxy {proxy_name}")
            return result

    async def _save_training_data(self, keyword: str, raw_data: Dict) -> None:
        """
        딥러닝 학습용 데이터 DB 저장
        - 30일간 보관 후 자동 삭제 예정 (별도 스케줄러 필요)
        - 에러가 발생해도 API 응답에 영향 없음 (로깅만 함)
        """
        try:
            items = raw_data.get("items", [])
            if not items:
                items = raw_data.get("data", [])

            if not items:
                logger.debug(f"No items to save for keyword: {keyword}")
                return

            now = datetime.now()
            expires_at = now + timedelta(days=TRAINING_DATA_RETENTION_DAYS)

            async with AsyncSessionLocal() as session:
                for item in items:
                    training_record = AdlogTrainingData(
                        keyword=keyword,
                        place_id=str(item.get("place_id", "")),
                        place_name=item.get("place_name", ""),
                        rank=parse_int_safe(item.get("place_rank")),
                        rank_change=parse_int_safe(item.get("place_rank_compare")),
                        index_n1=parse_float_safe(item.get("place_index1")),
                        index_n2=parse_float_safe(item.get("place_index2")),
                        index_n3=parse_float_safe(item.get("place_index3")),
                        index_n2_change=parse_float_safe(item.get("place_index2_compare")),
                        visitor_review_count=parse_int_safe(item.get("place_visit_cnt")) or 0,
                        blog_review_count=parse_int_safe(item.get("place_blog_cnt")) or 0,
                        save_count=parse_int_safe(item.get("place_save_cnt")) or 0,
                        collected_at=now,
                        expires_at=expires_at
                    )
                    session.add(training_record)

                await session.commit()
                logger.info(f"Saved {len(items)} training records for keyword: {keyword}")

        except Exception as e:
            # DB 저장 실패해도 API 응답에는 영향 없음
            logger.error(f"Failed to save training data for keyword '{keyword}': {str(e)}")

    def _transform_response(self, raw: Dict, keyword: str) -> Dict[str, Any]:
        """응답에서 ADLOG 관련 정보 제거 및 변환"""

        items = raw.get("items", [])
        if not items:
            items = raw.get("data", [])

        places = []
        for item in items:
            place = {
                "place_id": item.get("place_id", ""),
                "name": item.get("place_name", ""),
                "rank": parse_int_safe(item.get("place_rank")) or 0,
                "metrics": {
                    "blog_count": parse_int_safe(item.get("place_blog_cnt")) or 0,
                    "visit_count": parse_int_safe(item.get("place_visit_cnt")) or 0,
                    "save_count": parse_int_safe(item.get("place_save_cnt")) or 0,
                },
                "raw_indices": {
                    "n1": parse_float_safe(item.get("place_index1")),
                    "n2": parse_float_safe(item.get("place_index2")),
                    "n3": parse_float_safe(item.get("place_index3")),
                },
                "changes": {
                    "rank_change": parse_int_safe(item.get("place_rank_compare")) or 0,
                    "n2_change": parse_float_safe(item.get("place_index2_compare")),
                }
            }
            places.append(place)

        # 순위순 정렬
        places.sort(key=lambda x: x["rank"])

        return {
            "keyword": keyword,
            "total_count": len(places),
            "places": places,
            "cached_at": datetime.now().isoformat(),
        }

    def find_place_by_name(
        self,
        places: List[Dict],
        place_name: str
    ) -> Optional[Dict]:
        """업체명으로 해당 업체 찾기"""
        place_name = place_name.strip().lower()

        for place in places:
            if place_name in place["name"].lower():
                return place

        return None

    async def get_cached_keywords(self) -> List[str]:
        """현재 캐시된 키워드 목록 조회"""
        cache_info = self._cache.get_cache_info()
        return [e["key"] for e in cache_info.get("entries", [])]

    def get_rate_limit_status(self) -> Dict[str, Any]:
        """Rate Limit 상태 조회"""
        return {
            "per_minute_remaining": self._rate_limiter.get_remaining(),
            "per_hour_remaining": self._hourly_limiter.get_remaining(),
            "all_proxies_rate_limited": self._all_proxies_rate_limited,
            "all_proxies_rate_limit_reset_time": (
                self._all_proxies_rate_limit_reset_time.isoformat()
                if self._all_proxies_rate_limit_reset_time else None
            ),
        }

    def get_cache_stats(self) -> Dict[str, Any]:
        """캐시 통계 조회"""
        return self._cache.get_stats()

    async def clear_cache(self) -> int:
        """캐시 전체 삭제"""
        return await self._cache.clear()

    async def reset_all_proxy_limits(self) -> None:
        """모든 프록시 제한 수동 리셋 (관리자용)"""
        self._all_proxies_rate_limited = False
        self._all_proxies_rate_limit_reset_time = None
        await self._proxy_rotator.reset_all()
        logger.info("All proxy limits manually reset")

    def get_proxy_status(self) -> Dict[str, Any]:
        """프록시 상태 조회"""
        return self._proxy_rotator.get_status()

    async def reset_proxy(self, proxy_url: str) -> None:
        """특정 프록시 상태 리셋 (관리자용)"""
        await self._proxy_rotator.reset_proxy(proxy_url)


# 싱글톤 인스턴스
adlog_service = AdlogProxyService()
