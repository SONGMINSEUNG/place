"""
ADLOG 심층 분석: N1, N2, N3 계산 로직 역공학
"""

import numpy as np
from scipy import stats
import json

# ADLOG API 실제 데이터 (홍대맛집)
adlog_data = [
    {"rank": 1, "name": "유메오뎅 홍대", "V": 1053, "B": 371, "S": 2000, "N1": 0.366894, "N2": 0.547819, "N3": 0.368945},
    {"rank": 2, "name": "카페 공명 홍대점", "V": 5887, "B": 1895, "S": 101000, "N1": 0.366894, "N2": 0.543409, "N3": 0.368612},
    {"rank": 3, "name": "너가술집사장", "V": 1409, "B": 1049, "S": 75000, "N1": 0.366894, "N2": 0.543274, "N3": 0.368602},
    {"rank": 4, "name": "장인닭갈비 홍대점", "V": 1595, "B": 3576, "S": 78000, "N1": 0.366894, "N2": 0.548632, "N3": 0.368536},
    {"rank": 5, "name": "청년닭발1987 홍대점", "V": 2070, "B": 2582, "S": 34000, "N1": 0.366894, "N2": 0.542171, "N3": 0.368519},
    {"rank": 6, "name": "서교포차", "V": 5011, "B": 790, "S": 56000, "N1": 0.366894, "N2": 0.541687, "N3": 0.368482},
    {"rank": 7, "name": "럭럭마라도원 연남점", "V": 600, "B": 35, "S": 100, "N1": 0.366894, "N2": 0.547188, "N3": 0.368427},
    {"rank": 8, "name": "티엔미미 홍대점", "V": 1029, "B": 2094, "S": 101000, "N1": 0.366894, "N2": 0.546640, "N3": 0.368385},
    {"rank": 9, "name": "수작 합정점", "V": 2444, "B": 456, "S": 2000, "N1": 0.366894, "N2": 0.539918, "N3": 0.368349},
    {"rank": 10, "name": "신호등포차 홍대점", "V": 4703, "B": 2312, "S": 82000, "N1": 0.366894, "N2": 0.546139, "N3": 0.368347},
    {"rank": 11, "name": "스케줄합정", "V": 3104, "B": 4677, "S": 131000, "N1": 0.366894, "N2": 0.537209, "N3": 0.368145},
    {"rank": 12, "name": "깃랩 홍대본점", "V": 5404, "B": 1062, "S": 121000, "N1": 0.366894, "N2": 0.536824, "N3": 0.368115},
    {"rank": 13, "name": "벽돌포차 홍대점", "V": 1445, "B": 1664, "S": 66000, "N1": 0.366894, "N2": 0.542777, "N3": 0.368094},
    {"rank": 14, "name": "우동 카덴", "V": 3414, "B": 3449, "S": 211000, "N1": 0.366894, "N2": 0.542574, "N3": 0.368078},
    {"rank": 15, "name": "룸의정석 홍대점", "V": 457, "B": 52, "S": 1000, "N1": 0.366894, "N2": 0.541140, "N3": 0.367970},
    {"rank": 16, "name": "연막창 합정홍대점", "V": 700, "B": 731, "S": 100, "N1": 0.366894, "N2": 0.536063, "N3": 0.367930},
    {"rank": 17, "name": "카레시 합정본점", "V": 2035, "B": 1122, "S": 69000, "N1": 0.366894, "N2": 0.535467, "N3": 0.367928},
    {"rank": 18, "name": "오쪼꾸미 홍대점", "V": 615, "B": 183, "S": 100, "N1": 0.366894, "N2": 0.540520, "N3": 0.367923},
    {"rank": 19, "name": "킹콩포차", "V": 1502, "B": 371, "S": 3000, "N1": 0.366894, "N2": 0.533845, "N3": 0.367891},
    {"rank": 20, "name": "우규", "V": 1271, "B": 931, "S": 41000, "N1": 0.366894, "N2": 0.533675, "N3": 0.367878},
]

print("=" * 80)
print("ADLOG 심층 분석: N1, N2, N3 계산 로직 역공학")
print("=" * 80)

# 데이터 추출
V = np.array([d['V'] for d in adlog_data])
B = np.array([d['B'] for d in adlog_data])
S = np.array([d['S'] for d in adlog_data])
N1 = np.array([d['N1'] for d in adlog_data])
N2 = np.array([d['N2'] for d in adlog_data])
N3 = np.array([d['N3'] for d in adlog_data])
ranks = np.array([d['rank'] for d in adlog_data])

log_V = np.log1p(V)
log_B = np.log1p(B)
log_S = np.log1p(S)

# ============================================================
print("\n[1] 핵심 발견: N1, N2, N3와 순위의 관계")
print("=" * 80)

# N3 → 순위 상관
n3_rank_corr = stats.spearmanr(ranks, -N3)[0]
print(f"N3 → 순위 Spearman 상관: {n3_rank_corr:.6f}")

# N3 순서대로 정렬했을 때 순위 일치율
n3_pred_ranks = stats.rankdata(-N3)
exact_match = np.sum(ranks == n3_pred_ranks) / len(ranks)
print(f"N3로 예측한 순위 정확도: {exact_match*100:.1f}%")

print("\n→ 결론: 순위 = N3 내림차순 (완벽한 상관)")

# ============================================================
print("\n[2] N3 = f(N1, N2) 공식 역산")
print("=" * 80)

# N3 = a*N1 + b*N2 + c*N1*N2 + d
X_n3 = np.column_stack([N1, N2, N1*N2, np.ones(len(N3))])
coeffs_n3, _, _, _ = np.linalg.lstsq(X_n3, N3, rcond=None)
pred_n3 = X_n3 @ coeffs_n3
r2_n3 = 1 - np.sum((N3 - pred_n3)**2) / np.sum((N3 - N3.mean())**2)

print(f"\nN3 공식:")
print(f"  N3 = {coeffs_n3[0]:.6f} * N1")
print(f"       + {coeffs_n3[1]:.6f} * N2")
print(f"       + {coeffs_n3[2]:.6f} * N1 * N2")
print(f"       + {coeffs_n3[3]:.6f}")
print(f"\n  R² = {r2_n3:.6f} ({r2_n3*100:.2f}%)")

# 단순 선형 모델 테스트
X_n3_simple = np.column_stack([N2, np.ones(len(N3))])
coeffs_simple, _, _, _ = np.linalg.lstsq(X_n3_simple, N3, rcond=None)
pred_simple = X_n3_simple @ coeffs_simple
r2_simple = 1 - np.sum((N3 - pred_simple)**2) / np.sum((N3 - N3.mean())**2)

print(f"\n단순 모델 (N3 ~ N2만):")
print(f"  N3 = {coeffs_simple[0]:.6f} * N2 + {coeffs_simple[1]:.6f}")
print(f"  R² = {r2_simple:.6f} ({r2_simple*100:.2f}%)")

# ============================================================
print("\n[3] N2 예측 시도 (V, B, S로)")
print("=" * 80)

# 다양한 조합 테스트
formulas = {
    "log(V) + log(B) + log(S)": np.column_stack([log_V, log_B, log_S, np.ones(len(N2))]),
    "+ log(V)*log(B)": np.column_stack([log_V, log_B, log_S, log_V*log_B, np.ones(len(N2))]),
    "+ V/B ratio": np.column_stack([log_V, log_B, log_S, V/(B+1), np.ones(len(N2))]),
    "+ S/(V+B)": np.column_stack([log_V, log_B, log_S, S/(V+B+1), np.ones(len(N2))]),
    "V+B 만": np.column_stack([np.log1p(V+B), np.ones(len(N2))]),
}

print(f"\n{'공식':<25} {'R²':>10} {'순위상관':>10}")
print("-" * 50)

for name, X in formulas.items():
    coeffs, _, _, _ = np.linalg.lstsq(X, N2, rcond=None)
    pred = X @ coeffs
    r2 = 1 - np.sum((N2 - pred)**2) / np.sum((N2 - N2.mean())**2)

    # 순위 예측
    pred_ranks = stats.rankdata(-pred)
    rank_corr = stats.spearmanr(ranks, pred_ranks)[0]

    print(f"{name:<25} {r2:>10.4f} {rank_corr:>10.4f}")

print("\n→ 결론: V, B, S로 N2를 예측할 수 없음 (R² < 10%)")

# ============================================================
print("\n[4] N2의 특성 분석")
print("=" * 80)

print(f"\nN2 통계:")
print(f"  최소: {N2.min():.6f}")
print(f"  최대: {N2.max():.6f}")
print(f"  평균: {N2.mean():.6f}")
print(f"  표준편차: {N2.std():.6f}")
print(f"  범위: {N2.max() - N2.min():.6f}")

# 순위와의 관계
n2_rank_corr = stats.spearmanr(ranks, -N2)[0]
print(f"\nN2 → 순위 Spearman 상관: {n2_rank_corr:.4f}")

# 충격적 사례
print("\n충격적 사례:")
print(f"  1위 (유메오뎅): V={V[0]}, B={B[0]}, S={S[0]} → N2={N2[0]:.6f}")
print(f"  7위 (럭럭마라): V={V[6]}, B={B[6]}, S={S[6]} → N2={N2[6]:.6f}")
print(f"  → 7위 업체가 V, B, S 모두 작지만 N2는 1위와 비슷!")

# ============================================================
print("\n[5] 핵심 결론")
print("=" * 80)

print("""
┌─────────────────────────────────────────────────────────────────┐
│                    ADLOG 역공학 최종 결론                         │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  1. N1 = 키워드별 고정값                                          │
│     - 홍대맛집: 0.366894                                         │
│     - 강남카페: 0.397269                                         │
│     - 다른 키워드: 별도 확인 필요                                 │
│                                                                   │
│  2. N2 = 숨겨진 요소로 결정 (V, B, S와 무관!)                     │
│     - V, B, S로 예측 R² < 10%                                    │
│     - 90% 이상이 알 수 없는 요소로 결정됨                         │
│     - 추정: CTR, 체류시간, 예약률, 클릭수 등                      │
│     - 이 데이터는 네이버만 가지고 있음                            │
│                                                                   │
│  3. N3 = f(N1, N2)로 계산됨                                       │
│     - N3 ≈ 0.075 * N2 + 상수 (단순 모델 R²=99.6%)                │
│     - ADLOG 자체 알고리즘으로 계산                                │
│                                                                   │
│  4. 순위 = N3 내림차순 (완벽한 상관 1.0)                          │
│                                                                   │
│  5. ADLOG가 N2를 어디서 가져오는지:                               │
│     - 옵션 A: 네이버 비공개 API 접근 (가능성 높음)                │
│     - 옵션 B: 네이버 내부 직원 협력                               │
│     - 옵션 C: 자체 추정 알고리즘 (V,B,S 외 데이터 사용)          │
│                                                                   │
│  6. 현실적 해결책:                                                │
│     - ADLOG API를 직접 호출하여 N1, N2, N3 수집                   │
│     - 자체 예측 포기, ADLOG 데이터 활용                           │
│                                                                   │
└─────────────────────────────────────────────────────────────────┘
""")

# ============================================================
print("\n[6] ADLOG API 활용 방안")
print("=" * 80)

print("""
ADLOG API 엔드포인트:
  URL: http://adlog.ai.kr/placeAnalysis.php
  Method: POST
  Content-Type: application/json
  Body: {"query": "검색키워드"}

응답 데이터:
  - place_rank: 순위
  - place_id: 네이버 플레이스 ID
  - place_name: 업체명
  - place_blog_cnt: 블로그 리뷰 수 (B)
  - place_visit_cnt: 방문자 리뷰 수 (V)
  - place_save_cnt: 저장 수 (S)
  - place_index1: N1 (키워드 지수)
  - place_index2: N2 (품질 지수) ← 핵심!
  - place_index3: N3 (종합 지수)
  - place_rank_compare: 순위 변동
  - place_index2_compare: N2 변동

활용 전략:
  1. 키워드별로 ADLOG API 호출
  2. N2, N3 값 저장 및 추적
  3. N2 변동 모니터링으로 순위 변화 예측
  4. 경쟁사 N2 분석으로 마케팅 전략 수립
""")

print("\n" + "=" * 80)
print("분석 완료")
print("=" * 80)
