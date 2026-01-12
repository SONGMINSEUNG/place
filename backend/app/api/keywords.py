from fastapi import APIRouter, HTTPException, Depends, Query
from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, desc
from app.core.database import get_db
from app.models.place import SavedKeyword, RankHistory, Place
from app.services.naver_place import NaverPlaceService

router = APIRouter()
naver_service = NaverPlaceService()

# 임시: 고정 user_id (나중에 로그인 기능 추가 시 제거)
DEFAULT_USER_ID = 1


# Models
class SaveKeywordRequest(BaseModel):
    place_url: str
    place_name: Optional[str] = None
    keyword: str


class DailyData(BaseModel):
    date: str  # "12/23" 형태
    rank: Optional[int]
    visitor_review_count: int = 0
    blog_review_count: int = 0
    place_score: Optional[float] = None

class SavedKeywordResponse(BaseModel):
    id: int
    place_id: str
    place_name: Optional[str]
    keyword: str
    last_rank: Optional[int]
    best_rank: Optional[int]
    visitor_review_count: int = 0
    blog_review_count: int = 0
    place_score: Optional[float] = None
    weekly_data: List[DailyData] = []  # 최근 7일 데이터
    is_active: bool
    created_at: datetime


class RankHistoryResponse(BaseModel):
    rank: Optional[int]
    total_results: Optional[int]
    checked_at: datetime


class KeywordRankUpdate(BaseModel):
    keyword_id: int
    rank: Optional[int]
    total_results: Optional[int]


# Endpoints
@router.post("/save", response_model=SavedKeywordResponse)
async def save_keyword(
    request: SaveKeywordRequest,
    db: AsyncSession = Depends(get_db)
):
    """키워드 저장 (순위 추적용)"""
    place_id = naver_service.extract_place_id(request.place_url)
    if not place_id:
        raise HTTPException(status_code=400, detail="유효하지 않은 플레이스 URL입니다")

    # 이미 저장된 키워드인지 확인
    result = await db.execute(
        select(SavedKeyword).where(
            and_(
                SavedKeyword.user_id == DEFAULT_USER_ID,
                SavedKeyword.place_id == place_id,
                SavedKeyword.keyword == request.keyword
            )
        )
    )
    existing = result.scalar_one_or_none()

    if existing:
        raise HTTPException(status_code=400, detail="이미 저장된 키워드입니다")

    # 현재 순위 조회 (분석 포함)
    rank_result = await naver_service.get_place_rank(place_id, request.keyword)
    current_rank = rank_result.get("rank")

    # 분석 결과에서 데이터 추출 (우리 산식으로 계산된 점수)
    visitor_review_count = 0
    blog_review_count = 0
    place_score = None
    place_name = request.place_name

    analysis = rank_result.get("analysis")
    if analysis and analysis.get("target_analysis"):
        target = analysis["target_analysis"]
        place_score = target.get("total_score")
        counts = target.get("counts", {})
        visitor_review_count = counts.get("visitor_review", 0)
        blog_review_count = counts.get("blog_review", 0)

    # 업체명 가져오기
    if not place_name:
        target_place = rank_result.get("target_place")
        if target_place:
            place_name = target_place.get("name")

    # 저장
    saved_keyword = SavedKeyword(
        user_id=DEFAULT_USER_ID,
        place_id=place_id,
        place_name=place_name,
        keyword=request.keyword,
        last_rank=current_rank,
        best_rank=current_rank,
        visitor_review_count=visitor_review_count,
        blog_review_count=blog_review_count,
        place_score=place_score,
        is_active=True
    )

    db.add(saved_keyword)
    await db.commit()
    await db.refresh(saved_keyword)

    # 첫 히스토리 기록 (모든 데이터 포함)
    history = RankHistory(
        place_id=place_id,
        keyword=request.keyword,
        rank=current_rank,
        total_results=rank_result.get("total_results"),
        visitor_review_count=visitor_review_count,
        blog_review_count=blog_review_count,
        place_score=place_score,
        checked_at=datetime.utcnow()
    )
    db.add(history)
    await db.commit()

    today_data = DailyData(
        date=datetime.utcnow().strftime("%m/%d"),
        rank=current_rank,
        visitor_review_count=visitor_review_count,
        blog_review_count=blog_review_count,
        place_score=place_score
    )

    return SavedKeywordResponse(
        id=saved_keyword.id,
        place_id=saved_keyword.place_id,
        place_name=saved_keyword.place_name,
        keyword=saved_keyword.keyword,
        last_rank=saved_keyword.last_rank,
        best_rank=saved_keyword.best_rank,
        visitor_review_count=saved_keyword.visitor_review_count or 0,
        blog_review_count=saved_keyword.blog_review_count or 0,
        place_score=saved_keyword.place_score,
        weekly_data=[today_data],
        is_active=bool(saved_keyword.is_active),
        created_at=saved_keyword.created_at
    )


@router.get("/", response_model=List[SavedKeywordResponse])
async def get_saved_keywords(
    db: AsyncSession = Depends(get_db)
):
    """저장된 키워드 목록 조회"""
    result = await db.execute(
        select(SavedKeyword)
        .where(SavedKeyword.user_id == DEFAULT_USER_ID)
        .order_by(desc(SavedKeyword.created_at))
    )
    keywords = result.scalars().all()

    responses = []
    for kw in keywords:
        # 최근 7일 히스토리 가져오기
        week_ago = datetime.utcnow() - timedelta(days=7)
        history_result = await db.execute(
            select(RankHistory)
            .where(
                and_(
                    RankHistory.place_id == kw.place_id,
                    RankHistory.keyword == kw.keyword,
                    RankHistory.checked_at >= week_ago
                )
            )
            .order_by(RankHistory.checked_at)
        )
        history = history_result.scalars().all()

        # 일별로 그룹핑 (최신 데이터만)
        daily_data_map = {}
        for h in history:
            date_str = h.checked_at.strftime("%m/%d")
            daily_data_map[date_str] = DailyData(
                date=date_str,
                rank=h.rank,
                visitor_review_count=h.visitor_review_count or 0,
                blog_review_count=h.blog_review_count or 0,
                place_score=h.place_score
            )

        weekly_data = list(daily_data_map.values())

        responses.append(SavedKeywordResponse(
            id=kw.id,
            place_id=kw.place_id,
            place_name=kw.place_name,
            keyword=kw.keyword,
            last_rank=kw.last_rank,
            best_rank=kw.best_rank,
            visitor_review_count=kw.visitor_review_count or 0,
            blog_review_count=kw.blog_review_count or 0,
            place_score=kw.place_score,
            weekly_data=weekly_data,
            is_active=bool(kw.is_active),
            created_at=kw.created_at
        ))

    return responses


@router.delete("/{keyword_id}")
async def delete_keyword(
    keyword_id: int,
    db: AsyncSession = Depends(get_db)
):
    """저장된 키워드 삭제"""
    result = await db.execute(
        select(SavedKeyword).where(
            and_(
                SavedKeyword.id == keyword_id,
                SavedKeyword.user_id == DEFAULT_USER_ID
            )
        )
    )
    keyword = result.scalar_one_or_none()

    if not keyword:
        raise HTTPException(status_code=404, detail="키워드를 찾을 수 없습니다")

    await db.delete(keyword)
    await db.commit()

    return {"message": "키워드가 삭제되었습니다"}


@router.post("/{keyword_id}/refresh")
async def refresh_keyword_rank(
    keyword_id: int,
    db: AsyncSession = Depends(get_db)
):
    """키워드 순위 새로고침"""
    result = await db.execute(
        select(SavedKeyword).where(
            and_(
                SavedKeyword.id == keyword_id,
                SavedKeyword.user_id == DEFAULT_USER_ID
            )
        )
    )
    keyword = result.scalar_one_or_none()

    if not keyword:
        raise HTTPException(status_code=404, detail="키워드를 찾을 수 없습니다")

    # 순위 조회 (분석 포함)
    rank_result = await naver_service.get_place_rank(keyword.place_id, keyword.keyword)
    new_rank = rank_result.get("rank")

    # 분석 결과에서 데이터 추출 (우리 산식으로 계산된 점수)
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

    # 순위 변동
    rank_change = None
    if keyword.last_rank and new_rank:
        rank_change = keyword.last_rank - new_rank  # 양수면 순위 상승

    # 업데이트
    keyword.last_rank = new_rank
    keyword.visitor_review_count = visitor_review_count
    keyword.blog_review_count = blog_review_count
    keyword.place_score = place_score
    if new_rank and (keyword.best_rank is None or new_rank < keyword.best_rank):
        keyword.best_rank = new_rank
    keyword.updated_at = datetime.utcnow()

    # 히스토리 저장 (모든 데이터 포함)
    history = RankHistory(
        place_id=keyword.place_id,
        keyword=keyword.keyword,
        rank=new_rank,
        total_results=rank_result.get("total_results"),
        visitor_review_count=visitor_review_count,
        blog_review_count=blog_review_count,
        place_score=place_score,
        checked_at=datetime.utcnow()
    )
    db.add(history)

    await db.commit()

    return {
        "keyword_id": keyword_id,
        "current_rank": new_rank,
        "previous_rank": keyword.last_rank,
        "best_rank": keyword.best_rank,
        "rank_change": rank_change,
        "total_results": rank_result.get("total_results"),
        "visitor_review_count": visitor_review_count,
        "blog_review_count": blog_review_count,
        "place_score": place_score
    }


@router.get("/{keyword_id}/history", response_model=List[RankHistoryResponse])
async def get_rank_history(
    keyword_id: int,
    days: int = Query(30, ge=1, le=90, description="조회 기간 (일)"),
    db: AsyncSession = Depends(get_db)
):
    """키워드 순위 히스토리 조회"""
    # 키워드 확인
    result = await db.execute(
        select(SavedKeyword).where(
            and_(
                SavedKeyword.id == keyword_id,
                SavedKeyword.user_id == DEFAULT_USER_ID
            )
        )
    )
    keyword = result.scalar_one_or_none()

    if not keyword:
        raise HTTPException(status_code=404, detail="키워드를 찾을 수 없습니다")

    # 히스토리 조회
    start_date = datetime.utcnow() - timedelta(days=days)
    result = await db.execute(
        select(RankHistory)
        .where(
            and_(
                RankHistory.place_id == keyword.place_id,
                RankHistory.keyword == keyword.keyword,
                RankHistory.checked_at >= start_date
            )
        )
        .order_by(desc(RankHistory.checked_at))
    )
    history = result.scalars().all()

    return [
        RankHistoryResponse(
            rank=h.rank,
            total_results=h.total_results,
            checked_at=h.checked_at
        )
        for h in history
    ]


@router.post("/refresh-all")
async def refresh_all_keywords(
    db: AsyncSession = Depends(get_db)
):
    """모든 저장된 키워드 순위 새로고침"""
    result = await db.execute(
        select(SavedKeyword).where(
            and_(
                SavedKeyword.user_id == DEFAULT_USER_ID,
                SavedKeyword.is_active == True
            )
        )
    )
    keywords = result.scalars().all()

    updated = []
    for keyword in keywords:
        try:
            rank_result = await naver_service.get_place_rank(keyword.place_id, keyword.keyword)
            new_rank = rank_result.get("rank")

            rank_change = None
            if keyword.last_rank and new_rank:
                rank_change = keyword.last_rank - new_rank

            keyword.last_rank = new_rank
            if new_rank and (keyword.best_rank is None or new_rank < keyword.best_rank):
                keyword.best_rank = new_rank
            keyword.updated_at = datetime.utcnow()

            # 히스토리 저장
            history = RankHistory(
                place_id=keyword.place_id,
                keyword=keyword.keyword,
                rank=new_rank,
                total_results=rank_result.get("total_results"),
                checked_at=datetime.utcnow()
            )
            db.add(history)

            updated.append({
                "keyword_id": keyword.id,
                "keyword": keyword.keyword,
                "place_name": keyword.place_name,
                "current_rank": new_rank,
                "rank_change": rank_change
            })

        except Exception as e:
            updated.append({
                "keyword_id": keyword.id,
                "keyword": keyword.keyword,
                "error": str(e)
            })

    await db.commit()

    return {
        "total": len(keywords),
        "updated": len([u for u in updated if "error" not in u]),
        "results": updated
    }
