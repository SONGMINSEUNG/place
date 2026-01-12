# 플레이스 랭킹 분석 서비스 - 백엔드 기획서

## 목차
1. [시스템 아키텍처](#1-시스템-아키텍처)
2. [API 상세 명세](#2-api-상세-명세)
3. [데이터 플로우](#3-데이터-플로우)
4. [자동 학습 시스템 상세 로직](#4-자동-학습-시스템-상세-로직)
5. [에러 처리 방안](#5-에러-처리-방안)
6. [보안 고려사항](#6-보안-고려사항)

---

## 1. 시스템 아키텍처

### 1.1 전체 아키텍처 다이어그램

```
+------------------+     +------------------+     +------------------+
|                  |     |                  |     |                  |
|  Frontend        |     |  Backend         |     |  External API    |
|  (Next.js)       |     |  (FastAPI)       |     |  (ADLOG)         |
|                  |     |                  |     |                  |
+--------+---------+     +--------+---------+     +--------+---------+
         |                        |                        |
         |   HTTPS Request        |   Internal Only        |
         +----------------------->|   (Proxy)              |
         |                        +----------------------->|
         |                        |                        |
         |                        |<-----------------------+
         |<-----------------------+                        |
         |                        |                        |
+--------+---------+     +--------+---------+     +--------+---------+
|                  |     |                  |     |                  |
|  Vercel          |     |  Supabase        |     |  ML Service      |
|  Hosting         |     |  (PostgreSQL)    |     |  (Background)    |
|                  |     |                  |     |                  |
+------------------+     +------------------+     +------------------+
```

### 1.2 컴포넌트별 상세 구조

```
Backend Server (FastAPI)
|
+-- api/
|   +-- v1/
|       +-- analyze.py        # 분석 API
|       +-- history.py        # 히스토리 API
|       +-- model.py          # 모델 상태 API
|       +-- competitors.py    # 경쟁사 비교 API
|
+-- core/
|   +-- config.py             # 환경 설정
|   +-- security.py           # 보안 관련
|   +-- exceptions.py         # 커스텀 예외
|
+-- services/
|   +-- adlog_proxy.py        # ADLOG API 프록시 (숨김 처리)
|   +-- score_converter.py    # 점수 변환 로직
|   +-- prediction.py         # 예측 서비스
|   +-- recommendation.py     # 마케팅 제언 생성
|
+-- ml/
|   +-- trainer.py            # 모델 학습기
|   +-- predictor.py          # 예측기
|   +-- feature_analyzer.py   # 특성 분석기
|   +-- scheduler.py          # 학습 스케줄러
|
+-- models/
|   +-- database.py           # DB 모델
|   +-- schemas.py            # Pydantic 스키마
|
+-- utils/
|   +-- logger.py             # 로깅
|   +-- validators.py         # 입력 검증
```

### 1.3 인프라 구성도

```
                    Internet
                        |
                        v
            +-------------------+
            |   Cloudflare      |
            |   (WAF/DDoS)      |
            +-------------------+
                        |
          +-------------+-------------+
          |                           |
          v                           v
+------------------+        +------------------+
|   Vercel         |        |   Supabase       |
|   (Frontend)     |        |   Edge Functions |
|                  |        |   (Backend API)  |
+------------------+        +------------------+
                                      |
                    +-----------------+-----------------+
                    |                 |                 |
                    v                 v                 v
            +------------+    +------------+    +------------+
            | PostgreSQL |    |   Redis    |    |  Storage   |
            | (Main DB)  |    |  (Cache)   |    |  (Models)  |
            +------------+    +------------+    +------------+
```

---

## 2. API 상세 명세

### 2.1 인증 관련 API

#### POST /api/v1/auth/register
```
Description: 사용자 회원가입

Request:
{
    "email": "user@example.com",
    "password": "securePassword123!",
    "business_name": "유메오뎅 홍대"
}

Response (201):
{
    "success": true,
    "data": {
        "user_id": "uuid-xxx",
        "email": "user@example.com",
        "created_at": "2026-01-10T10:00:00Z"
    }
}

Error Response (400):
{
    "success": false,
    "error": {
        "code": "VALIDATION_ERROR",
        "message": "이메일 형식이 올바르지 않습니다."
    }
}
```

#### POST /api/v1/auth/login
```
Description: 로그인 및 토큰 발급

Request:
{
    "email": "user@example.com",
    "password": "securePassword123!"
}

Response (200):
{
    "success": true,
    "data": {
        "access_token": "eyJhbGciOiJIUzI1NiIs...",
        "refresh_token": "eyJhbGciOiJIUzI1NiIs...",
        "expires_in": 3600
    }
}
```

### 2.2 분석 API

#### POST /api/v1/analyze
```
Description: 플레이스 분석 요청 (핵심 API)

Headers:
    Authorization: Bearer {access_token}
    Content-Type: application/json

Request:
{
    "keyword": "홍대맛집",
    "place_name": "유메오뎅 홍대",       // Optional: 없으면 전체 조회
    "inflow": 150,                       // Optional: 사용자 입력
    "reservation": 5                     // Optional: 사용자 입력
}

Response (200):
{
    "success": true,
    "data": {
        "analysis_id": "uuid-xxx",
        "timestamp": "2026-01-10T10:00:00Z",

        "current_status": {
            "place_id": "1234567890",
            "place_name": "유메오뎅 홍대",
            "rank": 3,
            "total_places": 50,

            "scores": {
                "quality_score": 78,         // 품질점수 (N2 기반)
                "keyword_score": 37,         // 키워드지수 (N1 기반)
                "competition_score": 82      // 종합경쟁력 (N3 기반)
            },

            "raw_metrics": {
                "blog_count": 156,           // 블로그 리뷰 수
                "visit_count": 892,          // 방문자 리뷰 수
                "save_count": 234            // 저장 수
            }
        },

        "gap_analysis": {
            "to_rank_1": {
                "score_gap": 5,
                "estimated_effort": "블로그 리뷰 20개 필요"
            },
            "to_avg": {
                "score_gap": 3,
                "position": "상위 6%"
            }
        },

        "prediction": {
            "expected_score_change": "+2점",
            "expected_rank": 2,
            "confidence": 65,
            "prediction_period": "7일",
            "factors": [
                {"factor": "유입수 상승 추세", "impact": "+1.5점"},
                {"factor": "리뷰 증가", "impact": "+0.5점"}
            ]
        },

        "recommendations": [
            {
                "priority": 1,
                "type": "INFLOW",
                "message": "유입수 100 늘리면 +3점 예상",
                "effort": "MEDIUM",
                "expected_impact": 3
            },
            {
                "priority": 2,
                "type": "RESERVATION",
                "message": "예약수 10 늘리면 +1점 예상",
                "effort": "LOW",
                "expected_impact": 1
            },
            {
                "priority": 3,
                "type": "TREND",
                "message": "현재 추세면 3일 내 2위 가능",
                "effort": null,
                "expected_impact": null
            }
        ],

        "competitors": [
            {
                "rank": 1,
                "name": "경쟁사A",
                "quality_score": 83,
                "gap": 5,
                "trend": "stable"
            },
            {
                "rank": 2,
                "name": "경쟁사B",
                "quality_score": 80,
                "gap": 2,
                "trend": "rising"
            }
        ]
    }
}
```

#### POST /api/v1/analyze/batch
```
Description: 여러 키워드 일괄 분석

Request:
{
    "keywords": ["홍대맛집", "홍대오뎅", "홍대일식"],
    "place_name": "유메오뎅 홍대"
}

Response (200):
{
    "success": true,
    "data": {
        "results": [
            { "keyword": "홍대맛집", "rank": 3, "quality_score": 78 },
            { "keyword": "홍대오뎅", "rank": 1, "quality_score": 92 },
            { "keyword": "홍대일식", "rank": 5, "quality_score": 71 }
        ],
        "summary": {
            "best_keyword": "홍대오뎅",
            "worst_keyword": "홍대일식",
            "average_rank": 3
        }
    }
}
```

### 2.3 히스토리 API

#### GET /api/v1/history
```
Description: 순위/점수 변화 이력 조회

Query Parameters:
    place_id: string (required)
    keyword: string (required)
    days: int (default: 30, max: 90)
    metrics: string (comma-separated, default: "rank,quality_score")

Response (200):
{
    "success": true,
    "data": {
        "place_id": "1234567890",
        "keyword": "홍대맛집",
        "period": {
            "start": "2025-12-11",
            "end": "2026-01-10"
        },
        "history": [
            {
                "date": "2026-01-10",
                "rank": 3,
                "quality_score": 78,
                "blog_count": 156,
                "visit_count": 892,
                "inflow": 150,
                "reservation": 5
            },
            {
                "date": "2026-01-09",
                "rank": 4,
                "quality_score": 75,
                "blog_count": 152,
                "visit_count": 880,
                "inflow": 130,
                "reservation": 3
            }
            // ... more data
        ],
        "trends": {
            "rank": {
                "direction": "improving",
                "change": -1,
                "avg_30d": 4.2
            },
            "quality_score": {
                "direction": "improving",
                "change": 3,
                "avg_30d": 74.5
            }
        }
    }
}
```

#### GET /api/v1/history/compare
```
Description: 기간별 비교 분석

Query Parameters:
    place_id: string
    keyword: string
    period1_start: date
    period1_end: date
    period2_start: date
    period2_end: date

Response (200):
{
    "success": true,
    "data": {
        "period1": {
            "avg_rank": 5.2,
            "avg_score": 72.3
        },
        "period2": {
            "avg_rank": 3.8,
            "avg_score": 77.1
        },
        "improvement": {
            "rank": "+1.4위",
            "score": "+4.8점"
        }
    }
}
```

### 2.4 모델 상태 API

#### GET /api/v1/model/status
```
Description: 학습 모델 상태 조회 (관리자용)

Response (200):
{
    "success": true,
    "data": {
        "model_version": "v1.2.3",
        "last_trained_at": "2026-01-10T02:00:00Z",
        "next_training_at": "2026-01-11T02:00:00Z",

        "training_stats": {
            "total_data_count": 5000,
            "unique_places": 850,
            "unique_keywords": 320
        },

        "model_performance": {
            "r_squared": 0.52,
            "mae": 2.3,
            "rmse": 3.1,
            "accuracy_trend": [
                {"date": "2026-01-01", "r_squared": 0.45},
                {"date": "2026-01-05", "r_squared": 0.48},
                {"date": "2026-01-10", "r_squared": 0.52}
            ]
        },

        "feature_importance": [
            {"feature": "visit_count", "importance": 0.35, "is_significant": true},
            {"feature": "blog_count", "importance": 0.25, "is_significant": true},
            {"feature": "inflow", "importance": 0.20, "is_significant": true},
            {"feature": "save_count", "importance": 0.12, "is_significant": true},
            {"feature": "reservation", "importance": 0.08, "is_significant": false}
        ],

        "significant_features": ["visit_count", "blog_count", "inflow", "save_count"],

        "health": {
            "status": "healthy",
            "issues": []
        }
    }
}
```

#### POST /api/v1/model/retrain (Admin Only)
```
Description: 수동 재학습 트리거

Request:
{
    "force": true,
    "include_new_features": ["new_metric_1"]
}

Response (202):
{
    "success": true,
    "data": {
        "job_id": "uuid-xxx",
        "status": "queued",
        "estimated_completion": "2026-01-10T10:30:00Z"
    }
}
```

### 2.5 경쟁사 분석 API

#### GET /api/v1/competitors
```
Description: 경쟁사 상세 분석

Query Parameters:
    keyword: string (required)
    place_id: string (optional - 내 업체와 비교)
    top_n: int (default: 10)

Response (200):
{
    "success": true,
    "data": {
        "keyword": "홍대맛집",
        "my_place": {
            "place_id": "1234567890",
            "rank": 3,
            "quality_score": 78
        },
        "competitors": [
            {
                "rank": 1,
                "place_id": "1111111111",
                "name": "경쟁사A",
                "category": "일식",
                "quality_score": 83,
                "metrics": {
                    "blog_count": 200,
                    "visit_count": 1200,
                    "save_count": 450
                },
                "gap_to_me": {
                    "score": 5,
                    "blog_count": 44,
                    "visit_count": 308
                },
                "trend": "stable"
            }
            // ... more competitors
        ],
        "market_analysis": {
            "avg_quality_score": 68,
            "score_distribution": {
                "0-20": 5,
                "21-40": 10,
                "41-60": 15,
                "61-80": 12,
                "81-100": 8
            },
            "my_percentile": 94
        }
    }
}
```

---

## 3. 데이터 플로우

### 3.1 전체 데이터 흐름

```
+------------------+
|  User Request    |
|  (Keyword +      |
|   User Data)     |
+--------+---------+
         |
         v
+------------------+
|  Input           |
|  Validation      |
|  & Sanitization  |
+--------+---------+
         |
         v
+------------------+     +------------------+
|  Cache Check     |---->|  Redis Cache     |
|  (Hit?)          |     |  (TTL: 1hour)    |
+--------+---------+     +------------------+
         | Miss
         v
+------------------+
|  ADLOG Proxy     |
|  Service         |
+--------+---------+
         |
         v
+------------------+     +------------------+
|  ADLOG API       |---->|  Raw Response    |
|  (Hidden)        |     |  (N1, N2, N3)    |
+--------+---------+     +------------------+
         |
         v
+------------------+
|  Score           |
|  Conversion      |
+--------+---------+
         |
         +-----------------+
         |                 |
         v                 v
+------------------+  +------------------+
|  DB Storage      |  |  ML Prediction   |
|  (Historical)    |  |  Engine          |
+--------+---------+  +--------+---------+
         |                     |
         +----------+----------+
                    |
                    v
           +------------------+
           |  Response        |
           |  Aggregation     |
           +--------+---------+
                    |
                    v
           +------------------+
           |  Cache Update    |
           +--------+---------+
                    |
                    v
           +------------------+
           |  API Response    |
           +------------------+
```

### 3.2 사용자 데이터 입력 플로우

```
+------------------+
|  User Input      |
|  - inflow        |
|  - reservation   |
+--------+---------+
         |
         v
+------------------+
|  Validation      |
|  - Range check   |
|  - Type check    |
+--------+---------+
         |
         v
+------------------+
|  daily_data      |
|  Table Update    |
|  (UPSERT)        |
+--------+---------+
         |
         v
+------------------+
|  Trigger:        |
|  Correlation     |
|  Analysis        |
+--------+---------+
         |
         v
+------------------+
|  model_features  |
|  Table Update    |
+--------+---------+
         |
         v
+------------------+
|  Training Queue  |
|  (if threshold   |
|   reached)       |
+------------------+
```

### 3.3 점수 변환 상세 플로우

```
ADLOG Raw Data                     Our Service Output
+------------------+               +------------------+
| N1: 0.366894     |   Convert    | keyword_score:   |
|                  | -----------> |   37점           |
+------------------+               +------------------+
        |
        | Formula: round(N1 * 100)
        |
+------------------+               +------------------+
| N2: 0.547819     |   Convert    | quality_score:   |
|                  | -----------> |   78점           |
+------------------+               +------------------+
        |
        | Formula: ((N2 - 0.5) / 0.15) * 100
        | (0.5~0.65 범위를 0~100으로 정규화)
        |
+------------------+               +------------------+
| N3: 0.368945     |   Convert    | competition_     |
|                  | -----------> |   score: 82점    |
+------------------+               +------------------+
        |
        | Formula: 상대 순위 기반
        | (1 - (rank-1)/total) * 100
```

### 3.4 캐싱 전략

```
Cache Layers:

Layer 1: Application Cache (In-Memory)
+----------------------------------+
| Key: analyze:{keyword}:{place}   |
| TTL: 5 minutes                   |
| Use: Hot data (빈번한 동일 요청)  |
+----------------------------------+

Layer 2: Redis Cache
+----------------------------------+
| Key: adlog:{keyword}             |
| TTL: 1 hour                      |
| Use: ADLOG API 응답 캐싱          |
+----------------------------------+

Layer 3: Database
+----------------------------------+
| Table: daily_data                |
| Key: place_id + keyword + date   |
| Use: 영구 저장 (분석/학습용)      |
+----------------------------------+

Cache Invalidation:
- 사용자 데이터 입력 시 해당 키 무효화
- 매일 00:00 전체 분석 데이터 갱신
- 모델 재학습 시 예측 캐시 무효화
```

---

## 4. 자동 학습 시스템 상세 로직

### 4.1 학습 파이프라인 개요

```
+----------------+     +----------------+     +----------------+
|  Data          |     |  Feature       |     |  Model         |
|  Collection    | --> |  Engineering   | --> |  Training      |
+----------------+     +----------------+     +----------------+
        ^                                              |
        |                                              v
+----------------+     +----------------+     +----------------+
|  Monitoring    | <-- |  Validation    | <-- |  Evaluation    |
+----------------+     +----------------+     +----------------+
```

### 4.2 데이터 수집 로직

```python
# 의사 코드

class DataCollector:
    def collect_on_request(self, keyword, user_data):
        """매 API 요청 시 데이터 수집"""

        # 1. ADLOG API 호출
        adlog_response = self.adlog_proxy.fetch(keyword)

        # 2. 각 업체별 데이터 저장
        for place in adlog_response:
            daily_record = {
                'place_id': place.id,
                'keyword': keyword,
                'date': today(),

                # ADLOG 데이터
                'rank': place.rank,
                'blog_cnt': place.blog_cnt,
                'visit_cnt': place.visit_cnt,
                'save_cnt': place.save_cnt,
                'n1': place.n1,
                'n2': place.n2,
                'n3': place.n3,

                # 사용자 데이터 (해당 업체인 경우)
                'inflow': user_data.inflow if is_my_place else None,
                'reservation': user_data.reservation if is_my_place else None
            }

            self.db.upsert('daily_data', daily_record)

        # 3. 데이터 수집 카운트 증가
        self.metrics.increment('data_collected')

        # 4. 학습 트리거 체크
        if self.should_trigger_training():
            self.scheduler.queue_training()
```

### 4.3 상관관계 분석 로직

```python
class FeatureAnalyzer:
    def analyze_correlations(self):
        """모든 특성과 N2(품질지수)의 상관관계 분석"""

        features = ['inflow', 'reservation', 'blog_cnt', 'visit_cnt', 'save_cnt']
        target = 'n2'

        # 1. 데이터 로드 (최근 30일, 충분한 샘플)
        data = self.db.query("""
            SELECT * FROM daily_data
            WHERE date >= NOW() - INTERVAL '30 days'
            AND inflow IS NOT NULL
        """)

        if len(data) < 100:  # 최소 샘플 수
            return {"status": "insufficient_data", "count": len(data)}

        results = []

        for feature in features:
            # 2. Pearson 상관계수 계산
            correlation, p_value = stats.pearsonr(
                data[feature],
                data[target]
            )

            # 3. 유의성 판단
            is_significant = p_value < 0.05

            # 4. 결과 저장
            result = {
                'feature_name': feature,
                'correlation': round(correlation, 4),
                'p_value': round(p_value, 8),
                'is_significant': is_significant,
                'sample_size': len(data)
            }

            results.append(result)

            # 5. DB 업데이트
            self.db.upsert('model_features', result)

        return {
            "status": "completed",
            "significant_features": [r for r in results if r['is_significant']],
            "all_features": results
        }

    def get_significant_features(self):
        """유의미한 특성만 반환 (모델 학습용)"""
        return self.db.query("""
            SELECT feature_name
            FROM model_features
            WHERE is_significant = TRUE
            ORDER BY ABS(correlation) DESC
        """)
```

### 4.4 모델 학습 로직

```python
class ModelTrainer:
    def __init__(self):
        self.model = None
        self.scaler = StandardScaler()
        self.feature_names = []

    def prepare_training_data(self):
        """학습 데이터 준비"""

        # 1. 유의미한 특성 조회
        significant_features = self.feature_analyzer.get_significant_features()
        self.feature_names = [f['feature_name'] for f in significant_features]

        # 2. 학습 데이터 로드
        query = f"""
            SELECT {', '.join(self.feature_names)}, n2 as target
            FROM daily_data
            WHERE {' AND '.join([f'{f} IS NOT NULL' for f in self.feature_names])}
            AND n2 IS NOT NULL
        """

        data = self.db.query(query)

        X = data[self.feature_names].values
        y = data['target'].values

        return train_test_split(X, y, test_size=0.2, random_state=42)

    def train(self):
        """모델 학습 실행"""

        X_train, X_test, y_train, y_test = self.prepare_training_data()

        if len(X_train) < 100:
            return {"status": "insufficient_data"}

        # 1. 특성 스케일링
        X_train_scaled = self.scaler.fit_transform(X_train)
        X_test_scaled = self.scaler.transform(X_test)

        # 2. 모델 선택 (데이터 양에 따라)
        if len(X_train) < 1000:
            # 데이터 적음: 선형 회귀
            self.model = Ridge(alpha=1.0)
        elif len(X_train) < 5000:
            # 데이터 중간: 랜덤 포레스트
            self.model = RandomForestRegressor(
                n_estimators=100,
                max_depth=10,
                random_state=42
            )
        else:
            # 데이터 많음: 그래디언트 부스팅
            self.model = GradientBoostingRegressor(
                n_estimators=200,
                max_depth=5,
                learning_rate=0.1,
                random_state=42
            )

        # 3. 학습
        self.model.fit(X_train_scaled, y_train)

        # 4. 평가
        y_pred = self.model.predict(X_test_scaled)

        metrics = {
            'r_squared': r2_score(y_test, y_pred),
            'mae': mean_absolute_error(y_test, y_pred),
            'rmse': np.sqrt(mean_squared_error(y_test, y_pred))
        }

        # 5. 모델 저장
        self.save_model()

        # 6. 계수 저장 (선형 모델인 경우)
        if hasattr(self.model, 'coef_'):
            self.save_coefficients()

        return {
            "status": "completed",
            "metrics": metrics,
            "sample_size": len(X_train),
            "features_used": self.feature_names
        }

    def save_coefficients(self):
        """모델 계수 저장 (마케팅 제언용)"""

        for i, feature in enumerate(self.feature_names):
            self.db.update('model_features', {
                'feature_name': feature,
                'coefficient': self.model.coef_[i]
            })
```

### 4.5 학습 스케줄러

```python
class TrainingScheduler:
    def __init__(self):
        self.scheduler = APScheduler()
        self.setup_jobs()

    def setup_jobs(self):
        """스케줄 작업 설정"""

        # 1. 매일 새벽 2시: 상관관계 분석
        self.scheduler.add_job(
            self.daily_correlation_analysis,
            trigger='cron',
            hour=2,
            minute=0
        )

        # 2. 매일 새벽 3시: 모델 재학습 (조건부)
        self.scheduler.add_job(
            self.conditional_training,
            trigger='cron',
            hour=3,
            minute=0
        )

        # 3. 매주 일요일: 전체 재학습
        self.scheduler.add_job(
            self.full_training,
            trigger='cron',
            day_of_week='sun',
            hour=4,
            minute=0
        )

    def conditional_training(self):
        """조건부 재학습"""

        # 조건 체크
        conditions = self.check_training_conditions()

        if conditions['should_train']:
            self.trainer.train()

    def check_training_conditions(self):
        """학습 조건 확인"""

        last_training = self.get_last_training_time()
        new_data_count = self.get_new_data_count(since=last_training)
        current_accuracy = self.get_current_accuracy()

        should_train = (
            new_data_count >= 500 or  # 새 데이터 500개 이상
            (datetime.now() - last_training).days >= 7 or  # 7일 경과
            current_accuracy < 0.4  # 정확도 40% 미만
        )

        return {
            'should_train': should_train,
            'new_data_count': new_data_count,
            'days_since_training': (datetime.now() - last_training).days,
            'current_accuracy': current_accuracy
        }
```

### 4.6 예측 및 제언 생성

```python
class PredictionService:
    def predict(self, place_data, user_data):
        """N2 예측 및 마케팅 제언 생성"""

        # 1. 특성 준비
        features = self.prepare_features(place_data, user_data)

        # 2. 예측
        predicted_n2 = self.model.predict([features])[0]

        # 3. 신뢰도 계산
        confidence = self.calculate_confidence(features)

        # 4. 마케팅 제언 생성
        recommendations = self.generate_recommendations(
            current_n2=place_data.n2,
            predicted_n2=predicted_n2,
            user_data=user_data
        )

        return {
            'predicted_n2': predicted_n2,
            'predicted_score': self.convert_to_score(predicted_n2),
            'confidence': confidence,
            'recommendations': recommendations
        }

    def generate_recommendations(self, current_n2, predicted_n2, user_data):
        """마케팅 제언 생성"""

        recommendations = []
        coefficients = self.get_coefficients()

        # 1. 유입수 기반 제언
        if 'inflow' in coefficients:
            inflow_effect = coefficients['inflow']
            needed_inflow = 100  # 기준
            expected_gain = needed_inflow * inflow_effect * 1000  # 점수 환산

            recommendations.append({
                'priority': 1,
                'type': 'INFLOW',
                'message': f'유입수 {needed_inflow} 늘리면 +{expected_gain:.0f}점 예상',
                'effort': 'MEDIUM',
                'expected_impact': expected_gain
            })

        # 2. 예약수 기반 제언
        if 'reservation' in coefficients:
            reservation_effect = coefficients['reservation']
            needed_reservation = 10
            expected_gain = needed_reservation * reservation_effect * 1000

            recommendations.append({
                'priority': 2,
                'type': 'RESERVATION',
                'message': f'예약수 {needed_reservation} 늘리면 +{expected_gain:.0f}점 예상',
                'effort': 'LOW',
                'expected_impact': expected_gain
            })

        # 3. 추세 기반 제언
        trend = self.analyze_trend(user_data.place_id)
        if trend['direction'] == 'improving':
            days_to_target = self.estimate_days_to_rank(current_n2, trend)

            recommendations.append({
                'priority': 3,
                'type': 'TREND',
                'message': f'현재 추세면 {days_to_target}일 내 {trend["target_rank"]}위 가능',
                'effort': None,
                'expected_impact': None
            })

        return sorted(recommendations, key=lambda x: x['priority'])
```

### 4.7 학습 성능 모니터링

```python
class ModelMonitor:
    def track_performance(self):
        """모델 성능 추적"""

        # 1. 예측 vs 실제 비교 (다음날 검증)
        yesterday = date.today() - timedelta(days=1)

        predictions = self.db.query("""
            SELECT place_id, keyword, predicted_n2
            FROM predictions
            WHERE DATE(created_at) = %s
        """, [yesterday])

        actuals = self.db.query("""
            SELECT place_id, keyword, n2
            FROM daily_data
            WHERE date = %s
        """, [date.today()])

        # 2. 정확도 계산
        matched = self.match_predictions_actuals(predictions, actuals)

        if len(matched) > 0:
            mape = np.mean(np.abs(
                (matched['actual'] - matched['predicted']) / matched['actual']
            )) * 100

            accuracy_record = {
                'date': date.today(),
                'sample_size': len(matched),
                'mape': mape,
                'r_squared': self.calculate_r2(matched)
            }

            self.db.insert('model_accuracy_log', accuracy_record)

        # 3. 알림 (정확도 급락 시)
        if mape > 20:  # 20% 이상 오차
            self.alert_service.send(
                level='warning',
                message=f'모델 정확도 저하: MAPE {mape:.1f}%'
            )
```

---

## 5. 에러 처리 방안

### 5.1 에러 코드 체계

```
Error Code Structure: XXXX-YYY

XXXX: Category
- 1000: Authentication/Authorization
- 2000: Validation
- 3000: External API (ADLOG)
- 4000: Database
- 5000: ML/Model
- 6000: Rate Limit
- 9000: Internal Server

YYY: Specific Error
```

### 5.2 에러 응답 형식

```json
{
    "success": false,
    "error": {
        "code": "3001-001",
        "type": "EXTERNAL_API_ERROR",
        "message": "외부 서비스 연결에 실패했습니다. 잠시 후 다시 시도해주세요.",
        "details": {
            "retry_after": 60,
            "fallback_available": true
        },
        "request_id": "req-uuid-xxx",
        "timestamp": "2026-01-10T10:00:00Z"
    }
}
```

### 5.3 주요 에러 시나리오 및 처리

```
+------------------+------------------+------------------+------------------+
| 시나리오          | 에러 코드         | 처리 방법         | 사용자 메시지     |
+------------------+------------------+------------------+------------------+
| ADLOG API 타임아웃 | 3001-001        | 재시도 3회 후     | "분석 서비스가    |
|                  |                  | 캐시 데이터 반환   | 일시적으로 지연   |
|                  |                  |                  | 됩니다"          |
+------------------+------------------+------------------+------------------+
| ADLOG API 500    | 3001-002        | 캐시 데이터 반환   | "최근 분석 결과를 |
|                  |                  | + 백그라운드 재시도 | 표시합니다"      |
+------------------+------------------+------------------+------------------+
| 키워드 검색 결과   | 2001-001        | 유사 키워드 제안   | "검색 결과가     |
| 없음             |                  |                  | 없습니다.        |
|                  |                  |                  | 다른 키워드를    |
|                  |                  |                  | 시도해보세요"    |
+------------------+------------------+------------------+------------------+
| 업체 not found   | 2001-002        | 전체 순위만 표시   | "해당 업체를     |
|                  |                  |                  | 찾을 수 없습니다" |
+------------------+------------------+------------------+------------------+
| DB 연결 실패      | 4001-001        | 캐시 fallback     | "서비스 점검 중  |
|                  |                  | + 알림 발송       | 입니다"          |
+------------------+------------------+------------------+------------------+
| 모델 로드 실패    | 5001-001        | 기본 모델 사용     | 내부 처리        |
|                  |                  |                  | (사용자 인지 X)  |
+------------------+------------------+------------------+------------------+
| Rate Limit 초과  | 6001-001        | 429 반환 +       | "요청이 너무     |
|                  |                  | Retry-After 헤더  | 많습니다. N초 후 |
|                  |                  |                  | 다시 시도하세요" |
+------------------+------------------+------------------+------------------+
```

### 5.4 재시도 정책

```python
class RetryPolicy:
    ADLOG_API = {
        'max_retries': 3,
        'initial_delay': 1,  # seconds
        'max_delay': 10,
        'exponential_base': 2,
        'jitter': True
    }

    DATABASE = {
        'max_retries': 5,
        'initial_delay': 0.5,
        'max_delay': 5,
        'exponential_base': 2,
        'jitter': True
    }

    @staticmethod
    def calculate_delay(attempt, policy):
        delay = min(
            policy['initial_delay'] * (policy['exponential_base'] ** attempt),
            policy['max_delay']
        )

        if policy['jitter']:
            delay *= (0.5 + random.random())

        return delay
```

### 5.5 Circuit Breaker 패턴

```python
class CircuitBreaker:
    def __init__(self, failure_threshold=5, recovery_timeout=60):
        self.failure_count = 0
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.state = 'CLOSED'  # CLOSED, OPEN, HALF_OPEN
        self.last_failure_time = None

    def call(self, func, *args, **kwargs):
        if self.state == 'OPEN':
            if self._should_attempt_reset():
                self.state = 'HALF_OPEN'
            else:
                raise CircuitBreakerOpen()

        try:
            result = func(*args, **kwargs)
            self._on_success()
            return result
        except Exception as e:
            self._on_failure()
            raise

    def _on_success(self):
        self.failure_count = 0
        self.state = 'CLOSED'

    def _on_failure(self):
        self.failure_count += 1
        self.last_failure_time = time.time()

        if self.failure_count >= self.failure_threshold:
            self.state = 'OPEN'

    def _should_attempt_reset(self):
        return time.time() - self.last_failure_time >= self.recovery_timeout

# Usage
adlog_circuit_breaker = CircuitBreaker(failure_threshold=5, recovery_timeout=60)
```

### 5.6 Fallback 전략

```python
class FallbackStrategy:
    def get_analysis_with_fallback(self, keyword, place_name):
        """분석 데이터 조회 with Fallback"""

        try:
            # 1차: 실시간 ADLOG API
            return self.adlog_service.fetch(keyword)

        except AdlogApiError:
            try:
                # 2차: 1시간 이내 캐시
                cached = self.cache.get(f'adlog:{keyword}')
                if cached and cached.age < 3600:
                    return cached.data
            except CacheError:
                pass

            try:
                # 3차: 오늘 DB 데이터
                db_data = self.db.query("""
                    SELECT * FROM daily_data
                    WHERE keyword = %s AND date = %s
                """, [keyword, date.today()])

                if db_data:
                    return self._convert_db_to_response(db_data)
            except DatabaseError:
                pass

            # 4차: 어제 DB 데이터
            yesterday_data = self.db.query("""
                SELECT * FROM daily_data
                WHERE keyword = %s AND date = %s
            """, [keyword, date.today() - timedelta(days=1)])

            if yesterday_data:
                return self._convert_db_to_response(yesterday_data, is_stale=True)

            # 최종: 서비스 불가
            raise ServiceUnavailableError()
```

---

## 6. 보안 고려사항

### 6.1 ADLOG API 숨김 처리

```
+------------------+     +------------------+     +------------------+
|  Client          |     |  Our Backend     |     |  ADLOG API       |
|  (Browser)       |     |  (Proxy)         |     |  (Hidden)        |
+------------------+     +------------------+     +------------------+
        |                        |                        |
        |  POST /api/analyze     |                        |
        |  (keyword only)        |                        |
        +----------------------->|                        |
        |                        |  POST placeAnalysis    |
        |                        |  (internal only)       |
        |                        +----------------------->|
        |                        |                        |
        |                        |<-----------------------+
        |                        |  Transform & Filter    |
        |<-----------------------+                        |
        |  (No ADLOG info)       |                        |
```

#### 6.1.1 API 프록시 구현

```python
# services/adlog_proxy.py

class AdlogProxyService:
    """ADLOG API를 완전히 숨기는 프록시 서비스"""

    def __init__(self):
        # 환경변수에서만 로드 (코드에 하드코딩 X)
        self._base_url = os.environ.get('ADLOG_API_URL')
        self._api_key = os.environ.get('ADLOG_API_KEY')

        if not self._base_url:
            raise ConfigurationError("ADLOG configuration missing")

    async def fetch_analysis(self, keyword: str) -> dict:
        """키워드 분석 데이터 조회"""

        # 1. 입력 검증
        keyword = self._sanitize_keyword(keyword)

        # 2. ADLOG API 호출 (내부)
        async with httpx.AsyncClient() as client:
            response = await client.post(
                self._base_url,
                json={"query": keyword},
                headers={"X-API-Key": self._api_key},
                timeout=10.0
            )

        # 3. 응답 변환 (ADLOG 정보 제거)
        raw_data = response.json()
        transformed = self._transform_response(raw_data)

        return transformed

    def _transform_response(self, raw: dict) -> dict:
        """응답에서 ADLOG 관련 정보 제거 및 변환"""

        # 원본 필드명을 우리 서비스 필드명으로 변환
        return {
            'places': [
                {
                    'place_id': p['place_id'],
                    'name': p['place_name'],
                    'rank': p['place_rank'],
                    'metrics': {
                        'blog_count': p['place_blog_cnt'],
                        'visit_count': p['place_visit_cnt'],
                        'save_count': p['place_save_cnt']
                    },
                    'scores': {
                        # N1, N2, N3 원본 노출 X
                        'keyword_score': self._convert_n1(p['place_index1']),
                        'quality_score': self._convert_n2(p['place_index2']),
                        'competition_score': self._convert_n3(p['place_index3'])
                    }
                }
                for p in raw.get('data', [])
            ]
        }

    def _sanitize_keyword(self, keyword: str) -> str:
        """키워드 입력 검증 및 정제"""

        # XSS, Injection 방지
        keyword = keyword.strip()
        keyword = re.sub(r'[<>"\';]', '', keyword)

        if len(keyword) > 50:
            keyword = keyword[:50]

        return keyword
```

#### 6.1.2 환경변수 관리

```bash
# .env.example (Git 추적 O)
ADLOG_API_URL=
ADLOG_API_KEY=

# .env.local (Git 추적 X - .gitignore에 추가)
ADLOG_API_URL=http://adlog.ai.kr/placeAnalysis.php
ADLOG_API_KEY=your-secret-key-here
```

```python
# core/config.py

from pydantic import BaseSettings, SecretStr

class Settings(BaseSettings):
    # ADLOG 설정 (외부 노출 X)
    adlog_api_url: SecretStr
    adlog_api_key: SecretStr

    # 공개 설정
    app_name: str = "Place Analytics"
    debug: bool = False

    class Config:
        env_file = ".env.local"
        case_sensitive = False

settings = Settings()
```

### 6.2 API 보안

#### 6.2.1 인증 및 인가

```python
# core/security.py

from jose import jwt, JWTError
from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

class SecurityService:
    def __init__(self):
        self.secret_key = os.environ.get('JWT_SECRET_KEY')
        self.algorithm = "HS256"
        self.access_token_expire = timedelta(hours=1)
        self.refresh_token_expire = timedelta(days=7)

    def create_access_token(self, user_id: str) -> str:
        expire = datetime.utcnow() + self.access_token_expire
        payload = {
            "sub": user_id,
            "exp": expire,
            "type": "access"
        }
        return jwt.encode(payload, self.secret_key, algorithm=self.algorithm)

    def verify_token(self, token: str) -> dict:
        try:
            payload = jwt.decode(token, self.secret_key, algorithms=[self.algorithm])
            return payload
        except JWTError:
            raise AuthenticationError("Invalid token")

    def hash_password(self, password: str) -> str:
        return pwd_context.hash(password)

    def verify_password(self, plain: str, hashed: str) -> bool:
        return pwd_context.verify(plain, hashed)
```

#### 6.2.2 Rate Limiting

```python
# middleware/rate_limit.py

from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)

# Rate Limit 규칙
RATE_LIMITS = {
    'analyze': '30/minute',      # 분석 API
    'history': '60/minute',      # 히스토리 조회
    'auth': '5/minute',          # 인증 관련
    'default': '100/minute'      # 기본
}

# 사용 예시
@app.post("/api/v1/analyze")
@limiter.limit(RATE_LIMITS['analyze'])
async def analyze(request: Request, data: AnalyzeRequest):
    ...
```

#### 6.2.3 입력 검증

```python
# models/schemas.py

from pydantic import BaseModel, validator, constr
import re

class AnalyzeRequest(BaseModel):
    keyword: constr(min_length=1, max_length=50)
    place_name: Optional[constr(max_length=100)] = None
    inflow: Optional[int] = None
    reservation: Optional[int] = None

    @validator('keyword')
    def validate_keyword(cls, v):
        # 허용 문자만
        if not re.match(r'^[가-힣a-zA-Z0-9\s]+$', v):
            raise ValueError('키워드에 허용되지 않는 문자가 포함되어 있습니다.')
        return v.strip()

    @validator('inflow', 'reservation')
    def validate_positive(cls, v):
        if v is not None and v < 0:
            raise ValueError('음수는 허용되지 않습니다.')
        if v is not None and v > 1000000:
            raise ValueError('값이 너무 큽니다.')
        return v
```

### 6.3 데이터 보안

#### 6.3.1 데이터베이스 보안

```sql
-- Row Level Security (Supabase)

-- 사용자는 자신의 데이터만 조회 가능
CREATE POLICY "Users can only view own places"
ON places
FOR SELECT
USING (auth.uid() = user_id);

-- 사용자는 자신의 데이터만 입력 가능
CREATE POLICY "Users can only insert own data"
ON daily_data
FOR INSERT
WITH CHECK (
    EXISTS (
        SELECT 1 FROM places
        WHERE places.place_id = daily_data.place_id
        AND places.user_id = auth.uid()
    )
);
```

#### 6.3.2 민감 데이터 처리

```python
# utils/encryption.py

from cryptography.fernet import Fernet

class EncryptionService:
    def __init__(self):
        self.key = os.environ.get('ENCRYPTION_KEY')
        self.cipher = Fernet(self.key)

    def encrypt(self, data: str) -> str:
        return self.cipher.encrypt(data.encode()).decode()

    def decrypt(self, encrypted: str) -> str:
        return self.cipher.decrypt(encrypted.encode()).decode()

# 민감 데이터 저장 시
encryption = EncryptionService()
encrypted_api_key = encryption.encrypt(user.api_key)
```

### 6.4 로깅 및 감사

```python
# utils/logger.py

import logging
from datetime import datetime

class AuditLogger:
    def __init__(self):
        self.logger = logging.getLogger('audit')

    def log_api_call(self, user_id: str, endpoint: str, params: dict, response_code: int):
        """API 호출 로깅 (민감 정보 제외)"""

        # 민감 정보 마스킹
        safe_params = self._mask_sensitive(params)

        log_entry = {
            'timestamp': datetime.utcnow().isoformat(),
            'user_id': user_id,
            'endpoint': endpoint,
            'params': safe_params,
            'response_code': response_code,
            'ip': self._get_client_ip()
        }

        self.logger.info(json.dumps(log_entry))

    def _mask_sensitive(self, params: dict) -> dict:
        """민감 정보 마스킹"""
        sensitive_keys = ['password', 'token', 'api_key']

        masked = {}
        for key, value in params.items():
            if key.lower() in sensitive_keys:
                masked[key] = '***MASKED***'
            else:
                masked[key] = value

        return masked
```

### 6.5 보안 체크리스트

```
+------------------+------------------+------------------+
| 항목              | 구현 방법         | 상태             |
+------------------+------------------+------------------+
| ADLOG API 숨김   | 서버사이드 프록시   | Required        |
| HTTPS 강제       | Redirect 설정     | Required        |
| JWT 인증         | Access/Refresh   | Required        |
| Rate Limiting    | slowapi          | Required        |
| 입력 검증        | Pydantic         | Required        |
| SQL Injection    | ORM 사용         | Required        |
| XSS 방지         | 출력 이스케이프   | Required        |
| CORS 설정        | 허용 도메인 제한  | Required        |
| 환경변수 관리     | .env.local       | Required        |
| 로그 마스킹      | AuditLogger      | Required        |
| DB RLS           | Supabase Policy  | Recommended     |
| WAF              | Cloudflare       | Recommended     |
| 데이터 암호화    | Fernet           | Optional        |
+------------------+------------------+------------------+
```

---

## 7. 폴더 구조 (최종)

```
place-analytics/
|
+-- backend/
|   +-- app/
|   |   +-- __init__.py
|   |   +-- main.py                 # FastAPI 앱 진입점
|   |   |
|   |   +-- api/
|   |   |   +-- __init__.py
|   |   |   +-- v1/
|   |   |       +-- __init__.py
|   |   |       +-- router.py       # API 라우터 통합
|   |   |       +-- analyze.py      # 분석 API
|   |   |       +-- history.py      # 히스토리 API
|   |   |       +-- model.py        # 모델 상태 API
|   |   |       +-- auth.py         # 인증 API
|   |   |       +-- competitors.py  # 경쟁사 API
|   |   |
|   |   +-- core/
|   |   |   +-- __init__.py
|   |   |   +-- config.py           # 환경 설정
|   |   |   +-- security.py         # 보안 유틸
|   |   |   +-- exceptions.py       # 커스텀 예외
|   |   |
|   |   +-- services/
|   |   |   +-- __init__.py
|   |   |   +-- adlog_proxy.py      # ADLOG 프록시
|   |   |   +-- score_converter.py  # 점수 변환
|   |   |   +-- analysis.py         # 분석 로직
|   |   |   +-- recommendation.py   # 제언 생성
|   |   |
|   |   +-- ml/
|   |   |   +-- __init__.py
|   |   |   +-- trainer.py          # 모델 학습
|   |   |   +-- predictor.py        # 예측
|   |   |   +-- feature_analyzer.py # 특성 분석
|   |   |   +-- scheduler.py        # 학습 스케줄러
|   |   |
|   |   +-- models/
|   |   |   +-- __init__.py
|   |   |   +-- database.py         # SQLAlchemy 모델
|   |   |   +-- schemas.py          # Pydantic 스키마
|   |   |
|   |   +-- middleware/
|   |   |   +-- __init__.py
|   |   |   +-- rate_limit.py       # Rate Limiting
|   |   |   +-- logging.py          # 요청 로깅
|   |   |
|   |   +-- utils/
|   |       +-- __init__.py
|   |       +-- logger.py           # 로깅 유틸
|   |       +-- encryption.py       # 암호화
|   |       +-- validators.py       # 검증 함수
|   |
|   +-- tests/
|   |   +-- __init__.py
|   |   +-- test_analyze.py
|   |   +-- test_ml.py
|   |   +-- conftest.py
|   |
|   +-- migrations/                  # Alembic 마이그레이션
|   +-- requirements.txt
|   +-- Dockerfile
|   +-- .env.example
|
+-- frontend/                        # Next.js (별도 기획)
+-- docs/
|   +-- BACKEND_PLAN.md             # 이 문서
|   +-- API_SPEC.md                 # API 상세 문서
|
+-- PROJECT_SPEC.md                 # 프로젝트 명세
+-- README.md
```

---

## 8. 개발 우선순위 (백엔드)

### Phase 1: MVP Core (1주)
1. FastAPI 프로젝트 구조 설정
2. ADLOG 프록시 서비스 구현
3. 점수 변환 로직 구현
4. 기본 분석 API 구현
5. DB 스키마 및 마이그레이션

### Phase 2: 데이터 수집 (1주)
1. 사용자 입력 저장 로직
2. 히스토리 API 구현
3. 캐싱 레이어 추가
4. 에러 처리 고도화

### Phase 3: ML 파이프라인 (1주)
1. 상관관계 분석 모듈
2. 모델 학습 파이프라인
3. 예측 서비스 구현
4. 학습 스케줄러 설정

### Phase 4: 고도화 (1주)
1. 마케팅 제언 생성 로직
2. 경쟁사 분석 API
3. 모니터링 및 알림
4. 성능 최적화

---

## 9. 부록: API 테스트 시나리오

```bash
# 1. 기본 분석 테스트
curl -X POST http://localhost:8000/api/v1/analyze \
  -H "Authorization: Bearer {token}" \
  -H "Content-Type: application/json" \
  -d '{"keyword": "홍대맛집", "place_name": "유메오뎅 홍대"}'

# 2. 사용자 데이터 포함 분석
curl -X POST http://localhost:8000/api/v1/analyze \
  -H "Authorization: Bearer {token}" \
  -H "Content-Type: application/json" \
  -d '{"keyword": "홍대맛집", "place_name": "유메오뎅 홍대", "inflow": 150, "reservation": 5}'

# 3. 히스토리 조회
curl -X GET "http://localhost:8000/api/v1/history?place_id=123&keyword=홍대맛집&days=30" \
  -H "Authorization: Bearer {token}"

# 4. 모델 상태 확인
curl -X GET http://localhost:8000/api/v1/model/status \
  -H "Authorization: Bearer {token}"
```

---

*문서 버전: 1.0*
*작성일: 2026-01-10*
*작성자: Backend Planning Team*
