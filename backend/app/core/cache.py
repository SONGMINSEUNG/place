"""
Persistent File-Based Cache with TTL
ADLOG API 호출 결과를 캐싱하여 일일 제한 문제 완화
서버 재시작에도 캐시가 유지됨
"""
import asyncio
import aiofiles
import aiofiles.os
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, Callable
from functools import wraps
import hashlib
import json
import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)

# 캐시 디렉토리 설정
CACHE_DIR = Path(__file__).parent.parent.parent / ".cache" / "adlog"


class PersistentCache:
    """파일 기반 영속 캐시 - 서버 재시작에도 캐시 유지"""

    def __init__(self, cache_dir: Path = CACHE_DIR, default_ttl: int = 3600):
        """
        Args:
            cache_dir: 캐시 파일 저장 디렉토리
            default_ttl: 기본 캐시 유효 시간 (초). 기본값 1시간
        """
        self._cache_dir = cache_dir
        self._default_ttl = default_ttl
        self._lock = asyncio.Lock()
        self._stats = {
            "hits": 0,
            "misses": 0,
            "sets": 0,
            "evictions": 0,
        }
        # 캐시 디렉토리 생성
        self._cache_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"PersistentCache initialized at: {self._cache_dir}")

    def _make_key(self, prefix: str, *args, **kwargs) -> str:
        """캐시 키 생성"""
        key_data = {
            "prefix": prefix,
            "args": args,
            "kwargs": sorted(kwargs.items())
        }
        key_str = json.dumps(key_data, sort_keys=True, default=str)
        return hashlib.md5(key_str.encode()).hexdigest()

    def _get_cache_path(self, key: str) -> Path:
        """캐시 파일 경로 반환"""
        return self._cache_dir / f"{key}.json"

    async def get(self, key: str) -> Optional[Any]:
        """캐시에서 값 조회"""
        cache_path = self._get_cache_path(key)

        async with self._lock:
            if not cache_path.exists():
                self._stats["misses"] += 1
                logger.info(f"ADLOG Cache MISS (not found): {key[:16]}...")
                return None

            try:
                async with aiofiles.open(cache_path, 'r', encoding='utf-8') as f:
                    content = await f.read()
                    entry = json.loads(content)

                expires_at = datetime.fromisoformat(entry["expires_at"])
                if datetime.now() > expires_at:
                    # 만료된 캐시 삭제
                    await aiofiles.os.remove(cache_path)
                    self._stats["evictions"] += 1
                    self._stats["misses"] += 1
                    logger.info(f"ADLOG Cache MISS (expired): {key[:16]}...")
                    return None

                self._stats["hits"] += 1
                logger.info(f"ADLOG Cache HIT: {key[:16]}...")
                return entry["value"]

            except (json.JSONDecodeError, KeyError, OSError) as e:
                # 손상된 캐시 파일 삭제
                logger.warning(f"Corrupted cache file {key[:16]}: {e}")
                try:
                    await aiofiles.os.remove(cache_path)
                except OSError:
                    pass
                self._stats["misses"] += 1
                return None

    async def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        """캐시에 값 저장"""
        ttl = ttl or self._default_ttl
        cache_path = self._get_cache_path(key)

        entry = {
            "value": value,
            "expires_at": (datetime.now() + timedelta(seconds=ttl)).isoformat(),
            "created_at": datetime.now().isoformat(),
            "ttl": ttl,
        }

        async with self._lock:
            try:
                async with aiofiles.open(cache_path, 'w', encoding='utf-8') as f:
                    await f.write(json.dumps(entry, ensure_ascii=False, default=str))
                self._stats["sets"] += 1
                logger.info(f"ADLOG Cache SET: {key[:16]}... (TTL: {ttl}s)")
            except OSError as e:
                logger.error(f"Failed to write cache {key[:16]}: {e}")

    async def delete(self, key: str) -> bool:
        """캐시에서 값 삭제"""
        cache_path = self._get_cache_path(key)

        async with self._lock:
            if cache_path.exists():
                try:
                    await aiofiles.os.remove(cache_path)
                    return True
                except OSError:
                    return False
            return False

    async def clear(self) -> int:
        """모든 캐시 삭제"""
        async with self._lock:
            count = 0
            for cache_file in self._cache_dir.glob("*.json"):
                try:
                    await aiofiles.os.remove(cache_file)
                    count += 1
                except OSError:
                    pass
            logger.info(f"Cache cleared: {count} entries")
            return count

    async def cleanup_expired(self) -> int:
        """만료된 캐시 정리"""
        async with self._lock:
            now = datetime.now()
            expired_count = 0

            for cache_file in self._cache_dir.glob("*.json"):
                try:
                    async with aiofiles.open(cache_file, 'r', encoding='utf-8') as f:
                        content = await f.read()
                        entry = json.loads(content)

                    expires_at = datetime.fromisoformat(entry["expires_at"])
                    if now > expires_at:
                        await aiofiles.os.remove(cache_file)
                        expired_count += 1
                except (json.JSONDecodeError, KeyError, OSError):
                    # 손상된 파일도 삭제
                    try:
                        await aiofiles.os.remove(cache_file)
                        expired_count += 1
                    except OSError:
                        pass

            if expired_count:
                self._stats["evictions"] += expired_count
                logger.info(f"Cleaned up {expired_count} expired cache entries")

            return expired_count

    def get_stats(self) -> Dict[str, Any]:
        """캐시 통계 조회"""
        total = self._stats["hits"] + self._stats["misses"]
        hit_rate = (self._stats["hits"] / total * 100) if total > 0 else 0

        # 현재 캐시 파일 수 계산
        current_entries = len(list(self._cache_dir.glob("*.json")))

        return {
            **self._stats,
            "total_requests": total,
            "hit_rate": f"{hit_rate:.1f}%",
            "current_entries": current_entries,
            "cache_dir": str(self._cache_dir),
        }

    def get_cache_info(self) -> Dict[str, Any]:
        """캐시 상세 정보"""
        now = datetime.now()
        entries = []

        for cache_file in list(self._cache_dir.glob("*.json"))[:20]:  # 최대 20개
            try:
                with open(cache_file, 'r', encoding='utf-8') as f:
                    entry = json.load(f)
                expires_at = datetime.fromisoformat(entry["expires_at"])
                remaining = (expires_at - now).total_seconds()
                entries.append({
                    "key": cache_file.stem[:16] + "...",
                    "remaining_ttl": max(0, int(remaining)),
                    "created_at": entry.get("created_at", "unknown"),
                })
            except (json.JSONDecodeError, KeyError, OSError):
                pass

        return {
            "stats": self.get_stats(),
            "entries": entries,
        }


# 하위 호환성을 위한 InMemoryCache 별칭
InMemoryCache = PersistentCache


class RateLimiter:
    """API 호출 속도 제한 (파일 기반으로 영속화)"""

    def __init__(self, max_calls: int, period: int, name: str = "default"):
        """
        Args:
            max_calls: 기간 내 최대 호출 수
            period: 제한 기간 (초)
            name: Rate limiter 식별자
        """
        self._max_calls = max_calls
        self._period = period
        self._name = name
        self._lock = asyncio.Lock()
        self._state_file = CACHE_DIR / f"rate_limit_{name}.json"
        # 캐시 디렉토리 생성
        CACHE_DIR.mkdir(parents=True, exist_ok=True)

    def _load_calls(self) -> list:
        """저장된 호출 기록 로드"""
        if self._state_file.exists():
            try:
                with open(self._state_file, 'r') as f:
                    data = json.load(f)
                    return [datetime.fromisoformat(t) for t in data.get("calls", [])]
            except (json.JSONDecodeError, OSError):
                pass
        return []

    def _save_calls(self, calls: list) -> None:
        """호출 기록 저장"""
        try:
            with open(self._state_file, 'w') as f:
                json.dump({
                    "calls": [t.isoformat() for t in calls],
                    "updated_at": datetime.now().isoformat()
                }, f)
        except OSError as e:
            logger.error(f"Failed to save rate limit state: {e}")

    async def acquire(self) -> bool:
        """호출 가능 여부 확인 및 기록"""
        async with self._lock:
            now = datetime.now()
            cutoff = now - timedelta(seconds=self._period)

            # 저장된 호출 기록 로드
            calls = self._load_calls()

            # 기간 지난 호출 제거
            calls = [t for t in calls if t > cutoff]

            if len(calls) >= self._max_calls:
                return False

            calls.append(now)
            self._save_calls(calls)
            return True

    async def wait_if_needed(self) -> float:
        """필요시 대기 후 호출 기록"""
        async with self._lock:
            now = datetime.now()
            cutoff = now - timedelta(seconds=self._period)

            calls = self._load_calls()
            calls = [t for t in calls if t > cutoff]

            if len(calls) >= self._max_calls:
                # 가장 오래된 호출이 만료될 때까지 대기 시간 계산
                oldest = min(calls)
                wait_time = (oldest + timedelta(seconds=self._period) - now).total_seconds()
                if wait_time > 0:
                    return wait_time

            calls.append(now)
            self._save_calls(calls)
            return 0

    def get_remaining(self) -> int:
        """남은 호출 가능 횟수"""
        now = datetime.now()
        cutoff = now - timedelta(seconds=self._period)
        calls = self._load_calls()
        valid_calls = [t for t in calls if t > cutoff]
        return max(0, self._max_calls - len(valid_calls))


def cached(cache: PersistentCache, prefix: str, ttl: Optional[int] = None):
    """
    캐시 데코레이터

    Usage:
        @cached(cache, "adlog", ttl=3600)
        async def fetch_data(keyword: str):
            ...
    """
    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # 캐시 키 생성
            key = cache._make_key(prefix, *args, **kwargs)

            # 캐시 조회
            cached_value = await cache.get(key)
            if cached_value is not None:
                return cached_value

            # 캐시 미스: 실제 함수 실행
            result = await func(*args, **kwargs)

            # 결과 캐싱
            await cache.set(key, result, ttl)

            return result

        return wrapper
    return decorator


# 글로벌 인스턴스
# ADLOG 캐시: 24시간 TTL (동일 키워드 24시간 동안 캐시) - 파일 기반으로 서버 재시작에도 유지
adlog_cache = PersistentCache(default_ttl=86400)

# ADLOG Rate Limiter: 분당 10회, 일일 100회 고려하여 보수적으로 설정
# 분당 5회로 제한 (외부 서비스 제한 고려) - 파일 기반으로 서버 재시작에도 유지
adlog_rate_limiter = RateLimiter(max_calls=5, period=60, name="adlog_minute")

# 일일 호출 제한 트래커 (더 장기적인 제한)
# 시간당 30회로 제한 - 파일 기반으로 서버 재시작에도 유지
adlog_hourly_limiter = RateLimiter(max_calls=30, period=3600, name="adlog_hourly")
