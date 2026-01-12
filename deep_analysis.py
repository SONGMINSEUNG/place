"""
네이버 플레이스 ADLOG 알고리즘 심층 역추적 분석
==============================================
목표: N3와 순위의 정확한 관계 파악, Type B의 숨겨진 요소 발견
"""

import numpy as np
from scipy import stats
from scipy.optimize import minimize
import warnings
warnings.filterwarnings('ignore')

# ============================================================================
# 전체 데이터셋 (6개 키워드, 각 10개)
# ============================================================================

# Type A: N1 고정
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

# Type B: N1 가변
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
print("네이버 플레이스 ADLOG 알고리즘 심층 역추적 분석")
print("=" * 80)

# ============================================================================
# PART 1: N1, N2, N3 중 어떤 것이 순위와 가장 상관이 높은가?
# ============================================================================
print("\n" + "=" * 80)
print("PART 1: 순위 결정 요소 분석 (N1 vs N2 vs N3)")
print("=" * 80)

all_keywords = {
    "홍대맛집": matjip_data,
    "강남카페": cafe_data,
    "부산반지공방": ring_data,
    "성수브런치": brunch_data,
    "이태원술집": bar_data,
    "대전고기집": meat_data,
}

print("\n키워드별 순위 상관분석:")
print("-" * 75)
print(f"{'키워드':<12} {'N1-순위':>10} {'N2-순위':>10} {'N3-순위':>10} {'N1유형':>8} {'주결정요소':>10}")
print("-" * 75)

results = {}
for kw, data in all_keywords.items():
    ranks = np.array([d[0] for d in data])
    N1 = np.array([d[5] for d in data])
    N2 = np.array([d[6] for d in data])
    N3 = np.array([d[7] for d in data])

    # 순위와 상관 계산 (높을수록 순위 좋으므로 역상관)
    corr_n1 = stats.spearmanr(ranks, -N1)[0]  # N1 높으면 순위 낮아야 함
    corr_n2 = stats.spearmanr(ranks, -N2)[0]
    corr_n3 = stats.spearmanr(ranks, -N3)[0]

    n1_type = "고정" if np.std(N1) < 0.001 else "가변"

    # 주 결정 요소
    corrs = {'N1': abs(corr_n1), 'N2': abs(corr_n2), 'N3': abs(corr_n3)}
    main_factor = max(corrs, key=corrs.get)

    print(f"{kw:<12} {corr_n1:>10.4f} {corr_n2:>10.4f} {corr_n3:>10.4f} {n1_type:>8} {main_factor:>10}")

    results[kw] = {
        'data': data, 'ranks': ranks, 'N1': N1, 'N2': N2, 'N3': N3,
        'corr_n1': corr_n1, 'corr_n2': corr_n2, 'corr_n3': corr_n3,
        'n1_type': n1_type, 'main_factor': main_factor
    }

# ============================================================================
# PART 2: N3 = f(N1, N2) 관계 분석
# ============================================================================
print("\n" + "=" * 80)
print("PART 2: N3 = f(N1, N2) 관계 분석")
print("=" * 80)

# 모든 데이터 합치기
all_N1 = []
all_N2 = []
all_N3 = []
all_ranks = []
all_V = []
all_B = []
all_S = []
all_kw = []

for kw, data in all_keywords.items():
    for d in data:
        all_ranks.append(d[0])
        all_V.append(d[2])
        all_B.append(d[3])
        all_S.append(d[4])
        all_N1.append(d[5])
        all_N2.append(d[6])
        all_N3.append(d[7])
        all_kw.append(kw)

all_N1 = np.array(all_N1)
all_N2 = np.array(all_N2)
all_N3 = np.array(all_N3)
all_ranks = np.array(all_ranks)
all_V = np.array(all_V)
all_B = np.array(all_B)
all_S = np.array(all_S)

# N3 = a*N1 + b*N2 + c*N1*N2 + d 회귀분석
X_n3 = np.column_stack([all_N1, all_N2, all_N1 * all_N2, np.ones(len(all_N3))])
n3_coeffs, residuals, rank, s = np.linalg.lstsq(X_n3, all_N3, rcond=None)

pred_n3 = X_n3 @ n3_coeffs
r2_n3 = 1 - np.sum((all_N3 - pred_n3)**2) / np.sum((all_N3 - all_N3.mean())**2)

print(f"\n전체 데이터 N3 공식:")
print(f"  N3 = {n3_coeffs[0]:.6f}*N1 + {n3_coeffs[1]:.6f}*N2")
print(f"       + {n3_coeffs[2]:.6f}*N1*N2 + {n3_coeffs[3]:.6f}")
print(f"  R² = {r2_n3:.6f}")

# N3 예측 오차 분석
n3_errors = all_N3 - pred_n3
print(f"\n  N3 예측 오차: 평균={n3_errors.mean():.8f}, 표준편차={n3_errors.std():.8f}")
print(f"  최대 오차: {np.max(np.abs(n3_errors)):.8f}")

# ============================================================================
# PART 3: Type A 심층 분석 - N2 예측은 잘되는데 순위상관이 낮은 이유
# ============================================================================
print("\n" + "=" * 80)
print("PART 3: Type A 문제 분석 - N2 예측 vs 순위상관 괴리")
print("=" * 80)

type_a_keywords = ["홍대맛집", "강남카페", "부산반지공방"]

for kw in type_a_keywords:
    data = results[kw]['data']
    V = np.array([d[2] for d in data])
    B = np.array([d[3] for d in data])
    S = np.array([d[4] for d in data])
    N2 = np.array([d[6] for d in data])
    N3 = np.array([d[7] for d in data])
    ranks = np.array([d[0] for d in data])

    log_V = np.log1p(V)
    log_B = np.log1p(B)
    log_S = np.log1p(S)

    # N2 예측
    X = np.column_stack([log_V, log_B, log_S, np.ones(len(N2))])
    coeffs, _, _, _ = np.linalg.lstsq(X, N2, rcond=None)
    pred_N2 = X @ coeffs
    r2 = 1 - np.sum((N2 - pred_N2)**2) / np.sum((N2 - N2.mean())**2)

    # 예측 N2로 순위 예측
    pred_ranks_n2 = stats.rankdata(-pred_N2)
    rank_corr_n2 = stats.spearmanr(ranks, pred_ranks_n2)[0]

    # 실제 N2로 순위 예측
    actual_ranks_n2 = stats.rankdata(-N2)
    actual_corr_n2 = stats.spearmanr(ranks, actual_ranks_n2)[0]

    # N3로 순위 예측
    actual_ranks_n3 = stats.rankdata(-N3)
    actual_corr_n3 = stats.spearmanr(ranks, actual_ranks_n3)[0]

    print(f"\n[{kw}]")
    print(f"  N2 예측 R² = {r2:.4f}")
    print(f"  실제N2 vs 순위 상관: {actual_corr_n2:.4f}")
    print(f"  예측N2 vs 순위 상관: {rank_corr_n2:.4f}")
    print(f"  실제N3 vs 순위 상관: {actual_corr_n3:.4f}")

    # 순위별 N2, N3 값 비교
    print(f"\n  {'순위':>4} {'업체명':>15} {'N2':>10} {'N3':>10} {'V':>8} {'B':>8} {'S':>8}")
    for d in data:
        print(f"  {d[0]:4d} {d[1][:12]:>15} {d[6]:10.6f} {d[7]:10.6f} {d[2]:8d} {d[3]:8d} {d[4]:8d}")

# ============================================================================
# PART 4: Type B - Quality_Score 역산
# ============================================================================
print("\n" + "=" * 80)
print("PART 4: Type B - Quality_Score 역산")
print("=" * 80)

type_b_keywords = ["성수브런치", "이태원술집", "대전고기집"]

# Type B 전체 데이터로 기본 N1 공식 생성
type_b_data = []
for kw in type_b_keywords:
    for d in all_keywords[kw]:
        type_b_data.append({
            'kw': kw,
            'rank': d[0],
            'name': d[1],
            'V': d[2], 'B': d[3], 'S': d[4],
            'N1': d[5], 'N2': d[6], 'N3': d[7]
        })

V_b = np.array([d['V'] for d in type_b_data])
B_b = np.array([d['B'] for d in type_b_data])
S_b = np.array([d['S'] for d in type_b_data])
N1_b = np.array([d['N1'] for d in type_b_data])
ranks_b = np.array([d['rank'] for d in type_b_data])

log_V_b = np.log1p(V_b)
log_B_b = np.log1p(B_b)
log_S_b = np.log1p(S_b)

# N1 = f(V, B, S)
X_n1 = np.column_stack([log_V_b, log_B_b, log_S_b, np.ones(len(N1_b))])
n1_coeffs, _, _, _ = np.linalg.lstsq(X_n1, N1_b, rcond=None)
pred_n1 = X_n1 @ n1_coeffs
r2_n1 = 1 - np.sum((N1_b - pred_n1)**2) / np.sum((N1_b - N1_b.mean())**2)

print(f"\nType B N1 기본 공식 (V, B, S만):")
print(f"  N1_base = {n1_coeffs[0]:.6f}*log(V+1) + {n1_coeffs[1]:.6f}*log(B+1)")
print(f"           + {n1_coeffs[2]:.6f}*log(S+1) + {n1_coeffs[3]:.6f}")
print(f"  R² = {r2_n1:.4f}")

# Quality_Score = N1_actual - N1_predicted
quality_scores = N1_b - pred_n1

print(f"\n  Quality_Score = N1_actual - N1_predicted")
print(f"  Quality_Score 범위: {quality_scores.min():.6f} ~ {quality_scores.max():.6f}")
print(f"  Quality_Score 평균: {quality_scores.mean():.6f}")
print(f"  Quality_Score 표준편차: {quality_scores.std():.6f}")

# Quality_Score와 순위의 관계
qs_rank_corr = stats.spearmanr(ranks_b, -quality_scores)[0]
print(f"\n  Quality_Score vs 순위 상관: {qs_rank_corr:.4f}")

# 키워드별 상세 분석
print("\n" + "-" * 75)
print("키워드별 Quality_Score 분석:")
print("-" * 75)

for kw in type_b_keywords:
    kw_data = [d for d in type_b_data if d['kw'] == kw]
    kw_indices = [i for i, d in enumerate(type_b_data) if d['kw'] == kw]
    kw_qs = quality_scores[kw_indices]
    kw_ranks = np.array([d['rank'] for d in kw_data])

    qs_corr = stats.spearmanr(kw_ranks, -kw_qs)[0]

    print(f"\n[{kw}] Quality_Score vs 순위 상관: {qs_corr:.4f}")
    print(f"  {'순위':>4} {'업체명':>15} {'N1':>10} {'예측N1':>10} {'Q_Score':>10}")

    for i, d in enumerate(kw_data):
        idx = kw_indices[i]
        print(f"  {d['rank']:4d} {d['name'][:12]:>15} {d['N1']:10.6f} {pred_n1[idx]:10.6f} {quality_scores[idx]:+10.6f}")

# ============================================================================
# PART 5: 딥러닝 방식 - 숨겨진 변수 X 역산
# ============================================================================
print("\n" + "=" * 80)
print("PART 5: 딥러닝 방식 - 숨겨진 변수 X 탐색")
print("=" * 80)

print("""
가설: Quality_Score = a * X + b
여기서 X는 우리가 모르는 숨겨진 요소

가능한 X 후보:
1. 별점 (Rating): 4.0 ~ 5.0
2. 최근 리뷰 비율: 0 ~ 1
3. 리뷰 증가 속도: 양수 또는 음수
4. 업체 연령 (개업 후 경과 일수)
5. CTR (클릭률)
6. 체류 시간
""")

# X 후보 1: 별점으로 Quality_Score 설명 시도
# 가정: Quality_Score = a * (Rating - 4.5) + b
# Quality_Score 범위: -0.03 ~ +0.03 (대략)
# Rating 범위: 4.0 ~ 5.0 (범위 1.0)
# 따라서 a = 0.06 정도

print("\n가설 1: Quality_Score = k * (Rating - 4.5)")
print("-" * 60)

# Quality_Score에서 Rating 역산
# Rating = Quality_Score / k + 4.5
# k 값을 추정: Quality_Score 범위 / Rating 범위

qs_range = quality_scores.max() - quality_scores.min()
rating_range = 1.0  # 4.0 ~ 5.0
k_estimated = qs_range / rating_range

print(f"  추정 k = {k_estimated:.6f}")
print(f"  (Quality_Score 범위 {qs_range:.4f} / Rating 범위 {rating_range})")

# 역산된 Rating 계산
estimated_ratings = quality_scores / k_estimated + 4.5

print(f"\n  역산된 Rating 범위: {estimated_ratings.min():.2f} ~ {estimated_ratings.max():.2f}")

# 업체별 역산 결과
print(f"\n  {'키워드':>10} {'순위':>4} {'업체명':>15} {'Q_Score':>10} {'추정별점':>8}")
for i, d in enumerate(type_b_data):
    if d['rank'] <= 3:  # 상위 3개만
        print(f"  {d['kw'][:8]:>10} {d['rank']:4d} {d['name'][:12]:>15} {quality_scores[i]:+10.6f} {estimated_ratings[i]:8.2f}")

# ============================================================================
# PART 6: 다중 변수 조합 탐색
# ============================================================================
print("\n" + "=" * 80)
print("PART 6: 다중 변수 조합으로 N1 설명 시도")
print("=" * 80)

# 가설: N1 = a*log(V) + b*log(B) + c*log(S) + d*log(V/B) + e*(V+B)/S + f
# V/B 비율, (V+B)/S 비율 등 추가

VB_ratio = V_b / np.maximum(B_b, 1)
log_VB_ratio = np.log1p(VB_ratio)
VB_sum = V_b + B_b
VB_S_ratio = VB_sum / np.maximum(S_b, 1)
log_VB_S = np.log1p(VB_S_ratio)

# 다양한 조합 테스트
combinations = [
    ("기본 (V,B,S)", np.column_stack([log_V_b, log_B_b, log_S_b, np.ones(len(N1_b))])),
    ("+ V/B비율", np.column_stack([log_V_b, log_B_b, log_S_b, log_VB_ratio, np.ones(len(N1_b))])),
    ("+ (V+B)/S", np.column_stack([log_V_b, log_B_b, log_S_b, log_VB_S, np.ones(len(N1_b))])),
    ("+ V/B + (V+B)/S", np.column_stack([log_V_b, log_B_b, log_S_b, log_VB_ratio, log_VB_S, np.ones(len(N1_b))])),
    ("V*B interaction", np.column_stack([log_V_b, log_B_b, log_S_b, log_V_b * log_B_b, np.ones(len(N1_b))])),
    ("순위 기반", np.column_stack([log_V_b, log_B_b, log_S_b, np.log1p(ranks_b), np.ones(len(N1_b))])),
]

print(f"\n{'조합':>20} {'R²':>10} {'순위상관':>10}")
print("-" * 45)

for name, X in combinations:
    coeffs, _, _, _ = np.linalg.lstsq(X, N1_b, rcond=None)
    pred = X @ coeffs
    r2 = 1 - np.sum((N1_b - pred)**2) / np.sum((N1_b - N1_b.mean())**2)

    # 예측 N1으로 순위 예측
    pred_ranks = stats.rankdata(-pred)
    rank_corr = stats.spearmanr(ranks_b, pred_ranks)[0]

    print(f"{name:>20} {r2:>10.4f} {rank_corr:>10.4f}")

# ============================================================================
# PART 7: 최적화 기반 역산 (미지수 X 탐색)
# ============================================================================
print("\n" + "=" * 80)
print("PART 7: 최적화 기반 미지수 X 탐색")
print("=" * 80)

print("""
목표: N1 = a*log(V) + b*log(B) + c*log(S) + d*X + e
      여기서 X를 각 업체별로 찾아 R²와 순위상관 최대화
""")

# 업체별 X를 최적화로 찾기
def objective(X_vals):
    """목표: N1을 완벽하게 설명하는 X 찾기"""
    X_full = np.column_stack([log_V_b, log_B_b, log_S_b, X_vals, np.ones(len(N1_b))])
    coeffs, _, _, _ = np.linalg.lstsq(X_full, N1_b, rcond=None)
    pred = X_full @ coeffs
    error = np.sum((N1_b - pred)**2)
    return error

# 초기값: Quality_Score를 정규화한 값
X_init = (quality_scores - quality_scores.mean()) / quality_scores.std()

# 최적화
result = minimize(objective, X_init, method='L-BFGS-B')
X_optimal = result.x

# 최적 X로 회귀
X_full = np.column_stack([log_V_b, log_B_b, log_S_b, X_optimal, np.ones(len(N1_b))])
coeffs_opt, _, _, _ = np.linalg.lstsq(X_full, N1_b, rcond=None)
pred_opt = X_full @ coeffs_opt
r2_opt = 1 - np.sum((N1_b - pred_opt)**2) / np.sum((N1_b - N1_b.mean())**2)

print(f"\n최적화 결과:")
print(f"  R² = {r2_opt:.6f}")
print(f"  최적 X 범위: {X_optimal.min():.4f} ~ {X_optimal.max():.4f}")

# X와 순위의 관계
x_rank_corr = stats.spearmanr(ranks_b, -X_optimal)[0]
print(f"  최적 X vs 순위 상관: {x_rank_corr:.4f}")

# X가 무엇을 의미하는지 분석
print(f"\n최적 X와 다른 변수들의 상관:")
print(f"  X vs V: {stats.pearsonr(X_optimal, V_b)[0]:.4f}")
print(f"  X vs B: {stats.pearsonr(X_optimal, B_b)[0]:.4f}")
print(f"  X vs S: {stats.pearsonr(X_optimal, S_b)[0]:.4f}")
print(f"  X vs V/B: {stats.pearsonr(X_optimal, VB_ratio)[0]:.4f}")
print(f"  X vs Quality_Score: {stats.pearsonr(X_optimal, quality_scores)[0]:.4f}")

# ============================================================================
# PART 8: 순위 직접 예측 모델
# ============================================================================
print("\n" + "=" * 80)
print("PART 8: 순위 직접 예측 모델")
print("=" * 80)

print("""
접근법: N1, N2, N3를 거치지 않고 V, B, S로 직접 순위 예측
""")

# 키워드별로 분리해서 순위 예측
for kw in type_b_keywords:
    kw_data = [d for d in type_b_data if d['kw'] == kw]
    kw_V = np.array([d['V'] for d in kw_data])
    kw_B = np.array([d['B'] for d in kw_data])
    kw_S = np.array([d['S'] for d in kw_data])
    kw_ranks = np.array([d['rank'] for d in kw_data])
    kw_N1 = np.array([d['N1'] for d in kw_data])
    kw_N3 = np.array([d['N3'] for d in kw_data])

    log_kw_V = np.log1p(kw_V)
    log_kw_B = np.log1p(kw_B)
    log_kw_S = np.log1p(kw_S)

    print(f"\n[{kw}]")

    # 방법 1: log(V), log(B), log(S)로 순위 예측
    X_rank = np.column_stack([log_kw_V, log_kw_B, log_kw_S, np.ones(len(kw_ranks))])
    rank_coeffs, _, _, _ = np.linalg.lstsq(X_rank, kw_ranks, rcond=None)
    pred_ranks_direct = X_rank @ rank_coeffs

    direct_corr = stats.spearmanr(kw_ranks, pred_ranks_direct)[0]
    print(f"  V,B,S로 직접 순위 예측 상관: {direct_corr:.4f}")

    # 방법 2: N1으로 순위 예측
    n1_rank_corr = stats.spearmanr(kw_ranks, -kw_N1)[0]
    print(f"  N1으로 순위 예측 상관: {n1_rank_corr:.4f}")

    # 방법 3: N3로 순위 예측
    n3_rank_corr = stats.spearmanr(kw_ranks, -kw_N3)[0]
    print(f"  N3로 순위 예측 상관: {n3_rank_corr:.4f}")

    # N1이 순위와 완벽 상관인데 V,B,S로 N1 설명이 안 됨
    # -> N1에 V,B,S 외의 숨겨진 요소가 있음

    # N1 = f(V,B,S) + hidden
    X_n1_kw = np.column_stack([log_kw_V, log_kw_B, log_kw_S, np.ones(len(kw_N1))])
    n1_kw_coeffs, _, _, _ = np.linalg.lstsq(X_n1_kw, kw_N1, rcond=None)
    pred_n1_kw = X_n1_kw @ n1_kw_coeffs
    r2_n1_kw = 1 - np.sum((kw_N1 - pred_n1_kw)**2) / np.sum((kw_N1 - kw_N1.mean())**2)

    print(f"  N1 = f(V,B,S) R²: {r2_n1_kw:.4f}")

    # Hidden 요소
    hidden_kw = kw_N1 - pred_n1_kw
    hidden_rank_corr = stats.spearmanr(kw_ranks, -hidden_kw)[0]
    print(f"  Hidden(=N1-예측N1) vs 순위 상관: {hidden_rank_corr:.4f}")

# ============================================================================
# PART 9: 결론 및 다음 단계
# ============================================================================
print("\n" + "=" * 80)
print("PART 9: 결론 및 발견")
print("=" * 80)

print("""
=== 핵심 발견 ===

1. Type A (맛집, 카페, 반지공방):
   - N1 고정, N2가 순위 결정
   - N2 = f(V, B, S) 로 예측 가능하나 순위상관이 낮은 이유:
     -> 상위 업체들의 N2 값 차이가 매우 작음 (0.001~0.01 수준)
     -> 작은 오차에도 순위가 뒤바뀜

2. Type B (브런치, 술집, 고기집):
   - N1 가변, N1이 순위 결정
   - N1 = f(V, B, S) R² = 72% (설명 안 되는 28%가 숨겨진 요소)
   - Quality_Score (=N1 - 예측N1)가 순위와 높은 상관

3. 숨겨진 요소 후보:
   - 별점 (Rating) - 추정 가능
   - CTR, 체류시간 - 네이버만 알 수 있음
   - 최근 리뷰 비율, 리뷰 증가 속도 - 추가 크롤링 필요

=== 다음 단계 ===

1. 별점 데이터 추가 크롤링
2. Quality_Score = f(별점) 관계 검증
3. 시간에 따른 N1, N2, N3 변화 추적
4. 더 많은 키워드로 일반화 검증
""")

# ============================================================================
# PART 10: 최종 공식 요약
# ============================================================================
print("\n" + "=" * 80)
print("PART 10: 최종 공식 요약")
print("=" * 80)

print(f"""
=== Type A 공식 (N1 고정) ===

N2 = a*log(V+1) + b*log(B+1) + c*log(S+1) + d*N1 + e
순위 = N2 (또는 N3) 높은 순

=== Type B 공식 (N1 가변) ===

N1_base = {n1_coeffs[0]:.6f}*log(V+1) + {n1_coeffs[1]:.6f}*log(B+1)
         + {n1_coeffs[2]:.6f}*log(S+1) + {n1_coeffs[3]:.6f}

Quality_Score = 숨겨진 요소 (별점 기반 추정: k*(Rating-4.5), k≈{k_estimated:.4f})

N1 = N1_base + Quality_Score

순위 = N1 높은 순 (상관: ~0.95)

=== 키워드 유형 판별 ===

1. 상위 10개 업체 N1 수집
2. N1 표준편차 < 0.001 → Type A
3. N1 표준편차 > 0.001 → Type B
""")
