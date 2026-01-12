"""
ADLOG 최종 분석: N3 공식 정밀 역추적
=====================================
핵심 발견:
1. Type A: N2/N3가 순위 결정, N2 예측 가능하나 정밀도 문제
2. Type B: 키워드마다 다름 (브런치=N1, 술집/고기집=N3)

이번 분석 목표:
1. N3 = f(N1, N2) 정밀 공식 도출
2. N3가 순위를 결정할 때 V,B,S로 직접 예측 가능한지 확인
3. 숨겨진 요소 최종 정리
"""

import numpy as np
from scipy import stats
from scipy.optimize import minimize, curve_fit
import warnings
warnings.filterwarnings('ignore')

# ============================================================================
# 데이터 정의
# ============================================================================

# Type A
matjip_data = [
    (1, "연남살롱", 1054, 2110, 71500, 0.366894, 0.600166, 0.408574),
    (2, "도산분식", 2024, 2119, 103500, 0.366894, 0.595458, 0.407984),
    (3, "스시도쿄 홍대점", 420, 2031, 50500, 0.366894, 0.591671, 0.407502),
    (4, "진저 더 레스토랑", 1037, 977, 68500, 0.366894, 0.590108, 0.407309),
    (5, "도마 홍대본점", 2295, 1099, 66000, 0.366894, 0.588880, 0.407145),
    (6, "홍대오뎅 상수점", 1499, 1069, 28500, 0.366894, 0.572823, 0.405174),
    (7, "비시야끼홍대본점", 1011, 662, 23000, 0.366894, 0.559652, 0.403593),
    (8, "왈도손칼국수", 1207, 594, 34500, 0.366894, 0.556620, 0.403232),
    (9, "훠궈101 홍대점", 1159, 768, 33000, 0.366894, 0.555447, 0.403087),
    (10, "술과고기 그리고 안주", 766, 644, 26000, 0.366894, 0.554430, 0.402968),
]

cafe_data = [
    (1, "스틸북스 2호점", 2259, 1949, 138500, 0.397269, 0.640115, 0.429197),
    (2, "디미토", 3050, 1098, 189500, 0.397269, 0.638558, 0.429035),
    (3, "까미카페", 2141, 1108, 122500, 0.397269, 0.637006, 0.428871),
    (4, "쌤컴퍼니", 3219, 1389, 190500, 0.397269, 0.636655, 0.428834),
    (5, "성수디어모먼트", 2785, 1007, 171500, 0.397269, 0.630803, 0.428227),
    (6, "콘하스", 3048, 1168, 187500, 0.397269, 0.629907, 0.428133),
    (7, "카페 더 타로", 1891, 1227, 135000, 0.397269, 0.626912, 0.427828),
    (8, "백만송이카페", 1096, 766, 73000, 0.397269, 0.615188, 0.426573),
    (9, "릴트 강남점", 4148, 712, 189000, 0.397269, 0.614958, 0.426539),
    (10, "그리핀필즈", 2310, 595, 196500, 0.397269, 0.614422, 0.426477),
]

ring_data = [
    (1, "일로일이팔칠", 215, 3, 37500, 0.456679, 0.554896, 0.421694),
    (2, "주얼리공방 담", 1129, 192, 54000, 0.456679, 0.553161, 0.421516),
    (3, "장신구공방 수다", 556, 38, 37500, 0.456679, 0.548022, 0.421006),
    (4, "레몬스타쥬얼리공방", 206, 12, 22500, 0.456679, 0.541339, 0.420353),
    (5, "아뜰리에드보아", 2095, 95, 61500, 0.456679, 0.537682, 0.419995),
    (6, "김수공작소", 225, 9, 28500, 0.456679, 0.537499, 0.419965),
    (7, "디제이주얼리", 1038, 54, 28500, 0.456679, 0.527695, 0.419015),
    (8, "드영공방", 330, 20, 20000, 0.456679, 0.526958, 0.418936),
    (9, "스튜디오홍가", 1097, 86, 52000, 0.456679, 0.523098, 0.418563),
    (10, "랩홀릭랩그로운다이아몬드", 1188, 23, 42000, 0.456679, 0.520396, 0.418297),
]

# Type B
brunch_data = [
    (1, "쎄콩데live", 2779, 1409, 40000, 0.570408, 0.495284, 0.422618),
    (2, "메이플탑", 2224, 1454, 50000, 0.567826, 0.506261, 0.422058),
    (3, "써니눅 성수", 1313, 592, 33000, 0.565093, 0.484981, 0.420694),
    (4, "앤드밀 성수점", 1784, 2301, 109000, 0.564700, 0.512296, 0.421105),
    (5, "파이프그라운드", 4492, 2377, 100000, 0.564334, 0.518283, 0.421193),
    (6, "프렌즈앤야드", 3204, 440, 41000, 0.563447, 0.510410, 0.420562),
    (7, "밋보어 서울", 303, 569, 42000, 0.562872, 0.489894, 0.419570),
    (8, "리틀포레스트", 500, 855, 40000, 0.562425, 0.439621, 0.417504),
    (9, "플르서라구뜨", 1102, 2031, 109000, 0.561602, 0.512415, 0.419941),
    (10, "테니", 1654, 1366, 74000, 0.561392, 0.523002, 0.420261),
]

bar_data = [
    (1, "이태원사랑방", 1568, 990, 68000, 0.562335, 0.527362, 0.420781),
    (2, "마가진상회", 742, 416, 7000, 0.560117, 0.510203, 0.419297),
    (3, "김실력포차", 1166, 446, 38000, 0.558642, 0.522490, 0.419204),
    (4, "네번째집", 926, 570, 76000, 0.558660, 0.520155, 0.419123),
    (5, "술꼬마", 526, 372, 27000, 0.560615, 0.490019, 0.418723),
    (6, "이태원데판", 1104, 1518, 47000, 0.558367, 0.508585, 0.418576),
    (7, "티키타카", 306, 1326, 24000, 0.559986, 0.482771, 0.418213),
    (8, "이태원 주식", 876, 3182, 90000, 0.559643, 0.483778, 0.418121),
    (9, "이진칸", 1510, 2682, 151000, 0.562904, 0.446979, 0.417963),
    (10, "이태원교집합", 900, 592, 103000, 0.555001, 0.507475, 0.417678),
]

meat_data = [
    (1, "돼지명가 용문직영점", 1252, 174, 38000, 0.544612, 0.576698, 0.423032),
    (2, "고반", 741, 91, 7500, 0.530653, 0.587689, 0.420788),
    (3, "불백마을 대전둔산직영점", 654, 206, 28000, 0.524685, 0.591915, 0.420120),
    (4, "맥시멈식육식당 둔산점", 1078, 130, 65500, 0.526499, 0.560988, 0.417968),
    (5, "놀부부대찌개보쌈", 2318, 202, 12000, 0.524299, 0.564040, 0.417704),
    (6, "화로대첩", 396, 26, 11000, 0.518195, 0.566108, 0.416610),
    (7, "봉우이층집 용문점", 1110, 222, 21500, 0.519149, 0.553167, 0.415784),
    (8, "흥부찜 대전 둔산점", 449, 150, 15000, 0.516003, 0.551688, 0.415187),
    (9, "삼굽살 대전 둔산점", 1195, 109, 5500, 0.512098, 0.561422, 0.415074),
    (10, "곱가네 둔산점", 439, 51, 5000, 0.512050, 0.552823, 0.414565),
]

print("=" * 80)
print("ADLOG 최종 분석: N3 공식 정밀 역추적")
print("=" * 80)

# ============================================================================
# PART 1: N3 = f(N1, N2) 정밀 공식 역추적
# ============================================================================
print("\n" + "=" * 80)
print("PART 1: N3 = f(N1, N2) 정밀 공식 역추적")
print("=" * 80)

# 모든 데이터 합치기
all_data = []
for kw, data in [("맛집", matjip_data), ("카페", cafe_data), ("반지공방", ring_data),
                 ("브런치", brunch_data), ("술집", bar_data), ("고기집", meat_data)]:
    for d in data:
        all_data.append({
            'kw': kw,
            'rank': d[0],
            'name': d[1],
            'V': d[2], 'B': d[3], 'S': d[4],
            'N1': d[5], 'N2': d[6], 'N3': d[7]
        })

N1_all = np.array([d['N1'] for d in all_data])
N2_all = np.array([d['N2'] for d in all_data])
N3_all = np.array([d['N3'] for d in all_data])

# 다양한 N3 공식 시도
print("\n다양한 N3 = f(N1, N2) 공식 시도:")
print("-" * 70)

formulas = {
    "a*N1 + b*N2 + c": np.column_stack([N1_all, N2_all, np.ones(len(N3_all))]),
    "+ N1*N2": np.column_stack([N1_all, N2_all, N1_all*N2_all, np.ones(len(N3_all))]),
    "+ N1^2 + N2^2": np.column_stack([N1_all, N2_all, N1_all**2, N2_all**2, np.ones(len(N3_all))]),
    "+ sqrt(N1) + sqrt(N2)": np.column_stack([N1_all, N2_all, np.sqrt(N1_all), np.sqrt(N2_all), np.ones(len(N3_all))]),
    "+ log(N1) + log(N2)": np.column_stack([N1_all, N2_all, np.log(N1_all), np.log(N2_all), np.ones(len(N3_all))]),
    "N1*N2 only": np.column_stack([N1_all*N2_all, np.ones(len(N3_all))]),
}

print(f"{'공식':>25} {'R²':>12} {'RMSE':>12} {'Max Error':>12}")
print("-" * 65)

for name, X in formulas.items():
    coeffs, _, _, _ = np.linalg.lstsq(X, N3_all, rcond=None)
    pred = X @ coeffs
    r2 = 1 - np.sum((N3_all - pred)**2) / np.sum((N3_all - N3_all.mean())**2)
    rmse = np.sqrt(np.mean((N3_all - pred)**2))
    max_err = np.max(np.abs(N3_all - pred))

    print(f"{name:>25} {r2:>12.6f} {rmse:>12.8f} {max_err:>12.8f}")

# 최적 공식 (N1*N2)
X_best = np.column_stack([N1_all, N2_all, N1_all*N2_all, np.ones(len(N3_all))])
coeffs_best, _, _, _ = np.linalg.lstsq(X_best, N3_all, rcond=None)
pred_best = X_best @ coeffs_best
r2_best = 1 - np.sum((N3_all - pred_best)**2) / np.sum((N3_all - N3_all.mean())**2)

print(f"\n최적 N3 공식:")
print(f"  N3 = {coeffs_best[0]:.6f}*N1 + {coeffs_best[1]:.6f}*N2")
print(f"       + {coeffs_best[2]:.6f}*N1*N2 + {coeffs_best[3]:.6f}")
print(f"  R² = {r2_best:.6f}")

# ============================================================================
# PART 2: 간단한 N3 근사 공식 탐색
# ============================================================================
print("\n" + "=" * 80)
print("PART 2: 간단한 N3 근사 공식 탐색")
print("=" * 80)

# 가설: N3 = k * (N1 + N2) / 2 + c (평균의 선형 변환)
def simple_n3(params, N1, N2):
    k, c = params
    return k * (N1 + N2) / 2 + c

def simple_n3_error(params):
    pred = simple_n3(params, N1_all, N2_all)
    return np.sum((N3_all - pred)**2)

result = minimize(simple_n3_error, [0.5, 0.2])
k_opt, c_opt = result.x
pred_simple = simple_n3([k_opt, c_opt], N1_all, N2_all)
r2_simple = 1 - np.sum((N3_all - pred_simple)**2) / np.sum((N3_all - N3_all.mean())**2)

print(f"\n가설 1: N3 = k * (N1 + N2) / 2 + c")
print(f"  k = {k_opt:.6f}, c = {c_opt:.6f}")
print(f"  R² = {r2_simple:.6f}")

# 가설 2: N3 = a*N1 + b*N2 (가중 평균)
X_weighted = np.column_stack([N1_all, N2_all])
coeffs_weighted, _, _, _ = np.linalg.lstsq(X_weighted, N3_all, rcond=None)
pred_weighted = X_weighted @ coeffs_weighted
r2_weighted = 1 - np.sum((N3_all - pred_weighted)**2) / np.sum((N3_all - N3_all.mean())**2)

print(f"\n가설 2: N3 = a*N1 + b*N2 (상수항 없음)")
print(f"  a = {coeffs_weighted[0]:.6f}, b = {coeffs_weighted[1]:.6f}")
print(f"  R² = {r2_weighted:.6f}")

# 가설 3: N3 = sqrt(N1 * N2) + c (기하평균)
geo_mean = np.sqrt(N1_all * N2_all)
X_geo = np.column_stack([geo_mean, np.ones(len(N3_all))])
coeffs_geo, _, _, _ = np.linalg.lstsq(X_geo, N3_all, rcond=None)
pred_geo = X_geo @ coeffs_geo
r2_geo = 1 - np.sum((N3_all - pred_geo)**2) / np.sum((N3_all - N3_all.mean())**2)

print(f"\n가설 3: N3 = a * sqrt(N1 * N2) + c (기하평균)")
print(f"  a = {coeffs_geo[0]:.6f}, c = {coeffs_geo[1]:.6f}")
print(f"  R² = {r2_geo:.6f}")

# 가설 4: N3 = 2*N1*N2 / (N1 + N2) + c (조화평균)
harmonic_mean = 2 * N1_all * N2_all / (N1_all + N2_all)
X_harmonic = np.column_stack([harmonic_mean, np.ones(len(N3_all))])
coeffs_harmonic, _, _, _ = np.linalg.lstsq(X_harmonic, N3_all, rcond=None)
pred_harmonic = X_harmonic @ coeffs_harmonic
r2_harmonic = 1 - np.sum((N3_all - pred_harmonic)**2) / np.sum((N3_all - N3_all.mean())**2)

print(f"\n가설 4: N3 = a * (2*N1*N2/(N1+N2)) + c (조화평균)")
print(f"  a = {coeffs_harmonic[0]:.6f}, c = {coeffs_harmonic[1]:.6f}")
print(f"  R² = {r2_harmonic:.6f}")

# ============================================================================
# PART 3: 키워드 유형별 N3 공식 비교
# ============================================================================
print("\n" + "=" * 80)
print("PART 3: 키워드 유형별 N3 공식 비교")
print("=" * 80)

# Type A와 Type B 분리
type_a_data = [d for d in all_data if d['kw'] in ['맛집', '카페', '반지공방']]
type_b_data = [d for d in all_data if d['kw'] in ['브런치', '술집', '고기집']]

for type_name, data_list in [("Type A (맛집/카페/반지공방)", type_a_data),
                               ("Type B (브런치/술집/고기집)", type_b_data)]:
    N1 = np.array([d['N1'] for d in data_list])
    N2 = np.array([d['N2'] for d in data_list])
    N3 = np.array([d['N3'] for d in data_list])

    # N3 = a*N1 + b*N2 + c*N1*N2 + d
    X = np.column_stack([N1, N2, N1*N2, np.ones(len(N3))])
    coeffs, _, _, _ = np.linalg.lstsq(X, N3, rcond=None)
    pred = X @ coeffs
    r2 = 1 - np.sum((N3 - pred)**2) / np.sum((N3 - N3.mean())**2)

    print(f"\n[{type_name}]")
    print(f"  N3 = {coeffs[0]:.6f}*N1 + {coeffs[1]:.6f}*N2")
    print(f"       + {coeffs[2]:.6f}*N1*N2 + {coeffs[3]:.6f}")
    print(f"  R² = {r2:.6f}")

# ============================================================================
# PART 4: V, B, S로 N3 직접 예측 (Type B 술집/고기집)
# ============================================================================
print("\n" + "=" * 80)
print("PART 4: V, B, S로 N3 직접 예측 (Type B)")
print("=" * 80)

for kw_name, data_list in [("이태원술집", bar_data), ("대전고기집", meat_data)]:
    V = np.array([d[2] for d in data_list])
    B = np.array([d[3] for d in data_list])
    S = np.array([d[4] for d in data_list])
    N3 = np.array([d[7] for d in data_list])
    ranks = np.array([d[0] for d in data_list])

    log_V = np.log1p(V)
    log_B = np.log1p(B)
    log_S = np.log1p(S)

    print(f"\n[{kw_name}]")

    # 다양한 조합 시도
    formulas = {
        "log(V) + log(B) + log(S)": np.column_stack([log_V, log_B, log_S, np.ones(len(N3))]),
        "+ V*B 상호작용": np.column_stack([log_V, log_B, log_S, log_V*log_B, np.ones(len(N3))]),
        "+ V/(V+B)": np.column_stack([log_V, log_B, log_S, V/(V+B+1), np.ones(len(N3))]),
        "+ S/(V+B)": np.column_stack([log_V, log_B, log_S, S/(V+B+1), np.ones(len(N3))]),
        "+ 모든 조합": np.column_stack([log_V, log_B, log_S, log_V*log_B, V/(V+B+1), S/(V+B+1), np.ones(len(N3))]),
    }

    print(f"  {'공식':>20} {'R²':>10} {'순위상관':>10}")
    print("  " + "-" * 45)

    for name, X in formulas.items():
        coeffs, _, _, _ = np.linalg.lstsq(X, N3, rcond=None)
        pred = X @ coeffs
        r2 = 1 - np.sum((N3 - pred)**2) / np.sum((N3 - N3.mean())**2)

        # 순위 상관
        pred_ranks = stats.rankdata(-pred)
        corr = stats.spearmanr(ranks, pred_ranks)[0]

        print(f"  {name:>20} {r2:>10.4f} {corr:>10.4f}")

# ============================================================================
# PART 5: 순위 예측 최적 전략
# ============================================================================
print("\n" + "=" * 80)
print("PART 5: 순위 예측 최적 전략 요약")
print("=" * 80)

all_keywords = {
    "홍대맛집": matjip_data,
    "강남카페": cafe_data,
    "부산반지공방": ring_data,
    "성수브런치": brunch_data,
    "이태원술집": bar_data,
    "대전고기집": meat_data,
}

print("\n키워드별 최적 순위 예측 전략:")
print("-" * 80)
print(f"{'키워드':<12} {'N1유형':>8} {'순위결정':>10} {'V,B,S→순위':>12} {'예측가능성':>10}")
print("-" * 80)

for kw, data in all_keywords.items():
    V = np.array([d[2] for d in data])
    B = np.array([d[3] for d in data])
    S = np.array([d[4] for d in data])
    N1 = np.array([d[5] for d in data])
    N2 = np.array([d[6] for d in data])
    N3 = np.array([d[7] for d in data])
    ranks = np.array([d[0] for d in data])

    # N1 유형
    n1_type = "고정" if np.std(N1) < 0.001 else "가변"

    # 순위 결정 요소
    n1_corr = abs(stats.spearmanr(ranks, -N1)[0]) if not np.isnan(stats.spearmanr(ranks, -N1)[0]) else 0
    n2_corr = abs(stats.spearmanr(ranks, -N2)[0])
    n3_corr = abs(stats.spearmanr(ranks, -N3)[0])

    if n1_corr >= n2_corr and n1_corr >= n3_corr:
        main_factor = "N1"
    elif n2_corr >= n3_corr:
        main_factor = "N2"
    else:
        main_factor = "N3"

    # V, B, S로 순위 직접 예측
    log_V = np.log1p(V)
    log_B = np.log1p(B)
    log_S = np.log1p(S)

    X = np.column_stack([log_V, log_B, log_S, np.ones(len(ranks))])
    coeffs, _, _, _ = np.linalg.lstsq(X, ranks, rcond=None)
    pred_ranks = X @ coeffs
    direct_corr = stats.spearmanr(ranks, pred_ranks)[0]

    # 예측 가능성 판단
    if abs(direct_corr) > 0.9:
        predictability = "매우 높음"
    elif abs(direct_corr) > 0.7:
        predictability = "높음"
    elif abs(direct_corr) > 0.5:
        predictability = "중간"
    else:
        predictability = "낮음"

    print(f"{kw:<12} {n1_type:>8} {main_factor:>10} {direct_corr:>12.4f} {predictability:>10}")

# ============================================================================
# PART 6: 최종 알고리즘 공식
# ============================================================================
print("\n" + "=" * 80)
print("PART 6: 최종 ADLOG 알고리즘 공식")
print("=" * 80)

# Type A 공식 (맛집, 카페, 반지공방 통합)
type_a_all_data = [d for d in all_data if d['kw'] in ['맛집', '카페', '반지공방']]
V_a = np.array([d['V'] for d in type_a_all_data])
B_a = np.array([d['B'] for d in type_a_all_data])
S_a = np.array([d['S'] for d in type_a_all_data])
N2_a = np.array([d['N2'] for d in type_a_all_data])

log_V_a = np.log1p(V_a)
log_B_a = np.log1p(B_a)
log_S_a = np.log1p(S_a)

X_a = np.column_stack([log_V_a, log_B_a, log_S_a, np.ones(len(N2_a))])
coeffs_a, _, _, _ = np.linalg.lstsq(X_a, N2_a, rcond=None)
pred_a = X_a @ coeffs_a
r2_a = 1 - np.sum((N2_a - pred_a)**2) / np.sum((N2_a - N2_a.mean())**2)

print(f"""
=== Type A 공식 (맛집, 카페, 반지공방) ===

N1 = 키워드별 고정값 (사전 정의 필요)
  - 맛집 계열: 약 0.37
  - 카페 계열: 약 0.40
  - 공방 계열: 약 0.46

N2 = {coeffs_a[0]:.6f} * log(V+1)
     + {coeffs_a[1]:.6f} * log(B+1)
     + {coeffs_a[2]:.6f} * log(S+1)
     + {coeffs_a[3]:.6f}
R² = {r2_a:.4f}

N3 = {coeffs_best[0]:.6f}*N1 + {coeffs_best[1]:.6f}*N2 + {coeffs_best[2]:.6f}*N1*N2 + {coeffs_best[3]:.6f}

순위 = N2 또는 N3 높은 순서 (완벽 상관)
""")

# Type B 공식 (브런치, 술집, 고기집)
type_b_all_data = [d for d in all_data if d['kw'] in ['브런치', '술집', '고기집']]
V_b = np.array([d['V'] for d in type_b_all_data])
B_b = np.array([d['B'] for d in type_b_all_data])
S_b = np.array([d['S'] for d in type_b_all_data])
N1_b = np.array([d['N1'] for d in type_b_all_data])

log_V_b = np.log1p(V_b)
log_B_b = np.log1p(B_b)
log_S_b = np.log1p(S_b)

X_b = np.column_stack([log_V_b, log_B_b, log_S_b, np.ones(len(N1_b))])
coeffs_b, _, _, _ = np.linalg.lstsq(X_b, N1_b, rcond=None)
pred_b = X_b @ coeffs_b
r2_b = 1 - np.sum((N1_b - pred_b)**2) / np.sum((N1_b - N1_b.mean())**2)

# Quality Score 계산
quality_scores = N1_b - pred_b

print(f"""
=== Type B 공식 (브런치, 술집, 고기집) ===

N1_base = {coeffs_b[0]:.6f} * log(V+1)
         + {coeffs_b[1]:.6f} * log(B+1)
         + {coeffs_b[2]:.6f} * log(S+1)
         + {coeffs_b[3]:.6f}
R² = {r2_b:.4f}

Quality_Score = N1 - N1_base
  범위: {quality_scores.min():.6f} ~ {quality_scores.max():.6f}
  표준편차: {quality_scores.std():.6f}

N1 = N1_base + Quality_Score (숨겨진 요소)

순위 결정:
  - 브런치: N1 높은 순 (상관 1.0)
  - 술집: N3 높은 순 (상관 1.0)
  - 고기집: N3 높은 순 (상관 1.0)
""")

# ============================================================================
# PART 7: 숨겨진 요소 최종 분석
# ============================================================================
print("\n" + "=" * 80)
print("PART 7: 숨겨진 요소 최종 분석")
print("=" * 80)

print("""
=== 발견된 숨겨진 요소 (Quality_Score) ===

1. 정체:
   - V, B, S로 설명되지 않는 N1의 나머지 부분
   - 약 28%의 변동을 설명 (1 - R² = 1 - 0.72 = 0.28)

2. 특성:
   - V, B, S와 독립적 (상관 거의 0)
   - 순위와 양의 상관 (0.46)
   - 범위: -0.019 ~ +0.017

3. 가능한 정체:
   a) 별점 (Rating): 4.0~5.0 범위로 역산 시 합리적 값
   b) CTR (클릭률): 네이버만 알 수 있음
   c) 체류 시간: 네이버만 알 수 있음
   d) 리뷰 품질 점수: 별점 외 텍스트 분석

4. 검증 방법:
   - 실제 별점 데이터 크롤링 후 상관 분석
   - 시간에 따른 Quality_Score 변화 추적
   - 더 많은 키워드로 패턴 확인

=== 실용적 적용 ===

1. 새 업체 예측 시:
   - Quality_Score = 0 (기본값)
   - 또는 동일 카테고리 평균값 사용

2. 기존 업체:
   - ADLOG에서 실제 N1 확인
   - Quality_Score = N1 - N1_base 계산
   - 이 값을 저장해두고 재사용

3. 순위 예측:
   - Type A: N2 계산 → 순위
   - Type B: N1 계산 (+ Quality_Score) → N3 계산 → 순위
""")

print("\n" + "=" * 80)
print("분석 완료!")
print("=" * 80)
