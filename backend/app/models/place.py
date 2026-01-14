from sqlalchemy import Column, Integer, String, DateTime, Float, Text, ForeignKey, JSON, Boolean, Date
from sqlalchemy.orm import relationship
from datetime import datetime, date
from app.core.database import Base


class Place(Base):
    """플레이스 정보 캐시 테이블"""
    __tablename__ = "places"

    id = Column(Integer, primary_key=True, index=True)
    place_id = Column(String(50), unique=True, index=True, nullable=False)  # 네이버 플레이스 ID
    name = Column(String(255), nullable=False)
    category = Column(String(100), nullable=True)
    address = Column(String(500), nullable=True)
    road_address = Column(String(500), nullable=True)
    phone = Column(String(50), nullable=True)

    # 리뷰 및 지표
    visitor_review_count = Column(Integer, default=0)
    blog_review_count = Column(Integer, default=0)
    reservation_review_count = Column(Integer, default=0)
    save_count = Column(Integer, default=0)
    photo_count = Column(Integer, default=0)

    # 플레이스 지수
    place_score = Column(Float, nullable=True)

    # 추가 정보
    description = Column(Text, nullable=True)
    menu_info = Column(JSON, nullable=True)  # [{"name": "메뉴명", "price": "가격"}]
    keywords = Column(JSON, nullable=True)  # ["키워드1", "키워드2"]
    business_hours = Column(JSON, nullable=True)
    thumbnail_url = Column(String(500), nullable=True)

    # 타임스탬프
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    rank_history = relationship("RankHistory", back_populates="place")


class PlaceSearch(Base):
    """검색 기록 테이블"""
    __tablename__ = "place_searches"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    place_id = Column(String(50), index=True, nullable=False)
    keyword = Column(String(255), nullable=False)
    rank = Column(Integer, nullable=True)  # 순위 (없으면 300위 밖)
    total_results = Column(Integer, nullable=True)
    searched_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    user = relationship("User", back_populates="search_history")


class RankHistory(Base):
    """순위 히스토리 테이블"""
    __tablename__ = "rank_history"

    id = Column(Integer, primary_key=True, index=True)
    place_id = Column(String(50), ForeignKey("places.place_id"), nullable=False)
    keyword = Column(String(255), nullable=False, index=True)
    rank = Column(Integer, nullable=True)
    total_results = Column(Integer, nullable=True)

    # 일별 스냅샷 데이터
    visitor_review_count = Column(Integer, default=0)
    blog_review_count = Column(Integer, default=0)
    place_score = Column(Float, nullable=True)

    checked_at = Column(DateTime, default=datetime.utcnow, index=True)

    # Relationships
    place = relationship("Place", back_populates="rank_history")


class SavedKeyword(Base):
    """저장된 키워드 (순위 추적용)"""
    __tablename__ = "saved_keywords"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    place_id = Column(String(50), nullable=False, index=True)
    place_name = Column(String(255), nullable=True)
    keyword = Column(String(255), nullable=False)
    last_rank = Column(Integer, nullable=True)
    best_rank = Column(Integer, nullable=True)

    # 플레이스 정보
    visitor_review_count = Column(Integer, default=0)
    blog_review_count = Column(Integer, default=0)
    place_score = Column(Float, nullable=True)

    is_active = Column(Integer, default=True)  # 활성화 여부
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    user = relationship("User", back_populates="saved_keywords")


class PlaceStats(Base):
    """플레이스 일별 통계 (리뷰 수, 저장 수 변화 추적)"""
    __tablename__ = "place_stats"

    id = Column(Integer, primary_key=True, index=True)
    place_id = Column(String(50), nullable=False, index=True)
    place_name = Column(String(255), nullable=True)

    # 일별 스냅샷 데이터
    visitor_review_count = Column(Integer, default=0)
    blog_review_count = Column(Integer, default=0)
    save_count = Column(Integer, default=0)

    # 날짜 (하루에 한 번 기록)
    date = Column(DateTime, nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class TrackedPlace(Base):
    """자동 추적 대상 플레이스"""
    __tablename__ = "tracked_places"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    place_id = Column(String(50), nullable=False, index=True)
    place_name = Column(String(255), nullable=True)
    keywords = Column(JSON, nullable=True)  # ["키워드1", "키워드2"] - 순위 추적할 키워드들
    is_active = Column(Integer, default=1)  # 1: 활성, 0: 비활성
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class KeywordFactorAnalysis(Base):
    """키워드별 순위 영향 요소 분석 기록"""
    __tablename__ = "keyword_factor_analysis"

    id = Column(Integer, primary_key=True, index=True)
    keyword = Column(String(255), nullable=False, index=True)

    # 분석 데이터
    analyzed_places = Column(Integer, default=0)

    # 각 요소별 상관계수
    visitor_review_correlation = Column(Float, default=0)
    blog_review_correlation = Column(Float, default=0)
    save_count_correlation = Column(Float, default=0)

    # 각 요소별 영향력 (%)
    visitor_review_impact = Column(Float, default=0)
    blog_review_impact = Column(Float, default=0)
    save_count_impact = Column(Float, default=0)

    # 가장 영향력 높은 요소
    top_factor = Column(String(50), nullable=True)  # visitor_review, blog_review, save_count

    # 분석 시간
    analyzed_at = Column(DateTime, default=datetime.utcnow, index=True)


class KeywordSearchLog(Base):
    """키워드 검색 로그 (인기 키워드 집계용)"""
    __tablename__ = "keyword_search_logs"

    id = Column(Integer, primary_key=True, index=True)
    keyword = Column(String(255), nullable=False, index=True)
    search_count = Column(Integer, default=1)  # 검색 횟수
    last_searched_at = Column(DateTime, default=datetime.utcnow, index=True)
    date = Column(DateTime, nullable=False, index=True)  # 날짜별 집계용


class KeywordRankSnapshot(Base):
    """키워드별 순위 스냅샷 (누적 데이터 분석용)"""
    __tablename__ = "keyword_rank_snapshots"

    id = Column(Integer, primary_key=True, index=True)
    keyword = Column(String(255), nullable=False, index=True)

    # 순위 데이터 (JSON으로 상위 50개 저장)
    # [{"rank": 1, "place_id": "123", "name": "업체명", "visitor_review_count": 100, ...}, ...]
    rank_data = Column(JSON, nullable=True)
    total_places = Column(Integer, default=0)

    # 스냅샷 시간
    snapshot_at = Column(DateTime, default=datetime.utcnow, index=True)


class PlaceSaveTracker(Base):
    """플레이스 저장 체크 - 키워드별 플레이스 저장수 추적"""
    __tablename__ = "place_save_trackers"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)

    # 플레이스 정보
    place_id = Column(String(50), nullable=False, index=True)
    place_name = Column(String(255), nullable=True)
    place_url = Column(String(500), nullable=True)

    # 검색 키워드
    keyword = Column(String(255), nullable=False, index=True)

    # 그룹 (분류용)
    group_name = Column(String(100), default="기본")

    # 최신 데이터
    current_rank = Column(Integer, nullable=True)  # 현재 순위
    current_save_count = Column(Integer, default=0)  # 현재 저장수
    visitor_review_count = Column(Integer, default=0)
    blog_review_count = Column(Integer, default=0)

    # 메모
    memo = Column(Text, nullable=True)

    # 상태
    is_active = Column(Integer, default=1)  # 1: 활성, 0: 비활성

    # 타임스탬프
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_checked_at = Column(DateTime, nullable=True)  # 마지막 체크 시간

    # Relationships
    history = relationship("PlaceSaveHistory", back_populates="tracker", cascade="all, delete-orphan")


class PlaceSaveHistory(Base):
    """플레이스 저장수 히스토리 (주간 자동 기록)"""
    __tablename__ = "place_save_history"

    id = Column(Integer, primary_key=True, index=True)
    tracker_id = Column(Integer, ForeignKey("place_save_trackers.id"), nullable=False)

    # 기록 데이터
    rank = Column(Integer, nullable=True)
    save_count = Column(Integer, default=0)
    visitor_review_count = Column(Integer, default=0)
    blog_review_count = Column(Integer, default=0)

    # 변화량 (이전 기록 대비)
    rank_change = Column(Integer, nullable=True)  # 양수면 순위 상승
    save_change = Column(Integer, nullable=True)  # 저장수 변화
    visitor_review_change = Column(Integer, nullable=True)
    blog_review_change = Column(Integer, nullable=True)

    # 기록 시간
    recorded_at = Column(DateTime, default=datetime.utcnow, index=True)

    # Relationships
    tracker = relationship("PlaceSaveTracker", back_populates="history")


class AdlogTrainingData(Base):
    """
    ADLOG API 응답 데이터 저장 (딥러닝 학습용)
    - 30일간 보관 후 자동 삭제 예정
    - N1, N2, N3, V(방문자리뷰), B(블로그리뷰), S(저장수) 등 저장
    """
    __tablename__ = "adlog_training_data"

    id = Column(Integer, primary_key=True, index=True)

    # 검색 키워드
    keyword = Column(String(255), nullable=False, index=True)

    # 플레이스 정보
    place_id = Column(String(50), nullable=False, index=True)
    place_name = Column(String(255), nullable=True)

    # 순위 정보
    rank = Column(Integer, nullable=True, index=True)
    rank_change = Column(Integer, nullable=True)  # 순위 변동

    # ADLOG 지수 (N1, N2, N3)
    index_n1 = Column(Float, default=0)  # place_index1
    index_n2 = Column(Float, default=0)  # place_index2
    index_n3 = Column(Float, default=0)  # place_index3
    index_n2_change = Column(Float, default=0)  # N2 변동값

    # 메트릭스 (V, B, S)
    visitor_review_count = Column(Integer, default=0)  # V: 방문자 리뷰 수
    blog_review_count = Column(Integer, default=0)     # B: 블로그 리뷰 수
    save_count = Column(Integer, default=0)            # S: 저장 수

    # 수집 시간
    collected_at = Column(DateTime, default=datetime.utcnow, index=True)

    # 만료일 (30일 후 삭제 대상)
    expires_at = Column(DateTime, nullable=False, index=True)


class UserInputData(Base):
    """
    사용자 입력 데이터 (유입수, 예약수) + ADLOG N2 값
    - 상관관계 분석을 위한 데이터 수집용
    """
    __tablename__ = "user_input_data"

    id = Column(Integer, primary_key=True, index=True)

    # 사용자 정보
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)

    # 검색 키워드
    keyword = Column(String(255), nullable=False, index=True)

    # 플레이스 정보
    place_id = Column(String(50), nullable=False, index=True)
    place_name = Column(String(255), nullable=True)

    # 사용자 입력 데이터
    inflow = Column(Integer, nullable=False)  # 유입수
    # reservation 컬럼은 deprecated (하위 호환성을 위해 유지하되 사용하지 않음)
    reservation = Column(Integer, nullable=True, default=0)  # deprecated

    # ADLOG에서 가져온 값
    n1 = Column(Float, nullable=True)  # 키워드 지수
    n2 = Column(Float, nullable=True)  # 품질 점수
    n3 = Column(Float, nullable=True)  # 종합 경쟁력
    rank = Column(Integer, nullable=True)  # 현재 순위

    # 메트릭스 (ADLOG에서 가져온 값)
    visitor_review_count = Column(Integer, default=0)
    blog_review_count = Column(Integer, default=0)
    save_count = Column(Integer, default=0)

    # 타임스탬프
    created_at = Column(DateTime, default=datetime.utcnow, index=True)

    # Relationships
    user = relationship("User", back_populates="input_data")


class KeywordParameter(Base):
    """
    키워드별 파라미터 캐시 테이블
    - ADLOG API 응답에서 추출한 N1, N2 파라미터 저장
    - API 호출 없이 자체 계산에 활용
    """
    __tablename__ = "keyword_parameters"

    id = Column(Integer, primary_key=True, index=True)
    keyword = Column(String(255), unique=True, nullable=False, index=True)

    # N1 파라미터 (키워드별 고정 상수 - 평균값)
    n1_constant = Column(Float, nullable=True)
    n1_std = Column(Float, nullable=True)  # 표준편차 (신뢰도 판단용)

    # N2 파라미터 (N2 = slope * rank + intercept)
    n2_slope = Column(Float, nullable=True)
    n2_intercept = Column(Float, nullable=True)
    n2_r_squared = Column(Float, nullable=True)  # 결정계수 (모델 적합도)

    # 메타데이터
    sample_count = Column(Integer, default=0)  # 학습에 사용된 샘플 수
    last_trained_at = Column(DateTime, nullable=True)  # 마지막 학습 시간
    api_call_count = Column(Integer, default=0)  # 총 API 호출 횟수
    cache_hit_count = Column(Integer, default=0)  # 캐시 히트 횟수
    is_reliable = Column(Boolean, default=False)  # 신뢰성 (sample_count >= 10)

    # 타임스탬프
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class UserActivityLog(Base):
    """
    사용자 마케팅 활동 로그 테이블
    - 블로그 리뷰, 방문자 리뷰, 저장수 증가, 유입수 증가 등 활동 기록
    - D+1, D+7 결과 추적으로 활동-순위 상관관계 학습
    """
    __tablename__ = "user_activity_logs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    keyword = Column(String(255), nullable=False, index=True)
    place_id = Column(String(50), nullable=True, index=True)
    place_name = Column(String(255), nullable=True)
    activity_date = Column(Date, nullable=False, index=True)

    # 사용자가 기입한 활동 내역
    blog_review_added = Column(Integer, default=0)  # 추가한 블로그 리뷰 수
    visit_review_added = Column(Integer, default=0)  # 추가한 방문자 리뷰 수
    save_added = Column(Integer, default=0)  # 증가한 저장수
    inflow_added = Column(Integer, default=0)  # 증가한 유입수

    # 당시 순위/지수 스냅샷
    rank_before = Column(Integer, nullable=True)
    n1_before = Column(Float, nullable=True)
    n2_before = Column(Float, nullable=True)
    n3_before = Column(Float, nullable=True)

    # D+1 결과 (다음날 업데이트)
    rank_after_1d = Column(Integer, nullable=True)
    n3_after_1d = Column(Float, nullable=True)
    measured_at_1d = Column(DateTime, nullable=True)

    # D+7 결과 (7일 후 업데이트)
    rank_after_7d = Column(Integer, nullable=True)
    n3_after_7d = Column(Float, nullable=True)
    measured_at_7d = Column(DateTime, nullable=True)

    # 타임스탬프
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    user = relationship("User", back_populates="activity_logs")
