import asyncio
import logging
from datetime import datetime, date, timedelta
from typing import Optional
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from sqlalchemy import select, and_, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import AsyncSessionLocal
from app.models.place import (
    TrackedPlace, PlaceStats, RankHistory, SavedKeyword,
    UserActivityLog, AdlogTrainingData
)
from app.services.naver_place import NaverPlaceService

logger = logging.getLogger(__name__)

# 학습 상태 저장 (메모리)
training_status = {
    "is_running": False,
    "last_result": None,
    "last_run_at": None,
}


class PlaceScheduler:
    """플레이스 데이터 자동 수집 스케줄러"""

    def __init__(self):
        self.scheduler: Optional[AsyncIOScheduler] = None
        self.naver_service = NaverPlaceService()
        self._is_running = False

    def start(self):
        """스케줄러 시작"""
        if self._is_running:
            logger.warning("Scheduler already running")
            return

        self.scheduler = AsyncIOScheduler()

        # 매일 오전 9시에 실행 (KST) - 일일 데이터 수집
        self.scheduler.add_job(
            self.collect_daily_data,
            CronTrigger(hour=9, minute=0),
            id="daily_data_collection",
            name="Daily Place Data Collection",
            replace_existing=True
        )

        # 매 6시간마다 순위 체크 (09시, 15시, 21시, 03시)
        self.scheduler.add_job(
            self.check_ranks,
            CronTrigger(hour="3,9,15,21", minute=0),
            id="rank_check",
            name="Periodic Rank Check",
            replace_existing=True
        )

        # 매일 오전 9시에 저장된 키워드 순위 추적 (순위 추적 페이지용)
        self.scheduler.add_job(
            self.refresh_saved_keywords,
            CronTrigger(hour=9, minute=0),
            id="saved_keywords_refresh",
            name="Daily Saved Keywords Refresh",
            replace_existing=True
        )

        # 매일 새벽 2시에 키워드 파라미터 자동 학습
        self.scheduler.add_job(
            self.nightly_training_job,
            CronTrigger(hour=2, minute=0),
            id="nightly_training",
            name="Nightly Parameter Training",
            replace_existing=True
        )

        # 매일 오전 10시에 Activity D+1/D+7 결과 업데이트
        self.scheduler.add_job(
            self.update_activity_results,
            CronTrigger(hour=10, minute=0),
            id="activity_results_update",
            name="Activity D+1/D+7 Results Update",
            replace_existing=True
        )

        # 매일 새벽 3시에 30일 경과 데이터 자동 삭제
        self.scheduler.add_job(
            self.cleanup_expired_data,
            CronTrigger(hour=3, minute=30),
            id="cleanup_expired_data",
            name="Cleanup Expired Data (30 days)",
            replace_existing=True
        )

        self.scheduler.start()
        self._is_running = True
        logger.info("=" * 60)
        logger.info("Place Scheduler started with following jobs:")
        logger.info("  - 02:00 | Nightly Parameter Training")
        logger.info("  - 03:30 | Cleanup Expired Data (30 days)")
        logger.info("  - 09:00 | Daily Data Collection")
        logger.info("  - 09:00 | Saved Keywords Refresh")
        logger.info("  - 10:00 | Activity D+1/D+7 Results Update")
        logger.info("  - 03,09,15,21:00 | Periodic Rank Check")
        logger.info("=" * 60)

    def stop(self):
        """스케줄러 종료"""
        if self.scheduler:
            self.scheduler.shutdown()
            self._is_running = False
            logger.info("Place Scheduler stopped")

    async def collect_daily_data(self):
        """등록된 모든 플레이스의 일일 데이터 수집"""
        logger.info("Starting daily data collection...")

        async with AsyncSessionLocal() as db:
            try:
                # 활성화된 추적 플레이스 조회
                result = await db.execute(
                    select(TrackedPlace).where(TrackedPlace.is_active == 1)
                )
                tracked_places = result.scalars().all()

                if not tracked_places:
                    logger.info("No tracked places found")
                    return

                logger.info(f"Collecting data for {len(tracked_places)} places")
                today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)

                success_count = 0
                fail_count = 0

                for tracked in tracked_places:
                    try:
                        # 플레이스 정보 조회
                        # 1. 추적 키워드로 검색해서 찾기 (가장 정확)
                        # 2. place_id로 직접 조회
                        place_info = None

                        # 추적 키워드가 있으면 키워드로 검색
                        keywords = tracked.keywords or []
                        for keyword in keywords:
                            search_results = await self.naver_service.search_places(keyword, 50)
                            for result in search_results:
                                if str(result.get("place_id")) == str(tracked.place_id):
                                    place_info = result
                                    logger.info(f"Found place via keyword '{keyword}': {result.get('name')}")
                                    break
                            if place_info:
                                break
                            await asyncio.sleep(1)  # 검색 간격

                        # 키워드로 못 찾으면 place_id로 직접 조회 시도
                        if not place_info:
                            place_info = await self.naver_service.get_place_info(tracked.place_id)

                        if not place_info or place_info.get("visitor_review_count", 0) == 0:
                            logger.warning(f"Failed to get info for place {tracked.place_id} ({tracked.place_name})")
                            fail_count += 1
                            continue

                        # 기존 오늘 데이터 확인
                        existing = await db.execute(
                            select(PlaceStats).where(
                                PlaceStats.place_id == tracked.place_id,
                                PlaceStats.date == today
                            )
                        )
                        existing_stat = existing.scalar_one_or_none()

                        if existing_stat:
                            # 업데이트
                            existing_stat.visitor_review_count = place_info.get("visitor_review_count", 0)
                            existing_stat.blog_review_count = place_info.get("blog_review_count", 0)
                            existing_stat.save_count = place_info.get("save_count", 0)
                            existing_stat.place_name = place_info.get("name", tracked.place_name)
                        else:
                            # 새로 생성
                            new_stat = PlaceStats(
                                place_id=tracked.place_id,
                                place_name=place_info.get("name", tracked.place_name),
                                visitor_review_count=place_info.get("visitor_review_count", 0),
                                blog_review_count=place_info.get("blog_review_count", 0),
                                save_count=place_info.get("save_count", 0),
                                date=today
                            )
                            db.add(new_stat)

                        # place_name 업데이트
                        if place_info.get("name") and tracked.place_name != place_info.get("name"):
                            tracked.place_name = place_info.get("name")

                        success_count += 1

                        # 요청 간격 두기 (네이버 차단 방지)
                        await asyncio.sleep(2)

                    except Exception as e:
                        logger.error(f"Error collecting data for place {tracked.place_id}: {e}")
                        fail_count += 1

                await db.commit()
                logger.info(f"Daily data collection completed: {success_count} success, {fail_count} failed")

            except Exception as e:
                logger.error(f"Daily data collection error: {e}")
                await db.rollback()

    async def check_ranks(self):
        """등록된 키워드들의 순위 체크"""
        logger.info("Starting rank check...")

        async with AsyncSessionLocal() as db:
            try:
                # 활성화된 추적 플레이스 조회
                result = await db.execute(
                    select(TrackedPlace).where(TrackedPlace.is_active == 1)
                )
                tracked_places = result.scalars().all()

                if not tracked_places:
                    logger.info("No tracked places found")
                    return

                total_keywords = 0
                success_count = 0

                for tracked in tracked_places:
                    keywords = tracked.keywords or []
                    if not keywords:
                        continue

                    for keyword in keywords:
                        try:
                            total_keywords += 1

                            # 순위 조회
                            rank_result = await self.naver_service.get_place_rank(
                                tracked.place_id,
                                keyword
                            )

                            # 기록 저장
                            rank_history = RankHistory(
                                place_id=tracked.place_id,
                                keyword=keyword,
                                rank=rank_result.get("rank"),
                                total_results=rank_result.get("total_results", 0),
                                checked_at=datetime.now()
                            )
                            db.add(rank_history)
                            success_count += 1

                            # 요청 간격 두기
                            await asyncio.sleep(3)

                        except Exception as e:
                            logger.error(f"Error checking rank for {tracked.place_id} - {keyword}: {e}")

                await db.commit()
                logger.info(f"Rank check completed: {success_count}/{total_keywords} keywords checked")

            except Exception as e:
                logger.error(f"Rank check error: {e}")
                await db.rollback()

    async def collect_single_place(self, place_id: str) -> bool:
        """단일 플레이스 데이터 즉시 수집"""
        try:
            place_info = await self.naver_service.get_place_info(place_id)
            if not place_info:
                return False

            async with AsyncSessionLocal() as db:
                today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)

                existing = await db.execute(
                    select(PlaceStats).where(
                        PlaceStats.place_id == place_id,
                        PlaceStats.date == today
                    )
                )
                existing_stat = existing.scalar_one_or_none()

                if existing_stat:
                    existing_stat.visitor_review_count = place_info.get("visitor_review_count", 0)
                    existing_stat.blog_review_count = place_info.get("blog_review_count", 0)
                    existing_stat.save_count = place_info.get("save_count", 0)
                    existing_stat.place_name = place_info.get("name", "")
                else:
                    new_stat = PlaceStats(
                        place_id=place_id,
                        place_name=place_info.get("name", ""),
                        visitor_review_count=place_info.get("visitor_review_count", 0),
                        blog_review_count=place_info.get("blog_review_count", 0),
                        save_count=place_info.get("save_count", 0),
                        date=today
                    )
                    db.add(new_stat)

                await db.commit()
                return True

        except Exception as e:
            logger.error(f"Error collecting single place {place_id}: {e}")
            return False

    async def refresh_saved_keywords(self):
        """저장된 키워드들의 순위/리뷰/지수를 크롤링하고 히스토리 저장 (순위 추적 페이지용)"""
        logger.info("[SavedKeywords] 자동 크롤링 시작...")

        async with AsyncSessionLocal() as db:
            try:
                # 모든 활성 키워드 조회
                result = await db.execute(
                    select(SavedKeyword).where(SavedKeyword.is_active == 1)
                )
                keywords = result.scalars().all()

                if not keywords:
                    logger.info("[SavedKeywords] 저장된 키워드 없음")
                    return

                logger.info(f"[SavedKeywords] 크롤링할 키워드 수: {len(keywords)}")

                success_count = 0
                error_count = 0

                for kw in keywords:
                    try:
                        # 순위 조회 (분석 포함)
                        rank_result = await self.naver_service.get_place_rank(kw.place_id, kw.keyword)
                        new_rank = rank_result.get("rank")

                        # 분석 결과에서 데이터 추출
                        visitor_review_count = 0
                        blog_review_count = 0
                        place_score = None

                        analysis = rank_result.get("analysis")
                        if analysis and analysis.get("target_analysis"):
                            target = analysis["target_analysis"]
                            place_score = target.get("total_score")
                            counts = target.get("counts", {})
                            visitor_review_count = counts.get("visitor_review", 0)
                            blog_review_count = counts.get("blog_review", 0)

                        # 키워드 업데이트
                        kw.last_rank = new_rank
                        kw.visitor_review_count = visitor_review_count
                        kw.blog_review_count = blog_review_count
                        kw.place_score = place_score
                        if new_rank and (kw.best_rank is None or new_rank < kw.best_rank):
                            kw.best_rank = new_rank
                        kw.updated_at = datetime.now()

                        # 히스토리 저장
                        history = RankHistory(
                            place_id=kw.place_id,
                            keyword=kw.keyword,
                            rank=new_rank,
                            total_results=rank_result.get("total_results"),
                            visitor_review_count=visitor_review_count,
                            blog_review_count=blog_review_count,
                            place_score=place_score,
                            checked_at=datetime.now()
                        )
                        db.add(history)

                        success_count += 1
                        logger.info(f"[SavedKeywords] {kw.place_name} - {kw.keyword}: {new_rank}위, 리뷰: {visitor_review_count}/{blog_review_count}, 점수: {place_score}")

                        # 요청 간격 (네이버 차단 방지)
                        await asyncio.sleep(3)

                    except Exception as e:
                        error_count += 1
                        logger.error(f"[SavedKeywords] 크롤링 실패 - {kw.keyword}: {str(e)}")

                await db.commit()
                logger.info(f"[SavedKeywords] 크롤링 완료: 성공 {success_count}, 실패 {error_count}")

            except Exception as e:
                logger.error(f"[SavedKeywords] 전체 크롤링 실패: {str(e)}")
                await db.rollback()

    async def nightly_training_job(self):
        """
        새벽 2시 자동 학습 작업

        - 저장된 ADLOG 데이터로 N1, N2 파라미터 재학습
        - 학습 결과를 keyword_parameters 테이블에 저장
        """
        global training_status

        if training_status["is_running"]:
            logger.warning("[Scheduler] 학습 작업이 이미 실행 중입니다.")
            return

        logger.info(f"[Scheduler] 새벽 자동 학습 시작: {datetime.now()}")
        training_status["is_running"] = True

        try:
            # 지연 import (순환 참조 방지)
            from app.ml.trainer import keyword_trainer

            async with AsyncSessionLocal() as db:
                result = await keyword_trainer.train_all_keywords(db)

                training_status["last_result"] = result
                training_status["last_run_at"] = datetime.now()

                logger.info(
                    f"[Scheduler] 새벽 학습 완료: "
                    f"{result.get('trained', 0)}/{result.get('total_keywords', 0)} 키워드 학습, "
                    f"{result.get('reliable', 0)}개 신뢰성 확보"
                )

        except Exception as e:
            logger.error(f"[Scheduler] 새벽 학습 실패: {str(e)}")
            training_status["last_result"] = {
                "success": False,
                "error": str(e),
            }

        finally:
            training_status["is_running"] = False

    async def update_activity_results(self):
        """
        D+1, D+7 결과 업데이트 (매일 10시 실행)

        기록된 활동의 결과를 업데이트합니다.
        - D+1: 활동일 기준 1일 후 순위/N3
        - D+7: 활동일 기준 7일 후 순위/N3
        """
        logger.info("[Scheduler] Activity D+1/D+7 결과 업데이트 시작...")

        try:
            # 지연 import (순환 참조 방지)
            from app.services.adlog_proxy import adlog_service, AdlogApiError

            async with AsyncSessionLocal() as db:
                today = date.today()
                updated_count = 0

                # D+1 업데이트 대상 조회 (어제 활동, 아직 D+1 미측정)
                d1_target_date = today - timedelta(days=1)
                d1_query = select(UserActivityLog).where(
                    and_(
                        UserActivityLog.activity_date == d1_target_date,
                        UserActivityLog.rank_after_1d.is_(None),
                    )
                )

                result = await db.execute(d1_query)
                d1_logs = result.scalars().all()

                logger.info(f"[Scheduler] D+1 업데이트 대상: {len(d1_logs)}개")

                for log in d1_logs:
                    try:
                        raw_data = await adlog_service.fetch_keyword_analysis(log.keyword)
                        places = raw_data.get("places", [])

                        for place in places:
                            place_match = False
                            if log.place_id and place.get("place_id") == log.place_id:
                                place_match = True
                            elif log.place_name and log.place_name.lower() in place.get("name", "").lower():
                                place_match = True

                            if place_match:
                                raw_indices = place.get("raw_indices", {})
                                log.rank_after_1d = place.get("rank")
                                log.n3_after_1d = raw_indices.get("n3")
                                log.measured_at_1d = datetime.now()
                                updated_count += 1
                                logger.info(f"[Scheduler] D+1 업데이트: {log.keyword} - 순위 {log.rank_after_1d}")
                                break

                        # 요청 간격 (네이버 차단 방지)
                        await asyncio.sleep(2)

                    except AdlogApiError as e:
                        logger.warning(f"[Scheduler] D+1 조회 실패 - {log.keyword}: {str(e)}")
                    except Exception as e:
                        logger.error(f"[Scheduler] D+1 처리 오류 - {log.keyword}: {str(e)}")

                # D+7 업데이트 대상 조회 (7일 전 활동, 아직 D+7 미측정)
                d7_target_date = today - timedelta(days=7)
                d7_query = select(UserActivityLog).where(
                    and_(
                        UserActivityLog.activity_date == d7_target_date,
                        UserActivityLog.rank_after_7d.is_(None),
                    )
                )

                result = await db.execute(d7_query)
                d7_logs = result.scalars().all()

                logger.info(f"[Scheduler] D+7 업데이트 대상: {len(d7_logs)}개")

                for log in d7_logs:
                    try:
                        raw_data = await adlog_service.fetch_keyword_analysis(log.keyword)
                        places = raw_data.get("places", [])

                        for place in places:
                            place_match = False
                            if log.place_id and place.get("place_id") == log.place_id:
                                place_match = True
                            elif log.place_name and log.place_name.lower() in place.get("name", "").lower():
                                place_match = True

                            if place_match:
                                raw_indices = place.get("raw_indices", {})
                                log.rank_after_7d = place.get("rank")
                                log.n3_after_7d = raw_indices.get("n3")
                                log.measured_at_7d = datetime.now()
                                updated_count += 1
                                logger.info(f"[Scheduler] D+7 업데이트: {log.keyword} - 순위 {log.rank_after_7d}")
                                break

                        # 요청 간격 (네이버 차단 방지)
                        await asyncio.sleep(2)

                    except AdlogApiError as e:
                        logger.warning(f"[Scheduler] D+7 조회 실패 - {log.keyword}: {str(e)}")
                    except Exception as e:
                        logger.error(f"[Scheduler] D+7 처리 오류 - {log.keyword}: {str(e)}")

                await db.commit()
                logger.info(
                    f"[Scheduler] Activity 결과 업데이트 완료: "
                    f"D+1 {len(d1_logs)}건 처리, D+7 {len(d7_logs)}건 처리, "
                    f"총 {updated_count}건 업데이트"
                )

        except Exception as e:
            logger.error(f"[Scheduler] Activity 결과 업데이트 실패: {str(e)}")

    async def cleanup_expired_data(self):
        """
        30일 경과 데이터 자동 삭제

        AdlogTrainingData 테이블에서 expires_at이 지난 데이터를 삭제합니다.
        """
        logger.info("[Scheduler] 만료 데이터 정리 시작...")

        try:
            async with AsyncSessionLocal() as db:
                now = datetime.now()

                # 만료된 AdlogTrainingData 삭제
                delete_query = delete(AdlogTrainingData).where(
                    AdlogTrainingData.expires_at < now
                )

                result = await db.execute(delete_query)
                deleted_count = result.rowcount

                await db.commit()

                if deleted_count > 0:
                    logger.info(f"[Scheduler] 만료 데이터 정리 완료: {deleted_count}건 삭제")
                else:
                    logger.info("[Scheduler] 만료 데이터 정리 완료: 삭제할 데이터 없음")

        except Exception as e:
            logger.error(f"[Scheduler] 만료 데이터 정리 실패: {str(e)}")

    def get_status(self) -> dict:
        """스케줄러 상태 조회"""
        if not self.scheduler:
            return {"running": False, "jobs": [], "training_status": training_status}

        jobs = []
        for job in self.scheduler.get_jobs():
            jobs.append({
                "id": job.id,
                "name": job.name,
                "next_run": job.next_run_time.isoformat() if job.next_run_time else None
            })

        return {
            "running": self._is_running,
            "jobs": jobs,
            "training_status": {
                "is_running": training_status["is_running"],
                "last_result": training_status["last_result"],
                "last_run_at": training_status["last_run_at"].isoformat() if training_status["last_run_at"] else None,
            }
        }


def get_training_status() -> dict:
    """학습 상태 조회 (외부 호환용)"""
    return {
        "is_running": training_status["is_running"],
        "last_result": training_status["last_result"],
        "last_run_at": training_status["last_run_at"].isoformat() if training_status["last_run_at"] else None,
    }


# 전역 스케줄러 인스턴스
place_scheduler = PlaceScheduler()
