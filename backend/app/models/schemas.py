"""
Pydantic Schemas
API 요청/응답 스키마 정의
"""
from pydantic import BaseModel, Field, validator
from typing import Optional, List, Dict, Any
from datetime import datetime
import re


# ===========================================
# Request Schemas
# ===========================================

class AnalyzeRequest(BaseModel):
    """분석 요청"""
    keyword: str = Field(..., min_length=1, max_length=50, description="검색 키워드")
    place_name: Optional[str] = Field(None, max_length=100, description="업체명 (선택)")
    inflow: Optional[int] = Field(None, ge=0, le=1000000, description="오늘 유입수")

    @validator('keyword')
    def validate_keyword(cls, v):
        if not re.match(r'^[가-힣a-zA-Z0-9\s]+$', v):
            raise ValueError('키워드에 허용되지 않는 문자가 포함되어 있습니다.')
        return v.strip()

    @validator('place_name')
    def validate_place_name(cls, v):
        if v:
            return v.strip()
        return v


class SimulateInputs(BaseModel):
    """시뮬레이션 입력 항목"""
    inflow: int = Field(0, ge=0, le=10000, description="유입수 추가")
    blog_review: int = Field(0, ge=0, le=500, description="블로그 리뷰 추가")
    visit_review: int = Field(0, ge=0, le=1000, description="방문자 리뷰 추가")


class SimulateRequest(BaseModel):
    """시뮬레이션 요청"""
    keyword: str = Field(..., min_length=1, max_length=50)
    place_name: str = Field(..., min_length=1, max_length=100)
    inputs: SimulateInputs


class UserDataInput(BaseModel):
    """사용자 데이터 입력 (일간)"""
    place_id: str
    keyword: str
    date: Optional[datetime] = None
    inflow: int = Field(..., ge=0, description="일간 유입수")


# ===========================================
# Response Schemas
# ===========================================

class ScoresResponse(BaseModel):
    """점수 응답 (소수점 4자리)"""
    quality_score: float = Field(..., description="품질점수 (N2 기반)")
    keyword_score: float = Field(..., description="키워드지수 (N1 기반)")
    competition_score: float = Field(..., description="종합경쟁력 (N3 기반)")


class MetricsResponse(BaseModel):
    """지표 응답"""
    blog_count: int = Field(..., description="블로그 리뷰 수")
    visit_count: int = Field(..., description="방문자 리뷰 수")
    save_count: int = Field(..., description="저장 수")


class ChangesResponse(BaseModel):
    """변화량 응답"""
    rank_change: int = Field(..., description="순위 변화")
    score_change: float = Field(..., description="점수 변화")


class PlaceResponse(BaseModel):
    """업체 정보 응답"""
    place_id: str
    name: str
    rank: int
    scores: ScoresResponse
    metrics: MetricsResponse
    changes: ChangesResponse


class ComparisonResponse(BaseModel):
    """비교 분석 응답"""
    rank_1_gap: float = Field(..., description="1위와 점수 차이")
    rank_1_score: float = Field(..., description="1위 점수")


class RecommendationItem(BaseModel):
    """추천 전략 항목"""
    type: str = Field(..., description="유입수, 예약수, 블로그리뷰, 방문자리뷰")
    amount: int = Field(..., description="추천 개수")
    unit: str = Field(..., description="단위 (명, 건, 개)")
    effect: float = Field(..., description="예상 N2 점수 증가")
    description: Optional[str] = Field(None, description="N3 상승 효과 설명")
    n3_effect: Optional[float] = Field(None, description="예상 N3 점수 증가")


class CompetitorResponse(BaseModel):
    """경쟁사 정보"""
    rank: int
    name: str
    score: float


class AnalyzeResponse(BaseModel):
    """분석 결과 응답"""
    keyword: str
    my_place: Optional[PlaceResponse] = None
    comparison: Optional[ComparisonResponse] = None
    recommendations: List[RecommendationItem] = []
    competitors: List[CompetitorResponse] = []
    all_places: List[PlaceResponse] = []
    data_source: str = Field("api", description="데이터 소스 (api: ADLOG API, cache: 캐싱된 파라미터)")


class SimulateEffectItem(BaseModel):
    """시뮬레이션 효과 항목"""
    amount: int
    effect: float


class SimulateResponse(BaseModel):
    """시뮬레이션 결과 응답"""
    current_score: float = Field(..., description="현재 품질점수 (N2)")
    current_rank: int
    effects: Dict[str, SimulateEffectItem]
    total_effect: float = Field(..., description="N2 변화량")
    predicted_score: float = Field(..., description="예상 품질점수 (N2)")
    predicted_rank: int
    # N3 관련 필드 추가
    current_n3: Optional[float] = Field(None, description="현재 경쟁력점수 (N3)")
    predicted_n3: Optional[float] = Field(None, description="예상 경쟁력점수 (N3)")
    n3_change: Optional[float] = Field(None, description="N3 변화량 (순위 결정 핵심 지표)")


# ===========================================
# Error Response
# ===========================================

class ErrorDetail(BaseModel):
    """에러 상세"""
    code: str
    type: str
    message: str


class ErrorResponse(BaseModel):
    """에러 응답"""
    success: bool = False
    error: ErrorDetail


class SuccessResponse(BaseModel):
    """성공 응답 래퍼"""
    success: bool = True
    data: Any


# ===========================================
# 사용자 데이터 입력 Schemas
# ===========================================

class SubmitDataRequest(BaseModel):
    """사용자 데이터 제출 요청"""
    keyword: str = Field(..., min_length=1, max_length=50, description="검색 키워드")
    place_id: str = Field(..., min_length=1, max_length=50, description="플레이스 ID")
    place_name: Optional[str] = Field(None, max_length=255, description="업체명")
    inflow: int = Field(..., ge=0, le=1000000, description="유입수")

    @validator('keyword')
    def validate_keyword(cls, v):
        if not re.match(r'^[가-힣a-zA-Z0-9\s]+$', v):
            raise ValueError('키워드에 허용되지 않는 문자가 포함되어 있습니다.')
        return v.strip()


class SubmitDataResponse(BaseModel):
    """사용자 데이터 제출 응답"""
    success: bool = True
    data_id: int
    keyword: str
    place_id: str
    place_name: Optional[str]
    inflow: int
    n2: Optional[float] = None
    rank: Optional[int] = None
    created_at: datetime


class CorrelationResult(BaseModel):
    """상관관계 결과"""
    variable1: str
    variable2: str
    correlation: float = Field(..., description="상관계수 (-1 ~ 1)")
    p_value: float = Field(..., description="p-value (0.05 이하면 유의미)")
    is_significant: bool = Field(..., description="통계적 유의성")
    sample_size: int = Field(..., description="샘플 수")


class CorrelationResponse(BaseModel):
    """상관관계 분석 응답"""
    inflow_n2: CorrelationResult
    inflow_rank: CorrelationResult
    total_samples: int
    analysis_date: datetime
    interpretation: str = Field(..., description="분석 해석")
