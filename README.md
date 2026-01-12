# Place Analytics - 네이버 플레이스 분석 도구

네이버 플레이스 순위 조회 및 분석 서비스입니다.

## 주요 기능

### 1. 플레이스 순위 조회
- 키워드별 플레이스 검색 순위 실시간 조회
- 최대 300위까지 순위 확인
- 경쟁 업체 리스트 및 비교

### 2. 플레이스 지수 분석
- 방문자 리뷰, 블로그 리뷰, 저장 수 기반 종합 점수 산출
- 경쟁사 대비 강점/약점 분석
- 개선 추천사항 제공

### 3. 히든 키워드 분석
- 플레이스가 상위 노출되고 있는 숨겨진 키워드 발굴
- 카테고리/지역 기반 연관 키워드 분석
- 키워드별 잠재력 평가

### 4. 순위 추적
- 키워드별 순위 변동 모니터링
- 히스토리 차트로 순위 추이 확인
- 최고 순위 기록

### 5. 종합 리포트
- 플레이스 종합 분석 리포트 생성
- 텍스트 파일 다운로드 지원

## 기술 스택

### Backend
- Python 3.9+
- FastAPI
- SQLAlchemy (SQLite)
- httpx, BeautifulSoup (크롤링)

### Frontend
- Next.js 15
- TypeScript
- Tailwind CSS
- shadcn/ui
- Recharts

## 설치 및 실행

### 1. Backend 설정

```bash
cd place-analytics/backend

# 가상환경 생성 (선택)
python -m venv venv
source venv/bin/activate  # Mac/Linux
# venv\Scripts\activate  # Windows

# 의존성 설치
pip install -r requirements.txt

# 서버 실행
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### 2. Frontend 설정

```bash
cd place-analytics/frontend

# 의존성 설치
npm install

# 개발 서버 실행
npm run dev
```

### 3. 접속
- Frontend: http://localhost:3000
- Backend API: http://localhost:8000
- API 문서: http://localhost:8000/docs

## API 엔드포인트

### 플레이스
- `POST /api/place/rank` - 순위 조회
- `GET /api/place/info/{place_id}` - 플레이스 정보
- `POST /api/place/analysis` - 종합 분석
- `POST /api/place/hidden-keywords` - 히든 키워드 분석
- `POST /api/place/report` - 리포트 생성

### 키워드 추적
- `POST /api/keywords/save` - 키워드 저장
- `GET /api/keywords/` - 저장된 키워드 목록
- `POST /api/keywords/{id}/refresh` - 순위 새로고침
- `GET /api/keywords/{id}/history` - 히스토리 조회

### 인증
- `POST /api/auth/register` - 회원가입
- `POST /api/auth/login` - 로그인
- `GET /api/auth/me` - 내 정보

## 프로젝트 구조

```
place-analytics/
├── backend/
│   ├── app/
│   │   ├── api/              # API 라우터
│   │   │   ├── place.py      # 플레이스 API
│   │   │   ├── keywords.py   # 키워드 API
│   │   │   └── auth.py       # 인증 API
│   │   ├── core/             # 설정
│   │   │   ├── config.py
│   │   │   └── database.py
│   │   ├── models/           # DB 모델
│   │   │   ├── place.py
│   │   │   └── user.py
│   │   ├── services/         # 비즈니스 로직
│   │   │   ├── naver_place.py    # 크롤링
│   │   │   └── place_analyzer.py # 분석
│   │   └── main.py
│   ├── requirements.txt
│   └── .env
│
├── frontend/
│   ├── src/
│   │   ├── app/
│   │   │   ├── page.tsx          # 순위 조회
│   │   │   ├── analysis/         # 지수 분석
│   │   │   ├── hidden-keywords/  # 히든 키워드
│   │   │   ├── tracking/         # 순위 추적
│   │   │   └── report/           # 리포트
│   │   ├── components/
│   │   │   ├── ui/               # shadcn 컴포넌트
│   │   │   └── layout/
│   │   └── lib/
│   │       └── api.ts            # API 클라이언트
│   ├── .env.local
│   └── package.json
│
└── README.md
```

## 환경 변수

### Backend (.env)
```
APP_NAME=Place Analytics
DEBUG=True
HOST=0.0.0.0
PORT=8000
DATABASE_URL=sqlite+aiosqlite:///./place_analytics.db
SECRET_KEY=your-secret-key
```

### Frontend (.env.local)
```
NEXT_PUBLIC_API_URL=http://localhost:8000/api
```

## 주의사항

- 네이버 플레이스 크롤링은 네이버 이용약관을 확인하세요
- 과도한 요청은 IP 차단 등의 문제가 발생할 수 있습니다
- Rate Limiting이 적용되어 있습니다 (기본 30회/분)

## 라이선스

MIT License
