"""
학습된 모델의 정확도 분석 모듈

기능:
1. 실제 ADLOG 값 vs 예측값 비교
2. 오차율 리포트 생성
3. 키워드별 정확도 통계
"""
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime

import numpy as np
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, distinct

from app.models.place import KeywordParameter, AdlogTrainingData
from app.services.parameter_extractor import parameter_repository

logger = logging.getLogger(__name__)


class ModelAnalyzer:
    """학습된 모델 정확도 분석"""

    async def analyze_accuracy(
        self,
        db: AsyncSession,
        keyword: str
    ) -> Dict[str, Any]:
        """
        키워드별 정확도 분석

        예측값 vs 실제값 비교하여 MAE, RMSE, R² 계산

        Args:
            db: DB 세션
            keyword: 검색 키워드

        Returns:
            정확도 분석 결과
        """
        logger.info(f"Analyzing accuracy for keyword: {keyword}")

        # 지연 import (순환 참조 방지)
        from app.services.formula_calculator import formula_calculator

        # 1. 파라미터 조회
        params = await parameter_repository.get_by_keyword(db, keyword)

        if not params:
            return {
                "keyword": keyword,
                "success": False,
                "error": "파라미터가 없습니다.",
            }

        if not formula_calculator.can_calculate(params):
            return {
                "keyword": keyword,
                "success": False,
                "error": "신뢰할 수 있는 파라미터가 아닙니다.",
                "is_reliable": False,
            }

        # 2. 학습 데이터 조회
        result = await db.execute(
            select(AdlogTrainingData)
            .where(AdlogTrainingData.keyword == keyword)
            .order_by(AdlogTrainingData.collected_at.desc())
        )
        training_data = result.scalars().all()

        if len(training_data) < 3:
            return {
                "keyword": keyword,
                "success": False,
                "error": f"데이터 부족: {len(training_data)}개",
            }

        # 3. 예측값 vs 실제값 비교
        n1_actual = []
        n1_predicted = []
        n2_actual = []
        n2_predicted = []
        n3_actual = []
        n3_predicted = []

        for data in training_data:
            if data.rank is None or data.rank <= 0:
                continue

            # 예측값 계산
            indices = formula_calculator.calculate_all_indices(params, data.rank)

            # N1 비교
            if data.index_n1 is not None and indices["n1"] is not None:
                n1_actual.append(data.index_n1)
                n1_predicted.append(indices["n1"])

            # N2 비교
            if data.index_n2 is not None and indices["n2"] is not None:
                n2_actual.append(data.index_n2)
                n2_predicted.append(indices["n2"])

            # N3 비교
            if data.index_n3 is not None and indices["n3"] is not None:
                n3_actual.append(data.index_n3)
                n3_predicted.append(indices["n3"])

        # 4. 통계 계산
        n1_stats = self._calculate_metrics(n1_actual, n1_predicted, "N1")
        n2_stats = self._calculate_metrics(n2_actual, n2_predicted, "N2")
        n3_stats = self._calculate_metrics(n3_actual, n3_predicted, "N3")

        # 5. 전체 정확도 (N2 기준, 가장 중요)
        overall_accuracy = None
        if n2_stats and n2_stats.get("r_squared") is not None:
            overall_accuracy = round(n2_stats["r_squared"] * 100, 2)

        return {
            "keyword": keyword,
            "success": True,
            "sample_count": len(training_data),
            "is_reliable": params.is_reliable,
            "overall_accuracy_percent": overall_accuracy,
            "n1_metrics": n1_stats,
            "n2_metrics": n2_stats,
            "n3_metrics": n3_stats,
            "analyzed_at": datetime.utcnow().isoformat(),
        }

    def _calculate_metrics(
        self,
        actual: List[float],
        predicted: List[float],
        name: str
    ) -> Optional[Dict[str, Any]]:
        """
        MAE, RMSE, R² 계산

        Args:
            actual: 실제값 리스트
            predicted: 예측값 리스트
            name: 지표 이름

        Returns:
            통계 딕셔너리
        """
        if len(actual) < 3 or len(predicted) < 3:
            logger.warning(f"{name}: Not enough data points")
            return None

        try:
            actual_arr = np.array(actual)
            predicted_arr = np.array(predicted)

            # MAE (Mean Absolute Error)
            mae = float(np.mean(np.abs(actual_arr - predicted_arr)))

            # RMSE (Root Mean Squared Error)
            rmse = float(np.sqrt(np.mean((actual_arr - predicted_arr) ** 2)))

            # R² (Coefficient of Determination)
            ss_res = np.sum((actual_arr - predicted_arr) ** 2)
            ss_tot = np.sum((actual_arr - np.mean(actual_arr)) ** 2)
            r_squared = float(1 - (ss_res / ss_tot)) if ss_tot > 0 else 0.0

            # MAPE (Mean Absolute Percentage Error)
            # 0으로 나누는 것 방지
            non_zero_mask = actual_arr != 0
            if np.sum(non_zero_mask) > 0:
                mape = float(np.mean(
                    np.abs((actual_arr[non_zero_mask] - predicted_arr[non_zero_mask]) / actual_arr[non_zero_mask])
                ) * 100)
            else:
                mape = None

            logger.info(
                f"{name} metrics: MAE={mae:.4f}, RMSE={rmse:.4f}, "
                f"R²={r_squared:.4f}, count={len(actual)}"
            )

            return {
                "name": name,
                "count": len(actual),
                "mae": round(mae, 4),
                "rmse": round(rmse, 4),
                "r_squared": round(r_squared, 4),
                "mape_percent": round(mape, 2) if mape is not None else None,
            }

        except Exception as e:
            logger.error(f"{name} metrics calculation failed: {str(e)}")
            return None

    async def generate_report(
        self,
        db: AsyncSession
    ) -> Dict[str, Any]:
        """
        전체 정확도 리포트 생성

        Args:
            db: DB 세션

        Returns:
            전체 리포트 딕셔너리
        """
        logger.info("[Analyzer] Generating accuracy report")
        start_time = datetime.utcnow()

        # 1. 신뢰할 수 있는 키워드 조회
        result = await db.execute(
            select(KeywordParameter)
            .where(KeywordParameter.is_reliable.is_(True))
        )
        reliable_params = result.scalars().all()

        if not reliable_params:
            return {
                "success": True,
                "total_keywords": 0,
                "message": "No reliable parameters to analyze",
                "generated_at": datetime.utcnow().isoformat(),
            }

        # 2. 각 키워드 분석
        keyword_results = []
        total_r_squared = []
        total_mae = []
        total_rmse = []

        for params in reliable_params:
            try:
                analysis = await self.analyze_accuracy(db, params.keyword)

                if analysis["success"]:
                    keyword_results.append({
                        "keyword": params.keyword,
                        "sample_count": analysis["sample_count"],
                        "overall_accuracy_percent": analysis.get("overall_accuracy_percent"),
                        "n2_r_squared": analysis["n2_metrics"]["r_squared"] if analysis.get("n2_metrics") else None,
                    })

                    if analysis.get("n2_metrics"):
                        if analysis["n2_metrics"].get("r_squared") is not None:
                            total_r_squared.append(analysis["n2_metrics"]["r_squared"])
                        if analysis["n2_metrics"].get("mae") is not None:
                            total_mae.append(analysis["n2_metrics"]["mae"])
                        if analysis["n2_metrics"].get("rmse") is not None:
                            total_rmse.append(analysis["n2_metrics"]["rmse"])

            except Exception as e:
                logger.error(f"[Analyzer] Error analyzing keyword '{params.keyword}': {str(e)}")

        # 3. 전체 통계
        end_time = datetime.utcnow()
        duration = (end_time - start_time).total_seconds()

        report = {
            "success": True,
            "total_keywords": len(reliable_params),
            "analyzed_keywords": len(keyword_results),
            "summary": {
                "avg_r_squared": round(np.mean(total_r_squared), 4) if total_r_squared else None,
                "avg_mae": round(np.mean(total_mae), 4) if total_mae else None,
                "avg_rmse": round(np.mean(total_rmse), 4) if total_rmse else None,
                "avg_accuracy_percent": round(np.mean(total_r_squared) * 100, 2) if total_r_squared else None,
            },
            "keywords": sorted(keyword_results, key=lambda x: x.get("n2_r_squared") or 0, reverse=True)[:20],
            "duration_seconds": round(duration, 2),
            "generated_at": datetime.utcnow().isoformat(),
        }

        logger.info(
            f"[Analyzer] Report generated: "
            f"{len(keyword_results)}/{len(reliable_params)} keywords analyzed, "
            f"avg_r²={report['summary']['avg_r_squared']}"
        )

        return report

    async def get_keyword_comparison(
        self,
        db: AsyncSession,
        keyword: str,
        limit: int = 20
    ) -> Dict[str, Any]:
        """
        키워드별 예측값 vs 실제값 상세 비교

        Args:
            db: DB 세션
            keyword: 검색 키워드
            limit: 최대 개수

        Returns:
            비교 결과
        """
        # 지연 import (순환 참조 방지)
        from app.services.formula_calculator import formula_calculator

        # 1. 파라미터 조회
        params = await parameter_repository.get_by_keyword(db, keyword)

        if not params or not formula_calculator.can_calculate(params):
            return {
                "keyword": keyword,
                "success": False,
                "error": "유효한 파라미터가 없습니다.",
            }

        # 2. 학습 데이터 조회
        result = await db.execute(
            select(AdlogTrainingData)
            .where(AdlogTrainingData.keyword == keyword)
            .order_by(AdlogTrainingData.collected_at.desc())
            .limit(limit)
        )
        training_data = result.scalars().all()

        # 3. 비교 데이터 생성
        comparisons = []
        for data in training_data:
            if data.rank is None or data.rank <= 0:
                continue

            indices = formula_calculator.calculate_all_indices(params, data.rank)

            comparison = {
                "rank": data.rank,
                "place_name": data.place_name,
                "collected_at": data.collected_at.isoformat() if data.collected_at else None,
                "n1": {
                    "actual": data.index_n1,
                    "predicted": round(indices["n1"], 4) if indices["n1"] else None,
                    "error": round(abs(data.index_n1 - indices["n1"]), 4) if data.index_n1 and indices["n1"] else None,
                },
                "n2": {
                    "actual": data.index_n2,
                    "predicted": round(indices["n2"], 4) if indices["n2"] else None,
                    "error": round(abs(data.index_n2 - indices["n2"]), 4) if data.index_n2 and indices["n2"] else None,
                },
                "n3": {
                    "actual": data.index_n3,
                    "predicted": round(indices["n3"], 4) if indices["n3"] else None,
                    "error": round(abs(data.index_n3 - indices["n3"]), 4) if data.index_n3 and indices["n3"] else None,
                },
            }
            comparisons.append(comparison)

        return {
            "keyword": keyword,
            "success": True,
            "sample_count": len(comparisons),
            "parameters": {
                "n1_constant": params.n1_constant,
                "n2_slope": params.n2_slope,
                "n2_intercept": params.n2_intercept,
                "n2_r_squared": params.n2_r_squared,
            },
            "comparisons": comparisons,
        }


# 싱글톤 인스턴스
model_analyzer = ModelAnalyzer()
