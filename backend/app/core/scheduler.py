"""
매일 자동으로 키워드 순위를 크롤링하는 스케줄러
"""
import logging
from datetime import datetime
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import async_session_maker
from app.models.place import SavedKeyword, RankHistory
from app.services.naver_place import NaverPlaceService

logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler()
naver_service = NaverPlaceService()


async def refresh_all_keywords_job():
    """모든 저장된 키워드의 순위를 크롤링하고 저장"""
    logger.info(f"[Scheduler] 자동 크롤링 시작: {datetime.now()}")

    async with async_session_maker() as db:
        try:
            # 모든 활성 키워드 조회
            result = await db.execute(
                select(SavedKeyword).where(SavedKeyword.is_active == 1)
            )
            keywords = result.scalars().all()

            logger.info(f"[Scheduler] 크롤링할 키워드 수: {len(keywords)}")

            success_count = 0
            error_count = 0

            for kw in keywords:
                try:
                    # 순위 조회 (분석 포함)
                    rank_result = await naver_service.get_place_rank(kw.place_id, kw.keyword)
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
                    kw.updated_at = datetime.utcnow()

                    # 히스토리 저장
                    history = RankHistory(
                        place_id=kw.place_id,
                        keyword=kw.keyword,
                        rank=new_rank,
                        total_results=rank_result.get("total_results"),
                        visitor_review_count=visitor_review_count,
                        blog_review_count=blog_review_count,
                        place_score=place_score,
                        checked_at=datetime.utcnow()
                    )
                    db.add(history)

                    success_count += 1
                    logger.info(f"[Scheduler] {kw.place_name} - {kw.keyword}: {new_rank}위, 점수: {place_score}")

                except Exception as e:
                    error_count += 1
                    logger.error(f"[Scheduler] 크롤링 실패 - {kw.keyword}: {str(e)}")

            await db.commit()
            logger.info(f"[Scheduler] 크롤링 완료: 성공 {success_count}, 실패 {error_count}")

        except Exception as e:
            logger.error(f"[Scheduler] 전체 크롤링 실패: {str(e)}")
            await db.rollback()


def start_scheduler():
    """스케줄러 시작 - 매일 오전 9시에 실행"""
    # 매일 오전 9시에 실행
    scheduler.add_job(
        refresh_all_keywords_job,
        CronTrigger(hour=9, minute=0),
        id="daily_keyword_refresh",
        replace_existing=True
    )

    # 테스트용: 1시간마다 실행 (필요시 주석 해제)
    # scheduler.add_job(
    #     refresh_all_keywords_job,
    #     CronTrigger(minute=0),  # 매 정시
    #     id="hourly_keyword_refresh",
    #     replace_existing=True
    # )

    scheduler.start()
    logger.info("[Scheduler] 스케줄러 시작됨 - 매일 오전 9시 자동 크롤링")


def stop_scheduler():
    """스케줄러 중지"""
    if scheduler.running:
        scheduler.shutdown()
        logger.info("[Scheduler] 스케줄러 중지됨")
