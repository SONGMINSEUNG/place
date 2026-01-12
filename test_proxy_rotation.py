#!/usr/bin/env python3
"""
ADLOG API 프록시 로테이션 테스트 스크립트

기능:
1. 설정된 프록시 목록 확인
2. 프록시 로테이션 동작 테스트
3. 실패/Rate limit 시 자동 전환 테스트
"""

import asyncio
import sys
import os

# 프로젝트 루트를 Python 경로에 추가
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

# 환경변수 로드 (.env 파일)
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), 'backend', '.env'))


async def test_proxy_rotation():
    """프록시 로테이션 테스트"""
    from app.services.adlog_proxy import (
        get_adlog_proxy_list,
        ProxyRotator,
        AdlogProxyService,
        adlog_service
    )

    print("=" * 60)
    print("ADLOG API 프록시 로테이션 테스트")
    print("=" * 60)

    # 1. 프록시 목록 확인
    print("\n[1] 설정된 프록시 목록 확인")
    print("-" * 40)

    proxies = get_adlog_proxy_list()
    if not proxies:
        print("  [WARNING] 설정된 프록시가 없습니다!")
        print("  .env 파일에 ADLOG_PROXY_LIST 또는 ADLOG_PROXY_URL을 설정하세요.")
    else:
        for i, p in enumerate(proxies, 1):
            print(f"  {i}. {p['name']} - {p['url']}")

    # 2. ProxyRotator 테스트
    print("\n[2] ProxyRotator 라운드 로빈 테스트")
    print("-" * 40)

    rotator = ProxyRotator(proxies, cooldown_minutes=5)

    print("  연속 5회 프록시 요청:")
    for i in range(5):
        proxy = await rotator.get_next_proxy()
        if proxy:
            print(f"    {i+1}. {proxy['name']}")
        else:
            print(f"    {i+1}. (프록시 없음 - 직접 연결)")

    # 3. 프록시 실패 마킹 테스트
    print("\n[3] 프록시 실패 마킹 테스트")
    print("-" * 40)

    if proxies:
        test_proxy = proxies[0]
        await rotator.mark_failed(test_proxy["url"], "test failure")
        print(f"  {test_proxy['name']} 프록시를 실패로 마킹")

        status = rotator.get_status()
        print(f"  현재 사용 가능: {status['available_count']}/{status['total_proxies']}")

        for ps in status['proxies']:
            print(f"    - {ps['name']}: {ps['status']}")

        # 복구
        await rotator.reset_all()
        print("  모든 프록시 상태 리셋 완료")

    # 4. 실제 API 호출 테스트
    print("\n[4] 실제 ADLOG API 호출 테스트")
    print("-" * 40)

    keyword = "홍대맛집"
    print(f"  키워드: {keyword}")

    try:
        result = await adlog_service.fetch_keyword_analysis(keyword, force_refresh=True)
        print(f"  [SUCCESS] {result['total_count']}개 업체 데이터 수신")

        if result['places']:
            top3 = result['places'][:3]
            print("  상위 3개 업체:")
            for p in top3:
                print(f"    - {p['rank']}위: {p['name']}")

    except Exception as e:
        print(f"  [ERROR] {type(e).__name__}: {str(e)}")

    # 5. 프록시 상태 확인
    print("\n[5] 프록시 상태 확인")
    print("-" * 40)

    proxy_status = adlog_service.get_proxy_status()
    print(f"  총 프록시: {proxy_status['total_proxies']}")
    print(f"  사용 가능: {proxy_status['available_count']}")

    for ps in proxy_status['proxies']:
        status_str = ps['status']
        if ps['status'] != 'available' and 'available_at' in ps:
            status_str += f" (복구 예정: {ps['available_at']})"
        print(f"    - {ps['name']}: {status_str}")

    # 6. Rate Limit 상태 확인
    print("\n[6] Rate Limit 상태")
    print("-" * 40)

    rate_status = adlog_service.get_rate_limit_status()
    print(f"  분당 남은 요청: {rate_status['per_minute_remaining']}")
    print(f"  시간당 남은 요청: {rate_status['per_hour_remaining']}")
    print(f"  모든 프록시 Rate Limited: {rate_status['all_proxies_rate_limited']}")

    print("\n" + "=" * 60)
    print("테스트 완료")
    print("=" * 60)


async def test_failover():
    """프록시 자동 전환 테스트"""
    from app.services.adlog_proxy import ProxyRotator

    print("\n" + "=" * 60)
    print("프록시 자동 전환 (Failover) 테스트")
    print("=" * 60)

    # 테스트용 프록시 목록 (일부러 잘못된 프록시 포함)
    test_proxies = [
        {"url": "http://invalid.proxy:1234", "name": "Invalid1"},
        {"url": "http://invalid.proxy:5678", "name": "Invalid2"},
        {"url": "http://154.3.236.202:3128", "name": "US"},
        {"url": "http://101.47.16.15:7890", "name": "SG"},
    ]

    rotator = ProxyRotator(test_proxies, cooldown_minutes=1)

    print("\n첫 번째 프록시 실패 시뮬레이션:")
    await rotator.mark_failed(test_proxies[0]["url"], "connection timeout")
    await rotator.mark_failed(test_proxies[1]["url"], "connection refused")

    print("\n사용 가능한 프록시:")
    available = rotator.get_available_proxies()
    for p in available:
        print(f"  - {p['name']}")

    print(f"\n다음 프록시 요청: ", end="")
    next_proxy = await rotator.get_next_proxy()
    if next_proxy:
        print(f"{next_proxy['name']}")
    else:
        print("없음")


if __name__ == "__main__":
    print("\n필요한 패키지: httpx, python-dotenv")
    print("설치: pip install httpx python-dotenv\n")

    asyncio.run(test_proxy_rotation())
    # asyncio.run(test_failover())  # 필요 시 주석 해제
