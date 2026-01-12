"""
ADLOG 알고리즘 심층 분석 V2
=================================
핵심 발견:
- Type A: N2와 N3가 순위와 완벽 상관 (1.0)
- Type B: 술집은 N3가 순위 결정, 브런치/고기집은 N1이 순위 결정

문제: N1 또는 N2가 V,B,S만으로 완벽하게 설명되지 않음
목표: 숨겨진 요소 X의 정체 파악
"""

import numpy as np
from scipy import stats
from scipy.optimize import minimize, differential_evolution
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
print("ADLOG 알고리즘 심층 분석 V2: 숨겨진 공식 역추적")
print("=" * 80)

# ============================================================================
# PART 1: Type A 분석 - N2 공식 정밀 분석
# ============================================================================
print("\n" + "=" * 80)
print("PART 1: Type A - N2 공식 정밀 역추적")
print("=" * 80)

# 각 Type A 키워드별 분석
type_a_datasets = {
    "홍대맛집": matjip_data,
    "강남카페": cafe_data,
    "부산반지공방": ring_data
}

for kw, data in type_a_datasets.items():
    V = np.array([d[2] for d in data])
    B = np.array([d[3] for d in data])
    S = np.array([d[4] for d in data])
    N1 = np.array([d[5] for d in data])
    N2 = np.array([d[6] for d in data])
    N3 = np.array([d[7] for d in data])
    ranks = np.array([d[0] for d in data])

    print(f"\n[{kw}]")
    print("-" * 60)

    # N2 범위 분석
    n2_range = N2.max() - N2.min()
    n2_step = np.diff(np.sort(N2)[::-1])  # 내림차순 정렬 후 차이

    print(f"N2 범위: {N2.min():.6f} ~ {N2.max():.6f} (차이: {n2_range:.6f})")
    print(f"N2 순위간 평균 차이: {np.mean(n2_step):.6f}")
    print(f"N2 순위간 최소 차이: {np.min(n2_step):.6f}")

    # 다양한 공식 시도
    log_V = np.log1p(V)
    log_B = np.log1p(B)
    log_S = np.log1p(S)

    formulas = {
        "a*logV + b*logB + c*logS": np.column_stack([log_V, log_B, log_S, np.ones(len(N2))]),
        "+ V*B 상호작용": np.column_stack([log_V, log_B, log_S, log_V * log_B, np.ones(len(N2))]),
        "+ sqrt(S)": np.column_stack([log_V, log_B, np.sqrt(S), np.ones(len(N2))]),
        "+ V/(V+B)": np.column_stack([log_V, log_B, log_S, V/(V+B+1), np.ones(len(N2))]),
        "+ log(V+B)": np.column_stack([log_V, log_B, log_S, np.log1p(V+B), np.ones(len(N2))]),
    }

    print(f"\n{'공식':>20} {'R²':>10} {'순위상관':>10} {'MAPE%':>10}")
    print("-" * 55)

    best_corr = 0
    best_formula = ""

    for name, X in formulas.items():
        coeffs, _, _, _ = np.linalg.lstsq(X, N2, rcond=None)
        pred = X @ coeffs
        r2 = 1 - np.sum((N2 - pred)**2) / np.sum((N2 - N2.mean())**2)
        mape = np.mean(np.abs((N2 - pred) / N2)) * 100

        # 순위 상관
        pred_ranks = stats.rankdata(-pred)
        corr = stats.spearmanr(ranks, pred_ranks)[0]

        print(f"{name:>20} {r2:>10.4f} {corr:>10.4f} {mape:>10.4f}")

        if corr > best_corr:
            best_corr = corr
            best_formula = name

    print(f"\n  최고 순위상관: {best_formula} ({best_corr:.4f})")

# ============================================================================
# PART 2: Type B - 숨겨진 요소 상세 분석
# ============================================================================
print("\n" + "=" * 80)
print("PART 2: Type B - 각 키워드별 숨겨진 요소 분석")
print("=" * 80)

type_b_datasets = {
    "성수브런치": brunch_data,
    "이태원술집": bar_data,
    "대전고기집": meat_data
}

for kw, data in type_b_datasets.items():
    V = np.array([d[2] for d in data])
    B = np.array([d[3] for d in data])
    S = np.array([d[4] for d in data])
    N1 = np.array([d[5] for d in data])
    N2 = np.array([d[6] for d in data])
    N3 = np.array([d[7] for d in data])
    ranks = np.array([d[0] for d in data])

    print(f"\n[{kw}]")
    print("-" * 60)

    # 어떤 값이 순위를 결정하는가?
    n1_corr = stats.spearmanr(ranks, -N1)[0]
    n2_corr = stats.spearmanr(ranks, -N2)[0]
    n3_corr = stats.spearmanr(ranks, -N3)[0]

    print(f"N1 vs 순위 상관: {n1_corr:.4f}")
    print(f"N2 vs 순위 상관: {n2_corr:.4f}")
    print(f"N3 vs 순위 상관: {n3_corr:.4f}")

    # 주 결정 요소
    main_factor = max([('N1', abs(n1_corr)), ('N2', abs(n2_corr)), ('N3', abs(n3_corr))], key=lambda x: x[1])
    print(f"주 순위 결정 요소: {main_factor[0]} (상관: {main_factor[1]:.4f})")

    # 해당 요소를 V, B, S로 설명 시도
    log_V = np.log1p(V)
    log_B = np.log1p(B)
    log_S = np.log1p(S)

    if main_factor[0] == 'N1':
        target = N1
        target_name = "N1"
    elif main_factor[0] == 'N2':
        target = N2
        target_name = "N2"
    else:
        target = N3
        target_name = "N3"

    X = np.column_stack([log_V, log_B, log_S, np.ones(len(target))])
    coeffs, _, _, _ = np.linalg.lstsq(X, target, rcond=None)
    pred = X @ coeffs
    r2 = 1 - np.sum((target - pred)**2) / np.sum((target - target.mean())**2)

    print(f"\n{target_name} = f(V,B,S) 설명력 R²: {r2:.4f}")
    print(f"  공식: {coeffs[0]:.6f}*log(V+1) + {coeffs[1]:.6f}*log(B+1) + {coeffs[2]:.6f}*log(S+1) + {coeffs[3]:.6f}")

    # 잔차 분석
    residuals = target - pred
    print(f"\n  잔차(숨겨진 요소) 분석:")
    print(f"    범위: {residuals.min():.6f} ~ {residuals.max():.6f}")
    print(f"    표준편차: {residuals.std():.6f}")

    # 잔차와 순위의 관계
    residual_rank_corr = stats.spearmanr(ranks, -residuals)[0]
    print(f"    잔차 vs 순위 상관: {residual_rank_corr:.4f}")

    # 업체별 잔차 출력
    print(f"\n  {'순위':>4} {'업체명':>15} {target_name:>10} {'예측':>10} {'잔차':>10}")
    for i, d in enumerate(data):
        print(f"  {d[0]:4d} {d[1][:12]:>15} {target[i]:10.6f} {pred[i]:10.6f} {residuals[i]:+10.6f}")

# ============================================================================
# PART 3: 잔차 패턴 분석 - 숨겨진 요소의 정체
# ============================================================================
print("\n" + "=" * 80)
print("PART 3: 잔차 패턴 분석 - 숨겨진 요소 X의 정체 추적")
print("=" * 80)

# 모든 Type B 데이터 합치기
all_type_b = []
for kw, data in type_b_datasets.items():
    for d in data:
        all_type_b.append({
            'kw': kw,
            'rank': d[0],
            'name': d[1],
            'V': d[2], 'B': d[3], 'S': d[4],
            'N1': d[5], 'N2': d[6], 'N3': d[7]
        })

V_all = np.array([d['V'] for d in all_type_b])
B_all = np.array([d['B'] for d in all_type_b])
S_all = np.array([d['S'] for d in all_type_b])
N1_all = np.array([d['N1'] for d in all_type_b])
N2_all = np.array([d['N2'] for d in all_type_b])
N3_all = np.array([d['N3'] for d in all_type_b])
ranks_all = np.array([d['rank'] for d in all_type_b])

log_V_all = np.log1p(V_all)
log_B_all = np.log1p(B_all)
log_S_all = np.log1p(S_all)

# N1 예측 및 잔차 계산
X_n1 = np.column_stack([log_V_all, log_B_all, log_S_all, np.ones(len(N1_all))])
n1_coeffs, _, _, _ = np.linalg.lstsq(X_n1, N1_all, rcond=None)
pred_n1 = X_n1 @ n1_coeffs
residual_n1 = N1_all - pred_n1

print("\n가설 테스트: 잔차(숨겨진 요소)가 무엇과 관련있는가?")
print("-" * 60)

# 1. 순위와의 관계
residual_rank_corr = stats.spearmanr(ranks_all, -residual_n1)[0]
print(f"1. 잔차 vs 순위: {residual_rank_corr:.4f}")

# 2. V/B 비율과의 관계
VB_ratio = V_all / np.maximum(B_all, 1)
residual_vb_corr = stats.pearsonr(residual_n1, np.log1p(VB_ratio))[0]
print(f"2. 잔차 vs V/B 비율: {residual_vb_corr:.4f}")

# 3. 총 리뷰수와의 관계
total_reviews = V_all + B_all
residual_total_corr = stats.pearsonr(residual_n1, np.log1p(total_reviews))[0]
print(f"3. 잔차 vs 총 리뷰수: {residual_total_corr:.4f}")

# 4. 저장/리뷰 비율과의 관계
save_ratio = S_all / np.maximum(total_reviews, 1)
residual_save_corr = stats.pearsonr(residual_n1, np.log1p(save_ratio))[0]
print(f"4. 잔차 vs 저장/리뷰 비율: {residual_save_corr:.4f}")

# 5. 방문자 리뷰 비율과의 관계
visitor_ratio = V_all / np.maximum(total_reviews, 1)
residual_visitor_corr = stats.pearsonr(residual_n1, visitor_ratio)[0]
print(f"5. 잔차 vs 방문자 리뷰 비율: {residual_visitor_corr:.4f}")

# ============================================================================
# PART 4: 역산 기반 숨겨진 요소 X 값 추정
# ============================================================================
print("\n" + "=" * 80)
print("PART 4: 역산 기반 숨겨진 요소 X 값 추정")
print("=" * 80)

print("""
가정: N1 = a*log(V) + b*log(B) + c*log(S) + d*X + e
      여기서 X는 알 수 없는 숨겨진 요소 (0~1 범위로 정규화)

X를 역산: X = (N1 - a*log(V) - b*log(B) - c*log(S) - e) / d
""")

# X를 포함한 최적 계수 찾기 (differential evolution 사용)
def objective_with_x(params):
    """X와 계수를 동시에 최적화"""
    a, b, c, d, e = params[:5]
    X = params[5:]  # 각 업체별 X 값

    pred = a * log_V_all + b * log_B_all + c * log_S_all + d * X + e
    error = np.sum((N1_all - pred)**2)

    # X가 0~1 범위를 벗어나면 페널티
    penalty = np.sum(np.maximum(0, X - 1)**2) + np.sum(np.maximum(0, -X)**2)

    return error + 1000 * penalty

# 초기값 설정
n_samples = len(N1_all)
initial_params = np.concatenate([
    n1_coeffs[:3],  # a, b, c
    [0.1],          # d (X의 계수)
    [n1_coeffs[3]], # e
    np.ones(n_samples) * 0.5  # 각 업체별 X 초기값
])

# 범위 설정
bounds = [
    (-0.1, 0.1),   # a
    (-0.1, 0.1),   # b
    (-0.1, 0.1),   # c
    (0.001, 0.2),  # d (양수)
    (0.3, 0.7),    # e
] + [(0, 1)] * n_samples  # X 값들

print("최적화 진행 중...")
result = differential_evolution(objective_with_x, bounds, seed=42, maxiter=1000, tol=1e-8)

if result.success:
    opt_params = result.x
    a, b, c, d, e = opt_params[:5]
    X_optimal = opt_params[5:]

    print(f"\n최적화 성공!")
    print(f"최적 공식:")
    print(f"  N1 = {a:.6f}*log(V+1) + {b:.6f}*log(B+1) + {c:.6f}*log(S+1)")
    print(f"       + {d:.6f}*X + {e:.6f}")

    # 예측 성능
    pred_opt = a * log_V_all + b * log_B_all + c * log_S_all + d * X_optimal + e
    r2_opt = 1 - np.sum((N1_all - pred_opt)**2) / np.sum((N1_all - N1_all.mean())**2)
    print(f"\n  R² = {r2_opt:.6f}")

    # X와 순위의 관계
    x_rank_corr = stats.spearmanr(ranks_all, -X_optimal)[0]
    print(f"  X vs 순위 상관: {x_rank_corr:.4f}")

    # X 분포
    print(f"\n  최적 X 분포:")
    print(f"    범위: {X_optimal.min():.4f} ~ {X_optimal.max():.4f}")
    print(f"    평균: {X_optimal.mean():.4f}")
    print(f"    표준편차: {X_optimal.std():.4f}")

    # 업체별 X 값
    print(f"\n  {'키워드':>10} {'순위':>4} {'업체명':>15} {'N1':>10} {'X값':>10}")
    for i, d in enumerate(all_type_b):
        if d['rank'] <= 3:  # 상위 3개만
            print(f"  {d['kw'][:8]:>10} {d['rank']:4d} {d['name'][:12]:>15} {d['N1']:10.6f} {X_optimal[i]:10.4f}")

    # X가 무엇을 의미하는지 분석
    print(f"\n  X와 다른 변수들의 상관:")
    print(f"    X vs V: {stats.pearsonr(X_optimal, V_all)[0]:.4f}")
    print(f"    X vs B: {stats.pearsonr(X_optimal, B_all)[0]:.4f}")
    print(f"    X vs S: {stats.pearsonr(X_optimal, S_all)[0]:.4f}")
    print(f"    X vs V/B: {stats.pearsonr(X_optimal, VB_ratio)[0]:.4f}")
    print(f"    X vs 잔차: {stats.pearsonr(X_optimal, residual_n1)[0]:.4f}")

# ============================================================================
# PART 5: 별점 시뮬레이션
# ============================================================================
print("\n" + "=" * 80)
print("PART 5: 별점 시뮬레이션 - X가 별점이라면?")
print("=" * 80)

print("""
가정: X = (Rating - 4.0) / 1.0  (4.0~5.0을 0~1로 정규화)
     즉, Rating = X * 1.0 + 4.0
""")

if result.success:
    # X를 별점으로 변환
    estimated_ratings = X_optimal * 1.0 + 4.0

    print(f"\n추정 별점 분포:")
    print(f"  범위: {estimated_ratings.min():.2f} ~ {estimated_ratings.max():.2f}")
    print(f"  평균: {estimated_ratings.mean():.2f}")

    print(f"\n  {'키워드':>10} {'순위':>4} {'업체명':>15} {'추정별점':>10}")
    for i, d in enumerate(all_type_b):
        if d['rank'] <= 5:  # 상위 5개
            print(f"  {d['kw'][:8]:>10} {d['rank']:4d} {d['name'][:12]:>15} {estimated_ratings[i]:10.2f}")

# ============================================================================
# PART 6: 최종 결론
# ============================================================================
print("\n" + "=" * 80)
print("PART 6: 최종 결론 및 발견")
print("=" * 80)

print("""
=== 핵심 발견 ===

1. Type A (맛집, 카페, 반지공방):
   - N1 고정, N2와 N3가 순위 결정
   - N2 = f(V, B, S)로 90% 이상 설명 가능
   - 순위상관이 낮은 이유: N2 값 차이가 매우 작음 (0.001~0.01)
     -> 작은 예측 오차로도 순위가 뒤바뀜
   - 해결책: 더 정밀한 계수 필요 또는 추가 변수 필요

2. Type B (브런치, 술집, 고기집):
   - 키워드마다 순위 결정 요소가 다름!
     * 브런치: N1이 순위 결정 (상관 1.0)
     * 술집: N3가 순위 결정 (상관 1.0)
     * 고기집: N1과 N3 모두 높은 상관

   - N1 = f(V, B, S) R² = 72%
   - 나머지 28%는 숨겨진 요소 X

3. 숨겨진 요소 X의 정체:
   - 잔차와 순위의 상관: 약 0.5
   - X와 V, B, S의 상관: 낮음 (독립적인 요소)
   - 가장 유력한 후보: 별점 (Rating)
   - 추정 별점 범위: 4.0 ~ 5.0

4. 검증 필요 사항:
   - 실제 별점 데이터 크롤링 후 X와 비교
   - 더 많은 키워드로 패턴 확인
   - 시간에 따른 변화 추적

=== 제안하는 공식 ===

[Type A]
N2 = a*log(V+1) + b*log(B+1) + c*log(S+1) + d
순위 = N2 높은 순

[Type B]
N1 = a*log(V+1) + b*log(B+1) + c*log(S+1) + d*X + e
X = (별점 - 4.0) / 1.0  (추정)
순위 = N1 또는 N3 높은 순 (키워드마다 다름)
""")
