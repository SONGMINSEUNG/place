#!/usr/bin/env python3
"""
ADLOG API 무료 프록시 테스트 스크립트

1. 무료 프록시 목록을 수집
2. 각 프록시로 ADLOG API 호출 테스트
3. 성공하는 프록시 찾기
"""

import asyncio
import httpx
import time
import json
from typing import Optional, List, Dict, Tuple
from dataclasses import dataclass
import aiohttp
from bs4 import BeautifulSoup


@dataclass
class ProxyInfo:
    host: str
    port: str
    protocol: str = "http"
    country: str = ""
    anonymity: str = ""

    @property
    def url(self) -> str:
        return f"{self.protocol}://{self.host}:{self.port}"


# ADLOG API 설정
ADLOG_API_URL = "http://adlog.ai.kr/placeAnalysis.php"
TEST_KEYWORD = "홍대맛집"  # 테스트용 키워드
TIMEOUT_SECONDS = 15  # 프록시 타임아웃


async def fetch_free_proxy_list() -> List[ProxyInfo]:
    """
    free-proxy-list.net에서 무료 프록시 목록 수집
    """
    proxies = []

    print("\n[1/4] 무료 프록시 목록 수집 중...")

    # 여러 소스에서 프록시 수집
    sources = [
        fetch_from_free_proxy_list,
        fetch_from_sslproxies,
        fetch_from_proxylist_geonode,
    ]

    for source in sources:
        try:
            source_proxies = await source()
            proxies.extend(source_proxies)
            print(f"  - {source.__name__}: {len(source_proxies)}개 수집")
        except Exception as e:
            print(f"  - {source.__name__}: 수집 실패 ({str(e)[:50]})")

    # 중복 제거
    unique_proxies = []
    seen = set()
    for p in proxies:
        key = f"{p.host}:{p.port}"
        if key not in seen:
            seen.add(key)
            unique_proxies.append(p)

    print(f"\n총 {len(unique_proxies)}개 고유 프록시 수집됨")
    return unique_proxies


async def fetch_from_free_proxy_list() -> List[ProxyInfo]:
    """free-proxy-list.net에서 프록시 수집"""
    url = "https://free-proxy-list.net/"
    proxies = []

    async with aiohttp.ClientSession() as session:
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
            html = await resp.text()
            soup = BeautifulSoup(html, 'html.parser')

            table = soup.find('table', {'class': 'table'})
            if not table:
                return proxies

            rows = table.find_all('tr')[1:]  # 헤더 제외
            for row in rows[:50]:  # 상위 50개만
                cols = row.find_all('td')
                if len(cols) >= 7:
                    host = cols[0].text.strip()
                    port = cols[1].text.strip()
                    country = cols[3].text.strip()
                    anonymity = cols[4].text.strip()
                    https = cols[6].text.strip()

                    # HTTP만 (ADLOG가 HTTP 사용)
                    if https.lower() == 'no':
                        proxies.append(ProxyInfo(
                            host=host,
                            port=port,
                            protocol="http",
                            country=country,
                            anonymity=anonymity
                        ))

    return proxies


async def fetch_from_sslproxies() -> List[ProxyInfo]:
    """sslproxies.org에서 프록시 수집 (HTTP 프록시)"""
    url = "https://www.sslproxies.org/"
    proxies = []

    async with aiohttp.ClientSession() as session:
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
            html = await resp.text()
            soup = BeautifulSoup(html, 'html.parser')

            table = soup.find('table', {'class': 'table'})
            if not table:
                return proxies

            rows = table.find_all('tr')[1:]
            for row in rows[:30]:
                cols = row.find_all('td')
                if len(cols) >= 7:
                    host = cols[0].text.strip()
                    port = cols[1].text.strip()
                    country = cols[3].text.strip()

                    proxies.append(ProxyInfo(
                        host=host,
                        port=port,
                        protocol="http",
                        country=country
                    ))

    return proxies


async def fetch_from_proxylist_geonode() -> List[ProxyInfo]:
    """geonode.com API에서 프록시 수집"""
    url = "https://proxylist.geonode.com/api/proxy-list?limit=50&page=1&sort_by=lastChecked&sort_type=desc&protocols=http"
    proxies = []

    async with aiohttp.ClientSession() as session:
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
            data = await resp.json()

            for item in data.get('data', []):
                proxies.append(ProxyInfo(
                    host=item['ip'],
                    port=str(item['port']),
                    protocol="http",
                    country=item.get('country', ''),
                    anonymity=item.get('anonymityLevel', '')
                ))

    return proxies


async def test_proxy_connectivity(proxy: ProxyInfo) -> Tuple[bool, float, str]:
    """
    프록시 기본 연결 테스트 (httpbin.org)
    Returns: (성공여부, 응답시간, 메시지)
    """
    try:
        start = time.time()
        async with httpx.AsyncClient(
            proxy=proxy.url,
            timeout=httpx.Timeout(5.0)
        ) as client:
            resp = await client.get("http://httpbin.org/ip")
            elapsed = time.time() - start
            if resp.status_code == 200:
                return True, elapsed, "연결 성공"
            return False, elapsed, f"HTTP {resp.status_code}"
    except Exception as e:
        return False, 0, str(e)[:40]


async def test_proxy_with_adlog(proxy: ProxyInfo) -> Dict:
    """
    프록시로 ADLOG API 호출 테스트
    """
    result = {
        "proxy": proxy.url,
        "country": proxy.country,
        "success": False,
        "response_time": 0,
        "error": None,
        "data": None
    }

    try:
        start = time.time()
        async with httpx.AsyncClient(
            proxy=proxy.url,
            timeout=httpx.Timeout(TIMEOUT_SECONDS)
        ) as client:
            response = await client.post(
                ADLOG_API_URL,
                json={"query": TEST_KEYWORD},
                headers={"Content-Type": "application/json"}
            )
            elapsed = time.time() - start
            result["response_time"] = round(elapsed, 2)

            if response.status_code == 200:
                data = response.json()

                # ADLOG 응답 검증
                if data.get("code") == "2000":
                    result["error"] = "ADLOG 일일 제한 도달"
                elif "items" in data or "data" in data:
                    items = data.get("items") or data.get("data", [])
                    result["success"] = True
                    result["data"] = {
                        "item_count": len(items),
                        "sample": items[0] if items else None
                    }
                else:
                    result["error"] = f"예상치 못한 응답: {str(data)[:100]}"
            else:
                result["error"] = f"HTTP {response.status_code}"

    except httpx.TimeoutException:
        result["error"] = "타임아웃"
    except httpx.ProxyError as e:
        result["error"] = f"프록시 에러: {str(e)[:40]}"
    except Exception as e:
        result["error"] = str(e)[:50]

    return result


async def main():
    print("=" * 60)
    print("ADLOG API 무료 프록시 테스트 스크립트")
    print("=" * 60)

    # 1. 무료 프록시 목록 수집
    proxies = await fetch_free_proxy_list()

    if not proxies:
        print("\n[ERROR] 프록시를 수집할 수 없습니다.")
        return

    # 2. 기본 연결 테스트 (빠른 필터링)
    print("\n[2/4] 프록시 기본 연결 테스트 중...")

    working_proxies = []
    test_tasks = [test_proxy_connectivity(p) for p in proxies[:80]]  # 최대 80개
    results = await asyncio.gather(*test_tasks, return_exceptions=True)

    for proxy, result in zip(proxies[:80], results):
        if isinstance(result, tuple):
            success, elapsed, msg = result
            if success and elapsed < 5:
                working_proxies.append((proxy, elapsed))
                print(f"  [OK] {proxy.host}:{proxy.port} ({proxy.country}) - {elapsed:.2f}s")

    print(f"\n{len(working_proxies)}개 프록시 연결 가능")

    if not working_proxies:
        print("\n[ERROR] 동작하는 프록시가 없습니다.")
        return

    # 응답 시간 순으로 정렬
    working_proxies.sort(key=lambda x: x[1])
    top_proxies = [p for p, _ in working_proxies[:20]]  # 상위 20개만 테스트

    # 3. ADLOG API 테스트
    print(f"\n[3/4] ADLOG API 테스트 중 (상위 {len(top_proxies)}개 프록시)...")
    print(f"테스트 키워드: '{TEST_KEYWORD}'")
    print("-" * 50)

    successful_proxies = []

    for i, proxy in enumerate(top_proxies):
        print(f"\n[{i+1}/{len(top_proxies)}] {proxy.host}:{proxy.port} ({proxy.country}) 테스트 중...", end=" ")
        result = await test_proxy_with_adlog(proxy)

        if result["success"]:
            print(f"SUCCESS ({result['response_time']}s)")
            print(f"  -> {result['data']['item_count']}개 업체 데이터 수신")
            successful_proxies.append(result)
        else:
            print(f"FAIL - {result['error']}")

    # 4. 결과 요약
    print("\n" + "=" * 60)
    print("[4/4] 테스트 결과 요약")
    print("=" * 60)

    if successful_proxies:
        print(f"\n[SUCCESS] {len(successful_proxies)}개 프록시가 ADLOG API와 동작합니다!\n")

        # 응답 시간순 정렬
        successful_proxies.sort(key=lambda x: x["response_time"])

        for i, result in enumerate(successful_proxies, 1):
            print(f"{i}. {result['proxy']}")
            print(f"   국가: {result['country']}, 응답시간: {result['response_time']}s")
            print()

        # .env 설정 안내
        best_proxy = successful_proxies[0]
        print("-" * 50)
        print("\n.env 파일에 추가할 설정:")
        print("-" * 50)
        print(f"""
# ADLOG API 프록시 설정
ADLOG_PROXY_URL={best_proxy['proxy']}

# 또는 공용 프록시로 설정 (네이버 크롤링에도 사용)
# PROXY_URL={best_proxy['proxy']}
""")

        # 성공한 프록시 목록 저장
        output_file = "/Users/songminseung/place-analytics/working_proxies.json"
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(successful_proxies, f, ensure_ascii=False, indent=2)
        print(f"\n동작하는 프록시 목록이 {output_file}에 저장되었습니다.")

    else:
        print("\n[FAIL] ADLOG API와 동작하는 무료 프록시를 찾지 못했습니다.")
        print("\n가능한 원인:")
        print("1. 무료 프록시의 불안정성 (일시적 문제)")
        print("2. ADLOG API의 프록시 차단")
        print("3. 무료 프록시의 느린 응답 속도")
        print("\n권장 사항:")
        print("- 유료 프록시 서비스 사용 (예: BrightData, Oxylabs)")
        print("- VPN 서비스 사용")
        print("- 스크립트를 다시 실행하여 다른 프록시 테스트")


if __name__ == "__main__":
    print("\n필요한 패키지 확인 중...")
    print("필요: httpx, aiohttp, beautifulsoup4")
    print()

    asyncio.run(main())
