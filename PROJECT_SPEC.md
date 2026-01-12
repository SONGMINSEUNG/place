# 플레이스 랭킹 분석 서비스 - 프로젝트 명세서

## 1. 서비스 개요

### 목표
네이버 플레이스 순위 예측 및 마케팅 전략 제언 서비스

### 핵심 차별점
| ADLOG | 우리 서비스 |
|-------|-------------|
| 현재 순위/지수만 조회 | 예측 + 전략 제언 |
| 공개 데이터만 사용 | 사장님 내부 데이터 활용 |
| 고정된 알고리즘 | 자동 학습 AI |
| 의미 모를 지수 (N1, N2, N3) | 직관적 점수 (0-100점) |

---

## 2. 데이터 구조

### 2.1 ADLOG API (숨김 - 내부용)
```
POST http://adlog.ai.kr/placeAnalysis.php
Body: {"query": "검색키워드"}

Response:
- place_rank: 순위
- place_id: 네이버 플레이스 ID
- place_name: 업체명
- place_blog_cnt: 블로그 리뷰 수 (B)
- place_visit_cnt: 방문자 리뷰 수 (V)
- place_save_cnt: 저장 수 (S)
- place_index1: N1 (키워드 지수)
- place_index2: N2 (품질 지수) ← 핵심
- place_index3: N3 (종합 지수)
```

### 2.2 사용자 입력 데이터
```
- 유입수: 일간 (스마트플레이스에서 확인)
- 예약수: 일간 (스마트플레이스에서 확인)
```

### 2.3 우리 서비스 출력 (변환)
```
ADLOG 원본 → 우리 서비스
─────────────────────────────────
N1: 0.366894  →  키워드지수: 37점
N2: 0.547819  →  품질점수: 78점
N3: 0.368945  →  종합경쟁력: 82점
순위: 3       →  현재 순위: 3위

+ 추가 제공:
  - 1위까지 필요한 점수: +5점
  - 예상 순위 변화: "3일 내 2위 가능"
  - 마케팅 제언: "유입수 100 늘리면 +3점"
  - 경쟁사 비교표
  - 주간/월간 변화 그래프
```

---

## 3. 핵심 로직

### 3.1 자동 학습 시스템
```
1. 사용자 검색 + 데이터 입력
   ↓
2. ADLOG API 호출 → N2(정답) 획득
   ↓
3. DB 저장: {유입수, 예약수, V, B, S, N2, timestamp}
   ↓
4. 상관관계 자동 체크
   - 유입수 ↔ N2 상관분석
   - 예약수 ↔ N2 상관분석
   - p-value < 0.05 → 유의미 → 모델에 포함
   ↓
5. 딥러닝 모델 자동 재학습
   ↓
6. 정확도 점점 상승
   - 1주차: R² = 30%
   - 1개월: R² = 50%
   - 3개월: R² = 70%+
```

### 3.2 점수 변환 공식
```python
# N2 (0.50~0.60 범위) → 품질점수 (0-100, 소수점 4자리 유지)
품질점수 = (N2 - 0.50) / 0.10 * 100

# 예시:
# N2 = 0.547819 → (0.547819 - 0.50) / 0.10 * 100 = 47.8190점
# N2 = 0.558677 → (0.558677 - 0.50) / 0.10 * 100 = 58.6770점

# 소수점 유지로 미세한 차이도 비교 가능
```

### 3.3 마케팅 제언 로직
```python
# 모델이 학습한 계수 활용 (소수점 정밀도 유지)
유입수_효과 = model.coef_['유입수']      # 예: 0.000234
예약수_효과 = model.coef_['예약수']      # 예: 0.000912
블로그_효과 = model.coef_['블로그리뷰']   # 예: 0.002143
방문자_효과 = model.coef_['방문자리뷰']   # 예: 0.000598

# 제언 생성 (항목별 개수 + 점수 섬세하게)
"유입수 +100명 → +2.3456점"
"예약수 +20건 → +1.8234점"
"블로그 리뷰 +15개 → +3.2145점"
"방문자 리뷰 +50개 → +2.9876점"
```

### 3.4 시뮬레이션 기능
```python
# 사용자가 커스텀 개수 입력 → 실시간 점수 계산
def simulate(유입수, 예약수, 블로그, 방문자):
    증가점수 = (
        유입수 * model.coef_['유입수'] +
        예약수 * model.coef_['예약수'] +
        블로그 * model.coef_['블로그리뷰'] +
        방문자 * model.coef_['방문자리뷰']
    ) * 100  # 0-100 스케일 변환

    return {
        "유입수_효과": f"+{유입수 * coef['유입수'] * 100:.4f}점",
        "예약수_효과": f"+{예약수 * coef['예약수'] * 100:.4f}점",
        "블로그_효과": f"+{블로그 * coef['블로그리뷰'] * 100:.4f}점",
        "방문자_효과": f"+{방문자 * coef['방문자리뷰'] * 100:.4f}점",
        "총_증가": f"+{증가점수:.4f}점",
        "예상_품질점수": f"{현재점수 + 증가점수:.4f}점"
    }
```

---

## 4. 데이터베이스 스키마

### 4.1 places 테이블
```sql
CREATE TABLE places (
    id SERIAL PRIMARY KEY,
    place_id VARCHAR(20) UNIQUE,  -- 네이버 플레이스 ID
    place_name VARCHAR(100),
    category VARCHAR(50),
    created_at TIMESTAMP DEFAULT NOW()
);
```

### 4.2 daily_data 테이블
```sql
CREATE TABLE daily_data (
    id SERIAL PRIMARY KEY,
    place_id VARCHAR(20) REFERENCES places(place_id),
    keyword VARCHAR(50),          -- 검색 키워드
    date DATE,

    -- ADLOG 데이터
    rank INT,
    blog_cnt INT,                 -- B
    visit_cnt INT,                -- V
    save_cnt INT,                 -- S
    n1 DECIMAL(10,6),
    n2 DECIMAL(10,6),
    n3 DECIMAL(10,6),

    -- 사용자 입력 데이터
    inflow INT,                   -- 유입수
    reservation INT,              -- 예약수

    created_at TIMESTAMP DEFAULT NOW(),

    UNIQUE(place_id, keyword, date)
);
```

### 4.3 model_features 테이블
```sql
CREATE TABLE model_features (
    id SERIAL PRIMARY KEY,
    feature_name VARCHAR(50),     -- 'inflow', 'reservation' 등
    correlation DECIMAL(5,4),     -- N2와의 상관계수
    p_value DECIMAL(10,8),        -- 유의확률
    is_significant BOOLEAN,       -- p < 0.05 여부
    coefficient DECIMAL(15,10),   -- 모델 계수
    updated_at TIMESTAMP DEFAULT NOW()
);
```

### 4.4 predictions 테이블
```sql
CREATE TABLE predictions (
    id SERIAL PRIMARY KEY,
    place_id VARCHAR(20),
    keyword VARCHAR(50),
    predicted_n2 DECIMAL(10,6),
    predicted_rank INT,
    confidence DECIMAL(5,2),      -- 신뢰도 %
    recommendation TEXT,          -- 마케팅 제언
    created_at TIMESTAMP DEFAULT NOW()
);
```

---

## 5. API 엔드포인트

### 5.1 검색 및 분석
```
POST /api/analyze
Body: {
    "keyword": "홍대맛집",
    "place_name": "유메오뎅 홍대",
    "inflow": 150,        -- 오늘 유입수
    "reservation": 5      -- 오늘 예약수
}

Response: {
    "current": {
        "rank": 3,
        "quality_score": 47.8190,      -- 품질점수 (N2 변환, 소수점 4자리)
        "keyword_score": 36.6894,      -- 키워드지수 (N1 변환)
        "competition_score": 68.9450   -- 종합경쟁력 (N3 변환)
    },
    "comparison": {
        "rank_1_gap": 10.8580,         -- 1위와 점수 차이
        "rank_1_score": 58.6770        -- 1위 점수
    },
    "recommendation": [
        {"type": "유입수", "amount": 100, "unit": "명", "effect": 2.3456},
        {"type": "예약수", "amount": 20, "unit": "건", "effect": 1.8234},
        {"type": "블로그리뷰", "amount": 15, "unit": "개", "effect": 3.2145},
        {"type": "방문자리뷰", "amount": 50, "unit": "개", "effect": 2.9876}
    ],
    "competitors": [
        {"rank": 1, "name": "경쟁사A", "score": 58.6770},
        {"rank": 2, "name": "경쟁사B", "score": 52.3410}
    ]
}
```

### 5.4 시뮬레이션
```
POST /api/simulate
Body: {
    "place_id": "1234567890",
    "keyword": "홍대맛집",
    "inputs": {
        "inflow": 150,           -- 유입수 추가
        "reservation": 25,       -- 예약수 추가
        "blog_review": 10,       -- 블로그 리뷰 추가
        "visit_review": 30       -- 방문자 리뷰 추가
    }
}

Response: {
    "current_score": 47.8190,
    "effects": {
        "inflow": {"amount": 150, "effect": 3.5184},
        "reservation": {"amount": 25, "effect": 2.2793},
        "blog_review": {"amount": 10, "effect": 2.1430},
        "visit_review": {"amount": 30, "effect": 1.7926}
    },
    "total_effect": 9.7333,
    "predicted_score": 57.5523,
    "predicted_rank": 2,
    "current_rank": 5
}
```

### 5.2 히스토리 조회
```
GET /api/history?place_id=xxx&days=30

Response: {
    "data": [
        {"date": "2026-01-10", "rank": 3, "score": 78},
        {"date": "2026-01-09", "rank": 4, "score": 75},
        ...
    ]
}
```

### 5.3 모델 상태 조회
```
GET /api/model/status

Response: {
    "total_data_count": 5000,
    "r_squared": 0.52,
    "significant_features": ["inflow", "reservation"],
    "last_trained": "2026-01-10 10:00:00"
}
```

---

## 6. 기술 스택

### Backend
- Python FastAPI
- PostgreSQL (Supabase)
- scikit-learn / PyTorch (딥러닝)
- APScheduler (자동 학습 스케줄)

### Frontend
- Next.js / React
- Tailwind CSS
- Chart.js (그래프)

### Infra
- Vercel (Frontend)
- Supabase (Backend + DB)

---

## 7. 개발 우선순위

### Phase 1: MVP (1주)
1. ADLOG API 연동
2. 기본 DB 구조
3. 점수 변환 로직
4. 기본 UI (검색 + 결과)

### Phase 2: 학습 시스템 (2주)
1. 사용자 입력 수집
2. 상관관계 자동 분석
3. 모델 자동 학습
4. 마케팅 제언 생성

### Phase 3: 고도화 (2주)
1. 히스토리 그래프
2. 경쟁사 비교
3. 알림 시스템
4. 리포트 생성

---

## 8. 핵심 메트릭

### 성공 지표
- 모델 R² > 50% (3개월 내)
- MAU 1000명
- 유료 전환율 5%

### 모니터링
- 일간 데이터 수집량
- 모델 정확도 변화
- 사용자 입력 완료율
