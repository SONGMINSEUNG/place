"""
키워드 파라미터 자동 학습 모듈

기능:
1. 저장된 ADLOG 데이터로 N1, N2 파라미터 재학습
2. 학습 결과를 keyword_parameters 테이블에 저장
3. 정확도 검증 및 리포트 생성
"""
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime

import numpy as np
from scipy import stats
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, distinct

from app.models.place import KeywordParameter, AdlogTrainingData
from app.services.parameter_extractor import parameter_extractor, parameter_repository

logger = logging.getLogger(__name__)


# 학습 설정
MIN_SAMPLES = 10  # 최소 샘플 수
MIN_R_SQUARED = 0.3  # 최소 결정계수


class KeywordTrainer:
    """키워드별 N1, N2 파라미터 자동 학습"""

    def __init__(self):
        self.min_samples = MIN_SAMPLES
        self.min_r_squared = MIN_R_SQUARED

    async def get_training_data(
        self,
        db: AsyncSession,
        keyword: str
    ) -> List[AdlogTrainingData]:
        """
        특정 키워드의 학습 데이터 조회

        Args:
            db: DB 세션
            keyword: 검색 키워드

        Returns:
            학습 데이터 리스트
        """
        result = await db.execute(
            select(AdlogTrainingData)
            .where(AdlogTrainingData.keyword == keyword)
            .order_by(AdlogTrainingData.collected_at.desc())
        )
        return result.scalars().all()

    def calculate_n1_from_data(
        self,
        training_data: List[AdlogTrainingData]
    ) -> Dict[str, Optional[float]]:
        """
        학습 데이터에서 N1 파라미터 계산

        N1은 키워드별 고정 상수 (평균값)

        Args:
            training_data: 학습 데이터 리스트

        Returns:
            {"n1_constant": float, "n1_std": float}
        """
        n1_values = []

        for data in training_data:
            if data.index_n1 is not None and data.index_n1 > 0:
                n1_values.append(data.index_n1)

        if not n1_values:
            logger.warning("No valid N1 values found in training data")
            return {"n1_constant": None, "n1_std": None}

        n1_constant = float(np.mean(n1_values))
        n1_std = float(np.std(n1_values)) if len(n1_values) > 1 else 0.0

        logger.info(f"N1 calculated: mean={n1_constant:.4f}, std={n1_std:.4f}, count={len(n1_values)}")
        return {"n1_constant": n1_constant, "n1_std": n1_std}

    def calculate_n2_from_data(
        self,
        training_data: List[AdlogTrainingData]
    ) -> Dict[str, Optional[float]]:
        """
        학습 데이터에서 N2 파라미터 계산 (선형 회귀)

        N2 = slope * rank + intercept

        Args:
            training_data: 학습 데이터 리스트

        Returns:
            {"n2_slope": float, "n2_intercept": float, "n2_r_squared": float}
        """
        ranks = []
        n2_values = []

        for data in training_data:
            if (
                data.rank is not None and
                data.index_n2 is not None and
                data.rank > 0
            ):
                ranks.append(data.rank)
                n2_values.append(data.index_n2)

        if len(ranks) < 3:
            logger.warning(f"Not enough data points for N2 regression: {len(ranks)} points")
            return {"n2_slope": None, "n2_intercept": None, "n2_r_squared": None}

        try:
            # scipy.stats.linregress 사용
            slope, intercept, r_value, p_value, std_err = stats.linregress(ranks, n2_values)
            r_squared = r_value ** 2

            logger.info(
                f"N2 regression: slope={slope:.6f}, intercept={intercept:.4f}, "
                f"R²={r_squared:.4f}, count={len(ranks)}"
            )

            return {
                "n2_slope": float(slope),
                "n2_intercept": float(intercept),
                "n2_r_squared": float(r_squared),
            }

        except Exception as e:
            logger.error(f"N2 regression failed: {str(e)}")
            return {"n2_slope": None, "n2_intercept": None, "n2_r_squared": None}

    async def train_keyword(
        self,
        db: AsyncSession,
        keyword: str
    ) -> Dict[str, Any]:
        """
        특정 키워드 학습

        Args:
            db: DB 세션
            keyword: 검색 키워드

        Returns:
            학습 결과 딕셔너리
        """
        logger.info(f"Training keyword: {keyword}")

        # 1. 학습 데이터 조회
        training_data = await self.get_training_data(db, keyword)

        if len(training_data) < self.min_samples:
            logger.warning(
                f"Not enough samples for keyword '{keyword}': "
                f"{len(training_data)} < {self.min_samples}"
            )
            return {
                "keyword": keyword,
                "success": False,
                "error": f"샘플 부족 ({len(training_data)} < {self.min_samples})",
                "sample_count": len(training_data),
            }

        # 2. N1 파라미터 계산
        n1_params = self.calculate_n1_from_data(training_data)

        # 3. N2 파라미터 계산
        n2_params = self.calculate_n2_from_data(training_data)

        # 4. 신뢰성 판단
        is_reliable = (
            n1_params["n1_constant"] is not None and
            n2_params["n2_slope"] is not None and
            n2_params["n2_r_squared"] is not None and
            n2_params["n2_r_squared"] >= self.min_r_squared and
            len(training_data) >= self.min_samples
        )

        # 5. 파라미터 저장/업데이트
        params = {
            "keyword": keyword,
            "n1_constant": n1_params["n1_constant"],
            "n1_std": n1_params["n1_std"],
            "n2_slope": n2_params["n2_slope"],
            "n2_intercept": n2_params["n2_intercept"],
            "n2_r_squared": n2_params["n2_r_squared"],
            "sample_count": len(training_data),
            "is_reliable": is_reliable,
            "last_trained_at": datetime.utcnow(),
        }

        await parameter_repository.save_or_update(db, params)
        await db.commit()

        logger.info(f"Keyword '{keyword}' training completed: reliable={is_reliable}")

        return {
            "keyword": keyword,
            "success": True,
            "is_reliable": is_reliable,
            "sample_count": len(training_data),
            "n1_constant": n1_params["n1_constant"],
            "n1_std": n1_params["n1_std"],
            "n2_slope": n2_params["n2_slope"],
            "n2_intercept": n2_params["n2_intercept"],
            "n2_r_squared": n2_params["n2_r_squared"],
        }

    async def get_all_keywords(
        self,
        db: AsyncSession
    ) -> List[str]:
        """
        학습 데이터가 있는 모든 키워드 조회

        Args:
            db: DB 세션

        Returns:
            키워드 리스트
        """
        result = await db.execute(
            select(distinct(AdlogTrainingData.keyword))
        )
        keywords = result.scalars().all()
        return list(keywords)

    async def train_all_keywords(
        self,
        db: AsyncSession
    ) -> Dict[str, Any]:
        """
        모든 키워드 일괄 학습

        Args:
            db: DB 세션

        Returns:
            학습 결과 요약
        """
        logger.info("[Trainer] Starting batch training for all keywords")
        start_time = datetime.utcnow()

        # 1. 모든 키워드 조회
        keywords = await self.get_all_keywords(db)
        total_count = len(keywords)

        logger.info(f"[Trainer] Found {total_count} keywords to train")

        if total_count == 0:
            return {
                "success": True,
                "total_keywords": 0,
                "trained": 0,
                "skipped": 0,
                "reliable": 0,
                "duration_seconds": 0,
                "message": "No keywords to train",
            }

        # 2. 각 키워드 학습
        trained_count = 0
        skipped_count = 0
        reliable_count = 0
        errors = []

        for keyword in keywords:
            try:
                result = await self.train_keyword(db, keyword)

                if result["success"]:
                    trained_count += 1
                    if result.get("is_reliable"):
                        reliable_count += 1
                else:
                    skipped_count += 1

            except Exception as e:
                logger.error(f"[Trainer] Error training keyword '{keyword}': {str(e)}")
                errors.append({"keyword": keyword, "error": str(e)})
                skipped_count += 1

        # 3. 결과 요약
        end_time = datetime.utcnow()
        duration = (end_time - start_time).total_seconds()

        result = {
            "success": True,
            "total_keywords": total_count,
            "trained": trained_count,
            "skipped": skipped_count,
            "reliable": reliable_count,
            "duration_seconds": round(duration, 2),
            "started_at": start_time.isoformat(),
            "completed_at": end_time.isoformat(),
        }

        if errors:
            result["errors"] = errors[:10]  # 최대 10개만 반환
            result["error_count"] = len(errors)

        logger.info(
            f"[Trainer] Batch training completed: "
            f"{trained_count}/{total_count} trained, "
            f"{reliable_count} reliable, "
            f"duration={duration:.2f}s"
        )

        return result

    async def get_training_report(
        self,
        db: AsyncSession
    ) -> Dict[str, Any]:
        """
        학습 결과 리포트 생성

        Args:
            db: DB 세션

        Returns:
            학습 리포트 딕셔너리
        """
        # 1. 키워드 파라미터 통계
        total_result = await db.execute(
            select(func.count(KeywordParameter.id))
        )
        total_keywords = total_result.scalar() or 0

        reliable_result = await db.execute(
            select(func.count(KeywordParameter.id))
            .where(KeywordParameter.is_reliable.is_(True))
        )
        reliable_keywords = reliable_result.scalar() or 0

        avg_r2_result = await db.execute(
            select(func.avg(KeywordParameter.n2_r_squared))
            .where(KeywordParameter.n2_r_squared.isnot(None))
        )
        avg_r_squared = avg_r2_result.scalar()

        avg_sample_result = await db.execute(
            select(func.avg(KeywordParameter.sample_count))
        )
        avg_sample_count = avg_sample_result.scalar() or 0

        # 2. 학습 데이터 통계
        training_data_result = await db.execute(
            select(func.count(AdlogTrainingData.id))
        )
        total_training_data = training_data_result.scalar() or 0

        unique_keywords_result = await db.execute(
            select(func.count(distinct(AdlogTrainingData.keyword)))
        )
        unique_keywords = unique_keywords_result.scalar() or 0

        # 3. 최근 학습 시간
        last_trained_result = await db.execute(
            select(func.max(KeywordParameter.last_trained_at))
        )
        last_trained_at = last_trained_result.scalar()

        return {
            "parameters": {
                "total_keywords": total_keywords,
                "reliable_keywords": reliable_keywords,
                "unreliable_keywords": total_keywords - reliable_keywords,
                "reliability_ratio": round(reliable_keywords / total_keywords, 4) if total_keywords > 0 else 0,
                "avg_r_squared": round(avg_r_squared, 4) if avg_r_squared else None,
                "avg_sample_count": round(avg_sample_count, 2),
            },
            "training_data": {
                "total_records": total_training_data,
                "unique_keywords": unique_keywords,
            },
            "last_trained_at": last_trained_at.isoformat() if last_trained_at else None,
            "generated_at": datetime.utcnow().isoformat(),
        }


# 싱글톤 인스턴스
keyword_trainer = KeywordTrainer()
