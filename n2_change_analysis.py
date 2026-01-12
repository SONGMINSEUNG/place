"""
N2 변화량 분석 - place_index2_compare와 다른 변수의 관계
"""

import numpy as np
from scipy import stats

# ADLOG API 데이터 (홍대맛집) - 변화량 포함
data = [
    {"rank": 1, "V": 1053, "B": 371, "S": 2000, "N2": 0.547819,
     "V_change": 76, "B_change": 1, "N2_change": 0.004369},
    {"rank": 2, "V": 5887, "B": 1895, "S": 101000, "N2": 0.543409,
     "V_change": 34, "B_change": 7, "N2_change": -0.004155},
    {"rank": 3, "V": 1409, "B": 1049, "S": 75000, "N2": 0.543274,
     "V_change": 72, "B_change": -3, "N2_change": 0.024765},
    {"rank": 4, "V": 1595, "B": 3576, "S": 78000, "N2": 0.548632,
     "V_change": 40, "B_change": 5, "N2_change": -0.014396},
    {"rank": 6, "V": 5011, "B": 790, "S": 56000, "N2": 0.541687,
     "V_change": 144, "B_change": 7, "N2_change": -0.005794},
    {"rank": 7, "V": 600, "B": 35, "S": 100, "N2": 0.547188,
     "V_change": 112, "B_change": 6, "N2_change": 0.001319},
    {"rank": 8, "V": 1029, "B": 2094, "S": 101000, "N2": 0.546640,
     "V_change": 9, "B_change": 31, "N2_change": 0.010352},
    {"rank": 9, "V": 2444, "B": 456, "S": 2000, "N2": 0.539918,
     "V_change": 133, "B_change": 15, "N2_change": 0.006416},
    {"rank": 10, "V": 4703, "B": 2312, "S": 82000, "N2": 0.546139,
     "V_change": 206, "B_change": 8, "N2_change": 0.003250},
    {"rank": 11, "V": 3104, "B": 4677, "S": 131000, "N2": 0.537209,
     "V_change": 72, "B_change": -3, "N2_change": -0.017731},
    {"rank": 12, "V": 5404, "B": 1062, "S": 121000, "N2": 0.536824,
     "V_change": 68, "B_change": -1, "N2_change": 0.008953},
    {"rank": 14, "V": 3414, "B": 3449, "S": 211000, "N2": 0.542574,
     "V_change": 7, "B_change": 25, "N2_change": 0.026031},
]

print("=" * 80)
print("N2 변화량 분석 - N2_change = f(V_change, B_change)?")
print("=" * 80)

# 데이터 추출
V = np.array([d['V'] for d in data])
B = np.array([d['B'] for d in data])
S = np.array([d['S'] for d in data])
N2 = np.array([d['N2'] for d in data])
V_change = np.array([d['V_change'] for d in data])
B_change = np.array([d['B_change'] for d in data])
N2_change = np.array([d['N2_change'] for d in data])

print("\n[1] 기본 통계")
print("-" * 60)
print(f"V_change 범위: {V_change.min()} ~ {V_change.max()} (평균: {V_change.mean():.1f})")
print(f"B_change 범위: {B_change.min()} ~ {B_change.max()} (평균: {B_change.mean():.1f})")
print(f"N2_change 범위: {N2_change.min():.6f} ~ {N2_change.max():.6f}")

print("\n[2] 상관관계 분석")
print("-" * 60)

# N2_change와 각 변수의 상관
corr_v = stats.pearsonr(V_change, N2_change)[0]
corr_b = stats.pearsonr(B_change, N2_change)[0]
corr_vb = stats.pearsonr(V_change + B_change, N2_change)[0]

print(f"V_change → N2_change 상관: {corr_v:+.4f}")
print(f"B_change → N2_change 상관: {corr_b:+.4f}")
print(f"(V+B)_change → N2_change 상관: {corr_vb:+.4f}")

# 비율 변화
V_ratio_change = V_change / (V + 1)
B_ratio_change = B_change / (B + 1)

corr_v_ratio = stats.pearsonr(V_ratio_change, N2_change)[0]
corr_b_ratio = stats.pearsonr(B_ratio_change, N2_change)[0]

print(f"\nV_change/V 비율 → N2_change 상관: {corr_v_ratio:+.4f}")
print(f"B_change/B 비율 → N2_change 상관: {corr_b_ratio:+.4f}")

print("\n[3] 회귀 분석: N2_change = f(V_change, B_change)")
print("-" * 60)

# 다양한 모델 테스트
models = {
    "V_change만": np.column_stack([V_change, np.ones(len(N2_change))]),
    "B_change만": np.column_stack([B_change, np.ones(len(N2_change))]),
    "V+B change": np.column_stack([V_change, B_change, np.ones(len(N2_change))]),
    "비율 변화": np.column_stack([V_ratio_change, B_ratio_change, np.ones(len(N2_change))]),
    "B_change만(블로그)": np.column_stack([B_change, np.ones(len(N2_change))]),
}

print(f"\n{'모델':20s} {'R²':>10s} {'해석'}")
print("-" * 50)

for name, X in models.items():
    coeffs, _, _, _ = np.linalg.lstsq(X, N2_change, rcond=None)
    pred = X @ coeffs
    r2 = 1 - np.sum((N2_change - pred)**2) / np.sum((N2_change - N2_change.mean())**2)

    if r2 > 0.3:
        interp = "★★ 유의미!"
    elif r2 > 0.1:
        interp = "★ 약간 관련"
    else:
        interp = "관련 없음"

    print(f"{name:20s} {r2:>10.4f} {interp}")

print("\n[4] 핵심 발견: B_change(블로그 변화)와 N2_change 관계")
print("-" * 60)

# B_change로 N2_change 예측
X_b = np.column_stack([B_change, np.ones(len(N2_change))])
coeffs_b, _, _, _ = np.linalg.lstsq(X_b, N2_change, rcond=None)
pred_b = X_b @ coeffs_b
r2_b = 1 - np.sum((N2_change - pred_b)**2) / np.sum((N2_change - N2_change.mean())**2)

print(f"N2_change = {coeffs_b[0]:.8f} * B_change + {coeffs_b[1]:.6f}")
print(f"R² = {r2_b:.4f}")

# 상세 비교
print(f"\n{'순위':>4} {'B변화':>8} {'N2변화(실제)':>14} {'N2변화(예측)':>14} {'오차':>10}")
print("-" * 55)
for i, d in enumerate(data):
    pred = coeffs_b[0] * d['B_change'] + coeffs_b[1]
    error = d['N2_change'] - pred
    print(f"{d['rank']:>4} {d['B_change']:>+8} {d['N2_change']:>+14.6f} {pred:>+14.6f} {error:>+10.6f}")

print("\n[5] 새로운 가설: N2는 누적 행동 데이터의 함수")
print("-" * 60)

# N2 자체를 다시 분석 - V/B 비율 관점
VB_ratio = V / (B + 1)
BV_ratio = B / (V + 1)

corr_vb_ratio = stats.pearsonr(VB_ratio, N2)[0]
corr_bv_ratio = stats.pearsonr(BV_ratio, N2)[0]

print(f"V/B 비율 → N2 상관: {corr_vb_ratio:+.4f}")
print(f"B/V 비율 → N2 상관: {corr_bv_ratio:+.4f}")

# 새로운 조합
engagement = V + B * 2  # 블로그에 가중치
engagement_per_save = engagement / (S + 1)

corr_eng = stats.pearsonr(engagement, N2)[0]
corr_eng_save = stats.pearsonr(engagement_per_save, N2)[0]

print(f"Engagement(V+2B) → N2 상관: {corr_eng:+.4f}")
print(f"Engagement/S → N2 상관: {corr_eng_save:+.4f}")

# 역수/로그 조합
import warnings
warnings.filterwarnings('ignore')

log_V = np.log1p(V)
log_B = np.log1p(B)
log_S = np.log1p(S)

# N2와 상관관계가 높은 조합 찾기
combos = {
    "log(V)/log(S)": log_V / (log_S + 0.1),
    "log(B)/log(S)": log_B / (log_S + 0.1),
    "1/log(S)": 1 / (log_S + 0.1),
    "log(V+B)/log(S)": np.log1p(V+B) / (log_S + 0.1),
    "log(V)*log(B)": log_V * log_B,
    "log(V+B+S)": np.log1p(V+B+S),
}

print(f"\n다양한 조합과 N2 상관:")
for name, combo in combos.items():
    corr = stats.pearsonr(combo, N2)[0]
    if abs(corr) > 0.3:
        print(f"  {name}: {corr:+.4f} ★")
    else:
        print(f"  {name}: {corr:+.4f}")

print("\n" + "=" * 80)
print("[결론]")
print("=" * 80)
print("""
1. N2_change와 B_change의 상관관계 존재 (약 0.4)
   → 블로그 리뷰 증가 → N2 상승 경향

2. 하지만 R² < 30%
   → 블로그 변화만으로는 N2 변화를 설명 못함

3. N2는 단순 V, B, S 조합이 아님
   → CTR, 체류시간 등 숨겨진 행동 데이터 필요

4. ADLOG가 이 데이터를 어디서 가져오는지?
   → 네이버 공개 API에는 없음
   → ADLOG 자체 계산 또는 비공개 채널
""")
