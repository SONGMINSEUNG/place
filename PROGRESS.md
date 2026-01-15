# Place Analytics 프로젝트 진행 기록

## 2024-01-14 작업 내역

### 1. Dockerfile 배포 오류 수정
- 문제: `playwright install chromium --with-deps` 에러 (exit code 100)
- 원인: apt 캐시 삭제 후 --with-deps 옵션 사용 불가
- 해결: `--with-deps` 옵션 제거
- 커밋: `7c9b311`

### 2. N3 공식 역공학 및 최적화
- 기존 공식 정확도: 91.23% (R² = -292.65%)
- 새 공식 정확도: 99.16% (R² = 95.80%)
- 변경 파일: `backend/app/ml/predictor.py`
- 커밋: `6945218`

#### 새 N3 공식 (2차 다항식)
```python
n3 = (-0.288554
      + 3.350482 * n1
      + 0.159362 * n2
      + 0.438085 * n1 * n2
      - 3.715231 * n1**2
      - 0.851072 * n2**2)
```

### 3. N1, N2, N3 역공학 분석 결과

#### 정확도 요약
| 지수 | 정확도 | R² | 계산 방식 |
|------|--------|-----|-----------|
| N1 | 99.94% | 99.94% | 키워드별 상수값 |
| N2 | 99.10% | 99.10% | N2 = slope x rank + intercept |
| N3 | 99.97% | 99.97% | N3 = slope x N2 + intercept |

#### N1 키워드별 상수값
| 키워드 | N1 값 |
|--------|-------|
| 강남카페 | 0.3973 |
| 서울반지공방 | 0.4567 |
| 성남맞춤정장 | 0.4684 |
| 성수동맛집 | 0.3669 |
| 이태원술집 | 0.5563 |
| 판교맛집 | 0.3669 |

#### N2 키워드별 파라미터
| 키워드 | 기울기 (slope) | 절편 (intercept) |
|--------|----------------|------------------|
| 강남카페 | -0.00103 | 0.5506 |
| 서울반지공방 | -0.00519 | 0.4752 |
| 성남맞춤정장 | -0.01647 | 0.3807 |
| 성수동맛집 | -0.00100 | 0.5553 |
| 이태원술집 | -0.00209 | 0.5098 |
| 판교맛집 | -0.00138 | 0.5495 |

### 4. ADLOG API 의존성 제거 방안

#### 현재 상태
- ADLOG API에 완전 의존
- 매 요청마다 API 호출 필요

#### 개선 방안
- 키워드별 파라미터 테이블 생성
- 새 키워드만 1회 API 호출하여 파라미터 캐싱
- 이후 로컬 계산으로 N1, N2, N3 산출

#### 전체 파이프라인
```
입력: keyword + rank
  |
Step 1: N1 = keyword_params[keyword].n1_value
Step 2: N2 = keyword_params[keyword].n2_slope x rank + n2_intercept
Step 3: N3 = keyword_params[keyword].n3_slope x N2 + n3_intercept
  |
출력: N1, N2, N3 (99%+ 정확도)
```

---

## 🎯 궁극적 목표 (중요!)

### 현재 한계
- 현재 공식: `순위 → N2 → N3` (순위가 원인, N2가 결과)
- 불가능한 것: `블로그 리뷰 +10개 → N2 얼마나 상승?` (예측 불가)
- 이유: N2는 순위의 "결과"이지, 리뷰/유입수의 "결과"가 아님

### 궁극적으로 달성해야 할 것
```
블로그 리뷰 +10개 → 평균 2순위 상승 → N3 +1.5점
```
이런 패턴을 발견하려면 **시계열 데이터 학습**이 필요함

### 학습 데이터 수집 방법
```
1일차: 블로그 10개, 순위 7위
       ↓ 사용자 입력: "블로그 5개 추가함"
7일차: 블로그 15개, 순위 5위
       ↓
학습: "블로그 +5개 → 2순위 상승" 패턴 발견
```

**핵심: 사용자가 행동을 기입하면 그게 학습 데이터가 됨**

---

## 현재 시뮬레이션 문제점

### 문제 1: 인과관계 역전
- 현재 가정: `리뷰 증가 → N2 상승 → 순위 상승`
- 실제 로직: `순위 → N2 결정` (N2는 순위의 결과)

### 문제 2: 근거 없는 계수
```python
DEFAULT_COEFFICIENTS = {
    "blog_review": 0.002143,   # 근거 없음
    "visit_review": 0.000598,  # 근거 없음
}
```

### 개선 방향
1. ❌ 예약 건수 입력 삭제
2. ✅ 유입수 입력 유지 (경쟁 분석용)
3. 🔄 시뮬레이션: "목표 순위" 기반으로 변경
4. ➕ 사용자 행동 기입 기능 추가 (학습 데이터 수집)

---

## 구현 완료 (2024-01-15)

### Phase 1: 키워드 파라미터 시스템 ✅ (89점)
- [x] `KeywordParameter` 테이블 생성
- [x] ADLOG API 최초 1회 호출 → 파라미터 캐싱
- [x] 이후 자체 계산으로 N1, N2, N3 산출 (99% 정확도)

**구현 파일:**
- `backend/app/models/place.py` - KeywordParameter 모델
- `backend/app/services/parameter_extractor.py` - 파라미터 추출
- `backend/app/services/formula_calculator.py` - 자체 계산
- `backend/app/api/v1/parameters.py` - 파라미터 관리 API

### Phase 2: 새벽 자동 학습 시스템 ✅ (89점)
- [x] trainer.py 구현
- [x] analyzer.py 구현
- [x] 새벽 2시 cron job 설정
- [x] 수집된 데이터로 공식 계수 자동 최적화

**구현 파일:**
- `backend/app/ml/trainer.py` - 키워드 학습
- `backend/app/ml/analyzer.py` - 정확도 분석
- `backend/app/core/scheduler.py` - 새벽 2시 cron job
- `backend/app/api/v1/train.py` - 학습 API

### Phase 3: 시뮬레이션 개선 ✅ (88점)
- [x] 예약 건수 입력 필드 삭제
- [x] 유입수 입력 필드 삭제
- [x] 마케팅 제언 섹션 삭제
- [x] 목표 순위 기반 시뮬레이션으로 변경
- [x] 50위까지 전체 표시 (10위 → 50위)
- [x] 시뮬레이션 N3 감소 버그 수정

**구현 파일:**
- `backend/app/api/v1/simulate.py` - 목표 순위 시뮬레이션 API
- `frontend/src/app/inquiry/page.tsx` - UI 개선

### Phase 4: 시계열 학습 ✅ (82점)
- [x] 사용자 행동 기입 기능 추가
- [x] "오늘 어떤 작업을 하셨나요?" UI (조회 전 위치)
- [x] 행동 → 순위 변화 상관관계 분석
- [x] "블로그 +N개 → 평균 X순위 상승" 패턴 학습

**구현 파일:**
- `backend/app/api/v1/activity.py` - 활동 기록 API
- `backend/app/ml/correlation_analyzer.py` - 상관관계 분석
- `frontend/src/app/inquiry/page.tsx` - 활동 기입 UI

---

## 버그 수정 (2024-01-15)

| 이슈 | 상태 |
|------|------|
| 유입수 입력 칸 제거 | ✅ 완료 |
| "오늘 작업" UI 위치 (조회 전으로 이동) | ✅ 완료 |
| 시뮬레이션 N3 감소 버그 | ✅ 완료 |
| 마케팅 제언 섹션 삭제 | ✅ 완료 |
| 10위 → 50위까지 표시 | ✅ 완료 |

---

## 알려진 이슈

### 속도 느림 (Cold Start)
- **원인**: Render.com 무료 티어 - 15분 비활성 시 서버 종료
- **증상**: 첫 요청 시 30초+ 대기
- **해결 방법**:
  1. UptimeRobot으로 주기적 ping (무료)
  2. Render 유료 플랜 (월 $7)
  3. Railway/Fly.io로 이전

---

## 다음 단계

- [ ] Cold Start 해결 (UptimeRobot 또는 유료 플랜)
- [ ] 사용자 데이터 수집 시작
- [ ] 충분한 데이터 축적 후 상관관계 분석 결과 확인

---

## 배포 정보
- Frontend: Vercel
- Backend: Render.com
- GitHub: https://github.com/SONGMINSEUNG/place.git
