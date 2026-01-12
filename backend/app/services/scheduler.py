import asyncio
import logging
from datetime import datetime
from typing import Optional
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import AsyncSessionLocal
from app.models.place import TrackedPlace, PlaceStats, RankHistory, SavedKeyword
from app.services.naver_place import NaverPlaceService

logger = logging.getLogger(__name__)


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

        # 매일 오전 9시에 실행 (KST)
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

        self.scheduler.start()
        self._is_running = True
        logger.info("Place Scheduler started - Daily collection at 09:00, Saved keywords refresh at 09:00, Rank check every 6 hours")

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

    def get_status(self) -> dict:
        """스케줄러 상태 조회"""
        if not self.scheduler:
            return {"running": False, "jobs": []}

        jobs = []
        for job in self.scheduler.get_jobs():
            jobs.append({
                "id": job.id,
                "name": job.name,
                "next_run": job.next_run_time.isoformat() if job.next_run_time else None
            })

        return {
            "running": self._is_running,
            "jobs": jobs
        }


# 전역 스케줄러 인스턴스
place_scheduler = PlaceScheduler()
