"""
Training API
키워드 파라미터 학습 관련 엔드포인트

- 특정 키워드 수동 학습
- 전체 키워드 일괄 학습 (관리자용)
- 학습 상태 조회
- 학습 리포트 조회
- 정확도 분석
"""
from fastapi import APIRouter, HTTPException, Depends, Query, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional, List
from pydantic import BaseModel, Field
from datetime import datetime
import logging

from app.core.database import get_db
from app.core.scheduler import get_training_status, nightly_training_job
from app.ml.trainer import keyword_trainer
from app.ml.analyzer import model_analyzer

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/train", tags=["training"])


# ===========================================
# Response Schemas
# ===========================================

class TrainingResultResponse(BaseModel):
    """학습 결과 응답"""
    keyword: str
    success: bool
    is_reliable: Optional[bool] = None
    sample_count: int = 0
    n1_constant: Optional[float] = None
    n1_std: Optional[float] = None
    n2_slope: Optional[float] = None
    n2_intercept: Optional[float] = None
    n2_r_squared: Optional[float] = None
    error: Optional[str] = None


class BatchTrainingResultResponse(BaseModel):
    """일괄 학습 결과 응답"""
    success: bool
    total_keywords: int
    trained: int
    skipped: int
    reliable: int
    duration_seconds: float
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    errors: Optional[List[dict]] = None
    error_count: Optional[int] = None
    message: Optional[str] = None


class TrainingStatusResponse(BaseModel):
    """학습 상태 응답"""
    is_running: bool
    last_run_at: Optional[str] = None
    last_result: Optional[dict] = None


class TrainingReportResponse(BaseModel):
    """학습 리포트 응답"""
    parameters: dict
    training_data: dict
    last_trained_at: Optional[str] = None
    generated_at: str


class AccuracyAnalysisResponse(BaseModel):
    """정확도 분석 응답"""
    keyword: str
    success: bool
    sample_count: Optional[int] = None
    is_reliable: Optional[bool] = None
    overall_accuracy_percent: Optional[float] = None
    n1_metrics: Optional[dict] = None
    n2_metrics: Optional[dict] = None
    n3_metrics: Optional[dict] = None
    error: Optional[str] = None
    analyzed_at: Optional[str] = None


class AccuracyReportResponse(BaseModel):
    """전체 정확도 리포트 응답"""
    success: bool
    total_keywords: int
    analyzed_keywords: Optional[int] = None
    summary: Optional[dict] = None
    keywords: Optional[List[dict]] = None
    duration_seconds: Optional[float] = None
    generated_at: str
    message: Optional[str] = None


# ===========================================
# API Endpoints
# ===========================================

@router.post("/all", response_model=BatchTrainingResultResponse)
async def train_all(
    background_tasks: BackgroundTasks,
    sync: bool = Query(False, description="동기 실행 여부 (기본: 비동기)"),
    db: AsyncSession = Depends(get_db)
):
    """
    전체 키워드 학습 (관리자용)

    - sync=False: 백그라운드에서 비동기 실행 (즉시 응답)
    - sync=True: 동기 실행 (완료까지 대기)
    """
    logger.info(f"[Train API] Batch training requested (sync={sync})")

    if sync:
        # 동기 실행
        try:
            result = await keyword_trainer.train_all_keywords(db)

            return BatchTrainingResultResponse(
                success=result["success"],
                total_keywords=result["total_keywords"],
                trained=result["trained"],
                skipped=result["skipped"],
                reliable=result["reliable"],
                duration_seconds=result["duration_seconds"],
                started_at=result.get("started_at"),
                completed_at=result.get("completed_at"),
                errors=result.get("errors"),
                error_count=result.get("error_count"),
                message=result.get("message"),
            )

        except Exception as e:
            logger.error(f"[Train API] Batch training failed: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail=f"일괄 학습 실패: {str(e)}"
            )
    else:
        # 비동기 실행 (백그라운드)
        status = get_training_status()

        if status["is_running"]:
            raise HTTPException(
                status_code=409,
                detail="이미 학습 작업이 실행 중입니다."
            )

        background_tasks.add_task(nightly_training_job)

        return BatchTrainingResultResponse(
            success=True,
            total_keywords=0,
            trained=0,
            skipped=0,
            reliable=0,
            duration_seconds=0,
            message="백그라운드에서 학습을 시작했습니다. /train/status에서 상태를 확인하세요.",
        )


@router.post("/{keyword}", response_model=TrainingResultResponse)
async def train_keyword(
    keyword: str,
    db: AsyncSession = Depends(get_db)
):
    """
    특정 키워드 수동 학습

    - ADLOG 데이터에서 N1, N2 파라미터 추출
    - keyword_parameters 테이블에 저장
    """
    logger.info(f"[Train API] Manual training requested for keyword: {keyword}")

    try:
        result = await keyword_trainer.train_keyword(db, keyword)

        return TrainingResultResponse(
            keyword=result["keyword"],
            success=result["success"],
            is_reliable=result.get("is_reliable"),
            sample_count=result.get("sample_count", 0),
            n1_constant=result.get("n1_constant"),
            n1_std=result.get("n1_std"),
            n2_slope=result.get("n2_slope"),
            n2_intercept=result.get("n2_intercept"),
            n2_r_squared=result.get("n2_r_squared"),
            error=result.get("error"),
        )

    except Exception as e:
        logger.error(f"[Train API] Training failed for keyword '{keyword}': {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"학습 실패: {str(e)}"
        )


@router.get("/status", response_model=TrainingStatusResponse)
async def get_status():
    """
    학습 상태 조회

    - is_running: 현재 학습 중인지 여부
    - last_run_at: 마지막 학습 시간
    - last_result: 마지막 학습 결과
    """
    status = get_training_status()

    return TrainingStatusResponse(
        is_running=status["is_running"],
        last_run_at=status["last_run_at"],
        last_result=status["last_result"],
    )


@router.get("/report", response_model=TrainingReportResponse)
async def get_report(
    db: AsyncSession = Depends(get_db)
):
    """
    학습 리포트 조회

    - 키워드 파라미터 통계
    - 학습 데이터 통계
    - 마지막 학습 시간
    """
    try:
        report = await keyword_trainer.get_training_report(db)

        return TrainingReportResponse(
            parameters=report["parameters"],
            training_data=report["training_data"],
            last_trained_at=report["last_trained_at"],
            generated_at=report["generated_at"],
        )

    except Exception as e:
        logger.error(f"[Train API] Report generation failed: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"리포트 생성 실패: {str(e)}"
        )


@router.get("/accuracy/{keyword}", response_model=AccuracyAnalysisResponse)
async def analyze_keyword_accuracy(
    keyword: str,
    db: AsyncSession = Depends(get_db)
):
    """
    키워드별 정확도 분석

    - 예측값 vs 실제값 비교
    - MAE, RMSE, R² 계산
    """
    try:
        analysis = await model_analyzer.analyze_accuracy(db, keyword)

        return AccuracyAnalysisResponse(
            keyword=analysis["keyword"],
            success=analysis["success"],
            sample_count=analysis.get("sample_count"),
            is_reliable=analysis.get("is_reliable"),
            overall_accuracy_percent=analysis.get("overall_accuracy_percent"),
            n1_metrics=analysis.get("n1_metrics"),
            n2_metrics=analysis.get("n2_metrics"),
            n3_metrics=analysis.get("n3_metrics"),
            error=analysis.get("error"),
            analyzed_at=analysis.get("analyzed_at"),
        )

    except Exception as e:
        logger.error(f"[Train API] Accuracy analysis failed for '{keyword}': {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"정확도 분석 실패: {str(e)}"
        )


@router.get("/accuracy", response_model=AccuracyReportResponse)
async def get_accuracy_report(
    db: AsyncSession = Depends(get_db)
):
    """
    전체 정확도 리포트

    - 모든 신뢰 가능한 키워드에 대한 정확도 분석
    - 전체 통계 요약
    """
    try:
        report = await model_analyzer.generate_report(db)

        return AccuracyReportResponse(
            success=report["success"],
            total_keywords=report["total_keywords"],
            analyzed_keywords=report.get("analyzed_keywords"),
            summary=report.get("summary"),
            keywords=report.get("keywords"),
            duration_seconds=report.get("duration_seconds"),
            generated_at=report["generated_at"],
            message=report.get("message"),
        )

    except Exception as e:
        logger.error(f"[Train API] Accuracy report failed: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"정확도 리포트 생성 실패: {str(e)}"
        )


@router.get("/comparison/{keyword}")
async def get_keyword_comparison(
    keyword: str,
    limit: int = Query(20, ge=1, le=100, description="최대 개수"),
    db: AsyncSession = Depends(get_db)
):
    """
    키워드별 예측값 vs 실제값 상세 비교

    - 각 데이터 포인트에서 예측값과 실제값 비교
    - 에러율 계산
    """
    try:
        comparison = await model_analyzer.get_keyword_comparison(db, keyword, limit)

        return comparison

    except Exception as e:
        logger.error(f"[Train API] Comparison failed for '{keyword}': {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"비교 데이터 조회 실패: {str(e)}"
        )
