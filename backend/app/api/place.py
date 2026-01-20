from fastapi import APIRouter, HTTPException, Query, Depends
from pydantic import BaseModel, Field
from typing import List, Optional, Any, Dict
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, func
from datetime import datetime, timedelta
from app.services.naver_place import NaverPlaceService
from app.services.place_analyzer import PlaceAnalyzer
from app.services.naver_datalab import datalab_service
from app.core.database import get_db
from app.models.place import PlaceStats, RankHistory, TrackedPlace, KeywordFactorAnalysis, KeywordSearchLog, KeywordRankSnapshot, PlaceSaveTracker, PlaceSaveHistory
from app.services.scheduler import place_scheduler
import logging

logger = logging.getLogger(__name__)
router = APIRouter()

# Services
naver_service = NaverPlaceService()
analyzer = PlaceAnalyzer()


# Request/Response Models
class PlaceRankRequest(BaseModel):
    place_url: str = Field(..., description="네이버 플레이스 URL 또는 ID")
    keywords: List[str] = Field(..., description="검색 키워드 목록", min_items=1, max_items=10)
    traffic_count: Optional[int] = Field(None, description="내 업체 유입수 (선택, 네이버 플레이스 통계에서 확인)")


class PlaceRankResponse(BaseModel):
    place_id: str
    keyword: str
    rank: Optional[int] = None
    total_results: int = 0
    target_place: Optional[Dict[str, Any]] = None
    competitors: List[Dict[str, Any]] = []


class PlaceInfoResponse(BaseModel):
    place_id: str
    name: str
    category: Optional[str] = None
    address: Optional[str] = None
    road_address: Optional[str] = None
    phone: Optional[str] = None
    visitor_review_count: int = 0
    blog_review_count: int = 0
    save_count: int = 0
    place_score: float = 0.0
    description: Optional[str] = None
    keywords: List[str] = []


class PlaceAnalysisRequest(BaseModel):
    place_url: str
    keywords: List[str] = Field(default=[], max_items=5)


class HiddenKeywordResponse(BaseModel):
    keyword: str
    rank: int
    total_results: int
    potential: str


class CompetitivenessResponse(BaseModel):
    target_score: float
    average_competitor_score: float
    score_rank: int
    total_competitors: int
    strengths: List[str]
    weaknesses: List[str]
    top_competitors: List[Dict[str, Any]]


# API Endpoints - 순서 중요! 구체적인 경로가 먼저 와야 함

@router.post("/rank")
async def get_place_rank(request: PlaceRankRequest):
    """플레이스 순위 조회"""
    place_id = naver_service.extract_place_id(request.place_url)
    if not place_id:
        raise HTTPException(status_code=400, detail="유효하지 않은 플레이스 URL입니다")

    results = []
    for keyword in request.keywords:
        try:
            rank_result = await naver_service.get_place_rank(
                place_id,
                keyword.strip(),
                traffic_count=request.traffic_count  # 유입수 전달
            )
            results.append({
                "place_id": place_id,
                "keyword": keyword,
                "rank": rank_result.get("rank"),
                "total_results": rank_result.get("total_results", 0),
                "target_place": rank_result.get("target_place"),
                "competitors": rank_result.get("competitors", []),
                "analysis": rank_result.get("analysis")
            })
        except Exception as e:
            logger.error(f"Error getting rank for keyword '{keyword}': {e}")
            results.append({
                "place_id": place_id,
                "keyword": keyword,
                "rank": None,
                "total_results": 0,
                "target_place": None,
                "competitors": [],
                "analysis": None
            })

    return results


@router.get("/info-by-url")
async def get_place_info_by_url(url: str = Query(..., description="플레이스 URL")):
    """URL로 플레이스 정보 조회"""
    place_id = naver_service.extract_place_id(url)
    if not place_id:
        raise HTTPException(status_code=400, detail="유효하지 않은 플레이스 URL입니다")

    place_info = await naver_service.get_place_info(place_id)
    if not place_info:
        raise HTTPException(status_code=404, detail="플레이스를 찾을 수 없습니다")

    # 플레이스 지수 계산
    place_score = analyzer.calculate_place_score(place_info)

    return {
        "place_id": place_info.get("place_id", place_id),
        "name": place_info.get("name", "알 수 없음"),
        "category": place_info.get("category"),
        "address": place_info.get("address"),
        "road_address": place_info.get("road_address"),
        "phone": place_info.get("phone"),
        "visitor_review_count": place_info.get("visitor_review_count", 0),
        "blog_review_count": place_info.get("blog_review_count", 0),
        "save_count": place_info.get("save_count", 0),
        "place_score": place_score,
        "description": place_info.get("description"),
        "keywords": place_info.get("keywords", [])
    }


@router.get("/search")
async def search_places(
    keyword: str = Query(..., min_length=2, description="검색 키워드"),
    limit: int = Query(50, ge=1, le=300, description="결과 개수")
):
    """키워드로 플레이스 검색"""
    results = await naver_service.search_places(keyword, limit)
    return {
        "keyword": keyword,
        "total": len(results),
        "places": results
    }


@router.get("/competitors")
async def get_competitors(
    place_url: str = Query(..., description="플레이스 URL"),
    keyword: str = Query(..., description="검색 키워드"),
    limit: int = Query(20, ge=1, le=50, description="결과 개수")
):
    """경쟁 업체 조회"""
    place_id = naver_service.extract_place_id(place_url)
    if not place_id:
        raise HTTPException(status_code=400, detail="유효하지 않은 플레이스 URL입니다")

    rank_result = await naver_service.get_place_rank(place_id, keyword)

    return {
        "place_id": place_id,
        "keyword": keyword,
        "my_rank": rank_result.get("rank"),
        "competitors": rank_result.get("competitors", [])[:limit]
    }


@router.get("/info/{place_id}")
async def get_place_info(place_id: str):
    """플레이스 상세 정보 조회"""
    place_info = await naver_service.get_place_info(place_id)
    if not place_info:
        raise HTTPException(status_code=404, detail="플레이스를 찾을 수 없습니다")

    # 플레이스 지수 계산
    place_score = analyzer.calculate_place_score(place_info)

    return {
        "place_id": place_info.get("place_id", place_id),
        "name": place_info.get("name", "알 수 없음"),
        "category": place_info.get("category"),
        "address": place_info.get("address"),
        "road_address": place_info.get("road_address"),
        "phone": place_info.get("phone"),
        "visitor_review_count": place_info.get("visitor_review_count", 0),
        "blog_review_count": place_info.get("blog_review_count", 0),
        "save_count": place_info.get("save_count", 0),
        "place_score": place_score,
        "description": place_info.get("description"),
        "keywords": place_info.get("keywords", [])
    }


@router.post("/analysis")
async def analyze_place(request: PlaceAnalysisRequest):
    """플레이스 종합 분석"""
    place_id = naver_service.extract_place_id(request.place_url)
    if not place_id:
        raise HTTPException(status_code=400, detail="유효하지 않은 플레이스 URL입니다")

    # 플레이스 정보 조회
    place_info = await naver_service.get_place_info(place_id)
    if not place_info:
        raise HTTPException(status_code=404, detail="플레이스를 찾을 수 없습니다")

    # 키워드별 순위 조회
    keyword_ranks = []
    all_competitors = []

    for keyword in request.keywords:
        rank_result = await naver_service.get_place_rank(place_id, keyword)
        keyword_ranks.append({
            "keyword": keyword,
            "rank": rank_result.get("rank"),
            "total_results": rank_result.get("total_results", 0)
        })
        all_competitors.extend(rank_result.get("competitors", []))

    # 플레이스 지수
    place_score = analyzer.calculate_place_score(place_info)

    # 경쟁력 분석
    competitiveness = analyzer.analyze_competitiveness(place_info, all_competitors[:50])

    return {
        "place_info": {
            **place_info,
            "place_score": place_score
        },
        "keyword_ranks": keyword_ranks,
        "competitiveness": competitiveness
    }


@router.post("/hidden-keywords")
async def find_hidden_keywords(request: PlaceAnalysisRequest):
    """히든 키워드 분석"""
    place_id = naver_service.extract_place_id(request.place_url)
    if not place_id:
        raise HTTPException(status_code=400, detail="유효하지 않은 플레이스 URL입니다")

    place_info = await naver_service.get_place_info(place_id)
    if not place_info:
        raise HTTPException(status_code=404, detail="플레이스를 찾을 수 없습니다")

    hidden_keywords = await analyzer.find_hidden_keywords(place_id, place_info)

    return [
        {
            "keyword": kw["keyword"],
            "rank": kw["rank"],
            "total_results": kw["total_results"],
            "potential": kw["potential"]
        }
        for kw in hidden_keywords
    ]


@router.post("/report")
async def generate_report(request: PlaceAnalysisRequest):
    """종합 분석 리포트 생성"""
    place_id = naver_service.extract_place_id(request.place_url)
    if not place_id:
        raise HTTPException(status_code=400, detail="유효하지 않은 플레이스 URL입니다")

    if not request.keywords:
        raise HTTPException(status_code=400, detail="최소 1개 이상의 키워드가 필요합니다")

    report = await analyzer.generate_report(place_id, request.keywords)

    if "error" in report:
        raise HTTPException(status_code=404, detail=report["error"])

    return report


# ============== 추적 기능 API ==============

class TrackPlaceRequest(BaseModel):
    place_id: str
    place_name: Optional[str] = None
    visitor_review_count: Optional[int] = None
    blog_review_count: Optional[int] = None
    save_count: Optional[int] = None


class TrackRankRequest(BaseModel):
    place_id: str
    keyword: str


@router.post("/track")
async def track_place(request: TrackPlaceRequest, db: AsyncSession = Depends(get_db)):
    """플레이스 추적 시작 - 현재 데이터 저장

    요청에 stats 데이터가 포함되면 그 값을 사용하고,
    없으면 네이버에서 조회합니다.
    """
    # 요청에 데이터가 포함되어 있으면 사용
    if request.visitor_review_count is not None:
        place_name = request.place_name or ""
        visitor_review = request.visitor_review_count
        blog_review = request.blog_review_count or 0
        save_count = request.save_count or 0
    else:
        # 네이버에서 정보 가져오기
        place_info = await naver_service.get_place_info(request.place_id)
        if not place_info or not place_info.get("name"):
            raise HTTPException(status_code=404, detail="플레이스를 찾을 수 없습니다. place_name과 stats를 직접 전달해주세요.")

        place_name = place_info.get("name", "")
        visitor_review = place_info.get("visitor_review_count", 0)
        blog_review = place_info.get("blog_review_count", 0)
        save_count = place_info.get("save_count", 0)

    today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)

    # 오늘 이미 기록했는지 확인
    existing = await db.execute(
        select(PlaceStats).where(
            and_(
                PlaceStats.place_id == request.place_id,
                PlaceStats.date == today
            )
        )
    )
    existing_stat = existing.scalar_one_or_none()

    if existing_stat:
        # 업데이트
        existing_stat.visitor_review_count = visitor_review
        existing_stat.blog_review_count = blog_review
        existing_stat.save_count = save_count
        existing_stat.place_name = place_name
    else:
        # 새로 생성
        new_stat = PlaceStats(
            place_id=request.place_id,
            place_name=place_name,
            visitor_review_count=visitor_review,
            blog_review_count=blog_review,
            save_count=save_count,
            date=today
        )
        db.add(new_stat)

    await db.commit()

    return {
        "message": "추적 데이터 저장 완료",
        "place_id": request.place_id,
        "place_name": place_name,
        "date": today.isoformat(),
        "stats": {
            "visitor_review_count": visitor_review,
            "blog_review_count": blog_review,
            "save_count": save_count
        }
    }


@router.post("/track/rank")
async def track_rank(request: TrackRankRequest, db: AsyncSession = Depends(get_db)):
    """키워드 순위 추적 - 순위 기록"""
    # 순위 조회
    rank_result = await naver_service.get_place_rank(request.place_id, request.keyword)

    # 순위 기록 저장
    rank_history = RankHistory(
        place_id=request.place_id,
        keyword=request.keyword,
        rank=rank_result.get("rank"),
        total_results=rank_result.get("total_results", 0),
        checked_at=datetime.now()
    )
    db.add(rank_history)
    await db.commit()

    return {
        "message": "순위 기록 완료",
        "place_id": request.place_id,
        "keyword": request.keyword,
        "rank": rank_result.get("rank"),
        "total_results": rank_result.get("total_results", 0),
        "checked_at": datetime.now().isoformat()
    }


@router.get("/stats/{place_id}")
async def get_place_stats(
    place_id: str,
    days: int = Query(7, ge=1, le=30, description="조회 기간 (일)"),
    db: AsyncSession = Depends(get_db)
):
    """플레이스 통계 히스토리 조회"""
    start_date = datetime.now() - timedelta(days=days)

    result = await db.execute(
        select(PlaceStats)
        .where(
            and_(
                PlaceStats.place_id == place_id,
                PlaceStats.date >= start_date
            )
        )
        .order_by(PlaceStats.date.desc())
    )
    stats = result.scalars().all()

    return {
        "place_id": place_id,
        "period_days": days,
        "stats": [
            {
                "date": stat.date.isoformat(),
                "visitor_review_count": stat.visitor_review_count,
                "blog_review_count": stat.blog_review_count,
                "save_count": stat.save_count
            }
            for stat in stats
        ]
    }


@router.get("/stats/{place_id}/changes")
async def get_place_changes(
    place_id: str,
    db: AsyncSession = Depends(get_db)
):
    """플레이스 변화량 조회 (오늘 vs 어제, 3일 추이)"""
    today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    yesterday = today - timedelta(days=1)
    three_days_ago = today - timedelta(days=3)

    # 최근 데이터 조회
    result = await db.execute(
        select(PlaceStats)
        .where(
            and_(
                PlaceStats.place_id == place_id,
                PlaceStats.date >= three_days_ago
            )
        )
        .order_by(PlaceStats.date.desc())
    )
    stats = result.scalars().all()

    if not stats:
        # 데이터가 없으면 현재 정보 가져와서 반환
        place_info = await naver_service.get_place_info(place_id)
        return {
            "place_id": place_id,
            "has_history": False,
            "current": {
                "visitor_review_count": place_info.get("visitor_review_count", 0) if place_info else 0,
                "blog_review_count": place_info.get("blog_review_count", 0) if place_info else 0,
                "save_count": place_info.get("save_count", 0) if place_info else 0
            },
            "message": "추적 데이터가 없습니다. /track API를 호출해서 추적을 시작하세요."
        }

    # 날짜별 데이터 매핑
    stats_by_date = {stat.date.date(): stat for stat in stats}

    today_stat = stats_by_date.get(today.date())
    yesterday_stat = stats_by_date.get(yesterday.date())

    # 오늘 변화량 계산
    today_changes = None
    if today_stat and yesterday_stat:
        today_changes = {
            "visitor_review": today_stat.visitor_review_count - yesterday_stat.visitor_review_count,
            "blog_review": today_stat.blog_review_count - yesterday_stat.blog_review_count,
            "save": today_stat.save_count - yesterday_stat.save_count
        }

    # 3일 추이
    three_day_trend = [
        {
            "date": stat.date.isoformat(),
            "visitor_review_count": stat.visitor_review_count,
            "blog_review_count": stat.blog_review_count,
            "save_count": stat.save_count
        }
        for stat in sorted(stats, key=lambda x: x.date)
    ]

    return {
        "place_id": place_id,
        "place_name": stats[0].place_name if stats else "",
        "has_history": True,
        "today_changes": today_changes,
        "three_day_trend": three_day_trend,
        "latest": {
            "date": stats[0].date.isoformat(),
            "visitor_review_count": stats[0].visitor_review_count,
            "blog_review_count": stats[0].blog_review_count,
            "save_count": stats[0].save_count
        } if stats else None
    }


@router.get("/rank-history/{place_id}")
async def get_rank_history(
    place_id: str,
    keyword: str = Query(..., description="키워드"),
    days: int = Query(7, ge=1, le=30, description="조회 기간 (일)"),
    db: AsyncSession = Depends(get_db)
):
    """키워드 순위 히스토리 조회"""
    start_date = datetime.now() - timedelta(days=days)

    result = await db.execute(
        select(RankHistory)
        .where(
            and_(
                RankHistory.place_id == place_id,
                RankHistory.keyword == keyword,
                RankHistory.checked_at >= start_date
            )
        )
        .order_by(RankHistory.checked_at.desc())
    )
    history = result.scalars().all()

    # 순위 변화 계산
    rank_changes = []
    for i, h in enumerate(history):
        change = None
        if i < len(history) - 1:
            prev_rank = history[i + 1].rank
            if h.rank and prev_rank:
                change = prev_rank - h.rank  # 양수면 순위 상승
        rank_changes.append({
            "checked_at": h.checked_at.isoformat(),
            "rank": h.rank,
            "total_results": h.total_results,
            "change": change
        })

    return {
        "place_id": place_id,
        "keyword": keyword,
        "period_days": days,
        "history": rank_changes,
        "best_rank": min([h.rank for h in history if h.rank], default=None),
        "worst_rank": max([h.rank for h in history if h.rank], default=None)
    }


# ============== 추적 대상 관리 API ==============

class AddTrackedPlaceRequest(BaseModel):
    place_id: str = Field(..., description="플레이스 ID")
    place_name: Optional[str] = None
    keywords: Optional[List[str]] = Field(default=[], description="추적할 키워드 목록")


class UpdateTrackedPlaceRequest(BaseModel):
    place_name: Optional[str] = None
    keywords: Optional[List[str]] = None
    is_active: Optional[int] = None


@router.get("/tracked")
async def get_tracked_places(
    db: AsyncSession = Depends(get_db)
):
    """추적 중인 플레이스 목록 조회"""
    result = await db.execute(
        select(TrackedPlace).order_by(TrackedPlace.created_at.desc())
    )
    tracked = result.scalars().all()

    return {
        "total": len(tracked),
        "places": [
            {
                "id": t.id,
                "place_id": t.place_id,
                "place_name": t.place_name,
                "keywords": t.keywords or [],
                "is_active": t.is_active,
                "created_at": t.created_at.isoformat(),
                "updated_at": t.updated_at.isoformat() if t.updated_at else None
            }
            for t in tracked
        ]
    }


@router.post("/tracked")
async def add_tracked_place(
    request: AddTrackedPlaceRequest,
    db: AsyncSession = Depends(get_db)
):
    """플레이스 추적 등록"""
    # 이미 등록되어 있는지 확인
    existing = await db.execute(
        select(TrackedPlace).where(TrackedPlace.place_id == request.place_id)
    )
    existing_tracked = existing.scalar_one_or_none()

    if existing_tracked:
        raise HTTPException(status_code=400, detail="이미 추적 중인 플레이스입니다")

    # place_name이 없으면 조회
    place_name = request.place_name
    if not place_name:
        place_info = await naver_service.get_place_info(request.place_id)
        place_name = place_info.get("name", "") if place_info else ""

    # 새로 등록
    new_tracked = TrackedPlace(
        place_id=request.place_id,
        place_name=place_name,
        keywords=request.keywords,
        is_active=1
    )
    db.add(new_tracked)
    await db.commit()
    await db.refresh(new_tracked)

    return {
        "message": "추적 등록 완료",
        "tracked": {
            "id": new_tracked.id,
            "place_id": new_tracked.place_id,
            "place_name": new_tracked.place_name,
            "keywords": new_tracked.keywords,
            "is_active": new_tracked.is_active
        }
    }


@router.put("/tracked/{place_id}")
async def update_tracked_place(
    place_id: str,
    request: UpdateTrackedPlaceRequest,
    db: AsyncSession = Depends(get_db)
):
    """추적 플레이스 정보 업데이트"""
    result = await db.execute(
        select(TrackedPlace).where(TrackedPlace.place_id == place_id)
    )
    tracked = result.scalar_one_or_none()

    if not tracked:
        raise HTTPException(status_code=404, detail="추적 중인 플레이스가 아닙니다")

    if request.place_name is not None:
        tracked.place_name = request.place_name
    if request.keywords is not None:
        tracked.keywords = request.keywords
    if request.is_active is not None:
        tracked.is_active = request.is_active

    await db.commit()

    return {
        "message": "업데이트 완료",
        "tracked": {
            "id": tracked.id,
            "place_id": tracked.place_id,
            "place_name": tracked.place_name,
            "keywords": tracked.keywords,
            "is_active": tracked.is_active
        }
    }


@router.delete("/tracked/{place_id}")
async def delete_tracked_place(
    place_id: str,
    db: AsyncSession = Depends(get_db)
):
    """추적 플레이스 삭제"""
    result = await db.execute(
        select(TrackedPlace).where(TrackedPlace.place_id == place_id)
    )
    tracked = result.scalar_one_or_none()

    if not tracked:
        raise HTTPException(status_code=404, detail="추적 중인 플레이스가 아닙니다")

    await db.delete(tracked)
    await db.commit()

    return {"message": "추적 삭제 완료", "place_id": place_id}


@router.post("/tracked/{place_id}/keywords")
async def add_keyword_to_tracked(
    place_id: str,
    keyword: str = Query(..., description="추가할 키워드"),
    db: AsyncSession = Depends(get_db)
):
    """추적 플레이스에 키워드 추가"""
    result = await db.execute(
        select(TrackedPlace).where(TrackedPlace.place_id == place_id)
    )
    tracked = result.scalar_one_or_none()

    if not tracked:
        raise HTTPException(status_code=404, detail="추적 중인 플레이스가 아닙니다")

    keywords = tracked.keywords or []
    if keyword not in keywords:
        keywords.append(keyword)
        tracked.keywords = keywords
        await db.commit()

    return {
        "message": f"키워드 '{keyword}' 추가 완료",
        "place_id": place_id,
        "keywords": tracked.keywords
    }


@router.delete("/tracked/{place_id}/keywords")
async def remove_keyword_from_tracked(
    place_id: str,
    keyword: str = Query(..., description="삭제할 키워드"),
    db: AsyncSession = Depends(get_db)
):
    """추적 플레이스에서 키워드 제거"""
    result = await db.execute(
        select(TrackedPlace).where(TrackedPlace.place_id == place_id)
    )
    tracked = result.scalar_one_or_none()

    if not tracked:
        raise HTTPException(status_code=404, detail="추적 중인 플레이스가 아닙니다")

    keywords = tracked.keywords or []
    if keyword in keywords:
        keywords.remove(keyword)
        tracked.keywords = keywords
        await db.commit()

    return {
        "message": f"키워드 '{keyword}' 제거 완료",
        "place_id": place_id,
        "keywords": tracked.keywords
    }


# ============== 스케줄러 API ==============

@router.get("/scheduler/status")
async def get_scheduler_status():
    """스케줄러 상태 조회"""
    return place_scheduler.get_status()


@router.post("/scheduler/collect-now")
async def trigger_collection_now():
    """데이터 수집 즉시 실행"""
    import asyncio
    asyncio.create_task(place_scheduler.collect_daily_data())
    return {"message": "데이터 수집 시작됨 (백그라운드에서 실행중)"}


@router.post("/scheduler/check-ranks-now")
async def trigger_rank_check_now():
    """순위 체크 즉시 실행"""
    import asyncio
    asyncio.create_task(place_scheduler.check_ranks())
    return {"message": "순위 체크 시작됨 (백그라운드에서 실행중)"}


@router.post("/scheduler/refresh-keywords-now")
async def trigger_saved_keywords_refresh_now():
    """저장된 키워드 순위 크롤링 즉시 실행 (순위 추적 페이지용)"""
    import asyncio
    asyncio.create_task(place_scheduler.refresh_saved_keywords())
    return {"message": "저장된 키워드 크롤링 시작됨 (백그라운드에서 실행중)"}


@router.post("/scheduler/update-activity-results-now")
async def trigger_activity_results_update_now():
    """Activity D+1/D+7 결과 업데이트 즉시 실행"""
    import asyncio
    asyncio.create_task(place_scheduler.update_activity_results())
    return {"message": "Activity 결과 업데이트 시작됨 (백그라운드에서 실행중)"}


@router.post("/scheduler/cleanup-expired-now")
async def trigger_cleanup_expired_now():
    """만료 데이터 정리 즉시 실행 (30일 경과 데이터 삭제)"""
    import asyncio
    asyncio.create_task(place_scheduler.cleanup_expired_data())
    return {"message": "만료 데이터 정리 시작됨 (백그라운드에서 실행중)"}


@router.post("/scheduler/training-now")
async def trigger_training_now():
    """키워드 파라미터 학습 즉시 실행"""
    import asyncio
    asyncio.create_task(place_scheduler.nightly_training_job())
    return {"message": "키워드 파라미터 학습 시작됨 (백그라운드에서 실행중)"}


# ============== 순위 요소 분석 API ==============

@router.get("/ranking-factors/{keyword}")
async def analyze_ranking_factors(
    keyword: str,
    max_places: int = Query(50, ge=10, le=100, description="분석할 플레이스 수"),
    save_result: bool = Query(True, description="분석 결과 저장 여부"),
    db: AsyncSession = Depends(get_db)
):
    """
    키워드별 순위 영향 요소 분석

    해당 키워드의 검색 결과를 분석하여
    방문자 리뷰, 블로그 리뷰, 저장수 중
    어떤 요소가 순위에 가장 큰 영향을 주는지 분석합니다.
    """
    result = await analyzer.analyze_ranking_factors(keyword, max_places)

    # 결과 저장
    if save_result and "error" not in result:
        factors = result["factors"]
        ranking = result["ranking"]

        analysis_record = KeywordFactorAnalysis(
            keyword=keyword,
            analyzed_places=result["analyzed_places"],
            visitor_review_correlation=factors["visitor_review"]["correlation"],
            blog_review_correlation=factors["blog_review"]["correlation"],
            save_count_correlation=factors["save_count"]["correlation"],
            visitor_review_impact=factors["visitor_review"]["impact_percent"],
            blog_review_impact=factors["blog_review"]["impact_percent"],
            save_count_impact=factors["save_count"]["impact_percent"],
            top_factor=ranking[0]["factor"] if ranking else None,
            analyzed_at=datetime.now()
        )
        db.add(analysis_record)
        await db.commit()

    return result


@router.get("/ranking-factors/{keyword}/history")
async def get_ranking_factors_history(
    keyword: str,
    days: int = Query(30, ge=1, le=90, description="조회 기간 (일)"),
    db: AsyncSession = Depends(get_db)
):
    """키워드 순위 요소 분석 히스토리 조회"""
    start_date = datetime.now() - timedelta(days=days)

    result = await db.execute(
        select(KeywordFactorAnalysis)
        .where(
            and_(
                KeywordFactorAnalysis.keyword == keyword,
                KeywordFactorAnalysis.analyzed_at >= start_date
            )
        )
        .order_by(KeywordFactorAnalysis.analyzed_at.desc())
    )
    records = result.scalars().all()

    return {
        "keyword": keyword,
        "period_days": days,
        "total_analyses": len(records),
        "history": [
            {
                "analyzed_at": r.analyzed_at.isoformat(),
                "analyzed_places": r.analyzed_places,
                "factors": {
                    "visitor_review": {
                        "correlation": r.visitor_review_correlation,
                        "impact_percent": r.visitor_review_impact
                    },
                    "blog_review": {
                        "correlation": r.blog_review_correlation,
                        "impact_percent": r.blog_review_impact
                    },
                    "save_count": {
                        "correlation": r.save_count_correlation,
                        "impact_percent": r.save_count_impact
                    }
                },
                "top_factor": r.top_factor
            }
            for r in records
        ]
    }


@router.post("/ranking-factors/compare")
async def compare_ranking_factors(
    keywords: List[str] = Query(..., description="비교할 키워드 목록", min_items=1, max_items=5)
):
    """
    여러 키워드의 순위 영향 요소 비교

    여러 키워드를 분석하여 각 키워드별로
    어떤 요소가 중요한지 비교합니다.
    """
    results = []

    for keyword in keywords:
        result = await analyzer.analyze_ranking_factors(keyword, 30)
        if "error" not in result:
            results.append({
                "keyword": keyword,
                "ranking": result["ranking"],
                "insight": result["insight"],
                "analyzed_places": result["analyzed_places"]
            })
        else:
            results.append({
                "keyword": keyword,
                "error": result["error"]
            })

    return {
        "keywords_analyzed": len(results),
        "results": results
    }


@router.get("/marketing-recommendation/{keyword}")
async def get_marketing_recommendation(
    keyword: str,
    db: AsyncSession = Depends(get_db)
):
    """
    키워드별 마케팅 추천

    해당 키워드에서 순위를 올리기 위해
    **지금 당장 해야 할 것**을 명확하게 알려줍니다.
    """
    # 분석 실행
    analysis = await analyzer.analyze_ranking_factors(keyword, 50)

    if "error" in analysis:
        raise HTTPException(status_code=400, detail=analysis["error"])

    # 마케팅 추천 생성
    recommendation = analyzer.generate_marketing_recommendation(analysis)

    # 분석 결과 저장
    factors = analysis["factors"]
    ranking = analysis["ranking"]

    analysis_record = KeywordFactorAnalysis(
        keyword=keyword,
        analyzed_places=analysis["analyzed_places"],
        visitor_review_correlation=factors["visitor_review"]["correlation"],
        blog_review_correlation=factors["blog_review"]["correlation"],
        save_count_correlation=factors["save_count"]["correlation"],
        visitor_review_impact=factors["visitor_review"]["impact_percent"],
        blog_review_impact=factors["blog_review"]["impact_percent"],
        save_count_impact=factors["save_count"]["impact_percent"],
        top_factor=ranking[0]["factor"] if ranking else None,
        analyzed_at=datetime.now()
    )
    db.add(analysis_record)
    await db.commit()

    return recommendation


# ============== 히든 지수 API ==============

class HiddenScoreRequest(BaseModel):
    place_url: str = Field(..., description="플레이스 URL 또는 ID")
    keyword: Optional[str] = Field(None, description="분석할 키워드 (순위 체크용)")


@router.post("/hidden-score")
async def get_hidden_score(request: HiddenScoreRequest):
    """
    플레이스 히든 지수 분석 (N1, N2, N3)

    adlog.kr과 동일한 히든 지수 정보를 제공하며,
    AI 기반 분석 인사이트를 추가로 제공합니다.

    - N1: 인기도 지수 (리뷰, 저장 등)
    - N2: 관련성 지수 (키워드 매칭, 정보 완성도)
    - N3: 랭킹 지수 (키워드 순위 기반)
    """
    place_id = naver_service.extract_place_id(request.place_url)
    if not place_id:
        raise HTTPException(status_code=400, detail="유효하지 않은 플레이스 URL입니다")

    # 키워드가 있으면 순위 조회 및 플레이스 정보 가져오기
    rank = None
    total_places = None
    rank_info = None
    place_info = None

    if request.keyword:
        rank_result = await naver_service.get_place_rank(place_id, request.keyword)
        rank = rank_result.get("rank")
        total_places = rank_result.get("total_results", 0)
        rank_info = {
            "keyword": request.keyword,
            "rank": rank,
            "total_results": total_places
        }

        # 순위 조회 시 target_place에서 데이터 가져오기
        if rank_result.get("target_place"):
            place_info = rank_result["target_place"]
        # 또는 competitors에서 찾기
        elif rank_result.get("competitors"):
            for comp in rank_result["competitors"]:
                if str(comp.get("place_id")) == str(place_id):
                    place_info = comp
                    break

    # 플레이스 정보가 없으면 직접 조회 시도
    if not place_info or not place_info.get("name"):
        place_info = await naver_service.get_place_info(place_id)

    if not place_info:
        raise HTTPException(status_code=404, detail="플레이스를 찾을 수 없습니다")

    # 히든 지수 계산
    hidden_scores = analyzer.calculate_hidden_scores(
        place_info,
        keyword=request.keyword or "",
        rank=rank,
        total_places=total_places
    )

    # AI 분석
    ai_analysis = analyzer.generate_ai_analysis(
        hidden_scores,
        place_info,
        keyword=request.keyword or ""
    )

    return {
        "place_id": place_id,
        "place_name": place_info.get("name", ""),
        "category": place_info.get("category", ""),
        "hidden_scores": {
            "n1": hidden_scores["n1"],
            "n2": hidden_scores["n2"],
            "n3": hidden_scores["n3"],
            "total": hidden_scores["total"],
            "details": hidden_scores["details"]
        },
        "raw_data": {
            "visitor_review_count": place_info.get("visitor_review_count", 0),
            "blog_review_count": place_info.get("blog_review_count", 0),
            "save_count": place_info.get("save_count", 0),
            "reservation_review_count": place_info.get("reservation_review_count", 0),
            "keywords": place_info.get("keywords", [])
        },
        "rank_info": rank_info,
        "ai_analysis": ai_analysis
    }


@router.get("/hidden-score/batch")
async def get_hidden_scores_batch(
    place_ids: str = Query(..., description="플레이스 ID 목록 (쉼표 구분)"),
    keyword: Optional[str] = Query(None, description="분석할 키워드")
):
    """
    여러 플레이스 히든 지수 일괄 조회

    adlog.kr처럼 여러 플레이스의 N1, N2, N3 점수를 한번에 조회합니다.
    """
    ids = [pid.strip() for pid in place_ids.split(",") if pid.strip()]

    if len(ids) > 20:
        raise HTTPException(status_code=400, detail="최대 20개까지 조회 가능합니다")

    results = []

    for place_id in ids:
        try:
            place_info = await naver_service.get_place_info(place_id)
            if not place_info:
                results.append({
                    "place_id": place_id,
                    "error": "플레이스를 찾을 수 없습니다"
                })
                continue

            # 키워드 순위 조회
            rank = None
            total_places = None
            if keyword:
                rank_result = await naver_service.get_place_rank(place_id, keyword)
                rank = rank_result.get("rank")
                total_places = rank_result.get("total_results", 0)

            # 히든 지수 계산
            hidden_scores = analyzer.calculate_hidden_scores(
                place_info,
                keyword=keyword or "",
                rank=rank,
                total_places=total_places
            )

            results.append({
                "place_id": place_id,
                "place_name": place_info.get("name", ""),
                "n1": hidden_scores["n1"],
                "n2": hidden_scores["n2"],
                "n3": hidden_scores["n3"],
                "total": hidden_scores["total"],
                "visitor_review_count": place_info.get("visitor_review_count", 0),
                "blog_review_count": place_info.get("blog_review_count", 0),
                "save_count": place_info.get("save_count", 0),
                "rank": rank
            })

        except Exception as e:
            logger.error(f"Error processing place {place_id}: {e}")
            results.append({
                "place_id": place_id,
                "error": str(e)
            })

    return {
        "keyword": keyword,
        "total": len(results),
        "results": results
    }


@router.get("/hidden-score/compare")
async def compare_hidden_scores(
    place_url: str = Query(..., description="내 플레이스 URL"),
    keyword: str = Query(..., description="비교 키워드"),
    compare_top: int = Query(10, ge=5, le=30, description="상위 몇 개와 비교할지")
):
    """
    내 플레이스 vs 상위권 플레이스 히든 지수 비교

    내 플레이스의 N1, N2, N3 점수를
    해당 키워드 상위권 플레이스와 비교 분석합니다.
    """
    place_id = naver_service.extract_place_id(place_url)
    if not place_id:
        raise HTTPException(status_code=400, detail="유효하지 않은 플레이스 URL입니다")

    # 내 플레이스 정보
    my_place = await naver_service.get_place_info(place_id)
    if not my_place:
        raise HTTPException(status_code=404, detail="플레이스를 찾을 수 없습니다")

    # 내 순위 조회
    my_rank_result = await naver_service.get_place_rank(place_id, keyword)
    my_rank = my_rank_result.get("rank")
    total_places = my_rank_result.get("total_results", 0)

    # 내 히든 지수
    my_hidden_scores = analyzer.calculate_hidden_scores(
        my_place, keyword, my_rank, total_places
    )

    # 상위권 플레이스 조회
    top_places = await naver_service.search_places(keyword, compare_top)

    # 상위권 평균 계산
    top_n1_sum = 0
    top_n2_sum = 0
    top_n3_sum = 0
    top_scores = []

    for i, place in enumerate(top_places):
        p_rank = i + 1
        scores = analyzer.calculate_hidden_scores(
            place, keyword, p_rank, len(top_places)
        )
        top_n1_sum += scores["n1"]
        top_n2_sum += scores["n2"]
        top_n3_sum += scores["n3"]
        top_scores.append({
            "rank": p_rank,
            "name": place.get("name", ""),
            "n1": scores["n1"],
            "n2": scores["n2"],
            "n3": scores["n3"],
            "total": scores["total"]
        })

    count = len(top_places) or 1
    top_avg = {
        "n1": round(top_n1_sum / count, 6),
        "n2": round(top_n2_sum / count, 6),
        "n3": round(top_n3_sum / count, 6)
    }

    # 비교 분석
    comparison = {
        "n1_gap": round(my_hidden_scores["n1"] - top_avg["n1"], 6),
        "n2_gap": round(my_hidden_scores["n2"] - top_avg["n2"], 6),
        "n3_gap": round(my_hidden_scores["n3"] - top_avg["n3"], 6)
    }

    # 부족한 영역 파악
    weaknesses = []
    if comparison["n1_gap"] < -0.1:
        weaknesses.append({
            "area": "N1(인기도)",
            "gap": round(comparison["n1_gap"] * 100, 1),
            "action": "리뷰 수와 저장 수를 늘리세요"
        })
    if comparison["n2_gap"] < -0.1:
        weaknesses.append({
            "area": "N2(관련성)",
            "gap": round(comparison["n2_gap"] * 100, 1),
            "action": "플레이스 정보를 완성하고 키워드 관련성을 높이세요"
        })
    if comparison["n3_gap"] < -0.1:
        weaknesses.append({
            "area": "N3(순위)",
            "gap": round(comparison["n3_gap"] * 100, 1),
            "action": "N1과 N2를 개선하면 순위가 자동으로 올라갑니다"
        })

    # AI 분석
    ai_analysis = analyzer.generate_ai_analysis(
        my_hidden_scores, my_place, keyword
    )

    return {
        "keyword": keyword,
        "my_place": {
            "place_id": place_id,
            "name": my_place.get("name", ""),
            "rank": my_rank,
            "hidden_scores": my_hidden_scores
        },
        "top_average": top_avg,
        "comparison": comparison,
        "weaknesses": weaknesses,
        "top_places": top_scores[:5],  # 상위 5개만 상세 표시
        "ai_analysis": ai_analysis
    }


# ============== 실시간 인기 키워드 API ==============

@router.get("/keywords/popular")
async def get_popular_keywords(
    limit: int = Query(20, ge=1, le=50, description="조회 개수"),
    days: int = Query(7, ge=1, le=30, description="기간 (일)"),
    db: AsyncSession = Depends(get_db)
):
    """
    실시간 인기 키워드 목록

    최근 N일간 가장 많이 검색된 키워드 목록을 반환합니다.
    """
    start_date = datetime.now() - timedelta(days=days)

    # 키워드별 검색 횟수 집계
    result = await db.execute(
        select(
            KeywordSearchLog.keyword,
            func.sum(KeywordSearchLog.search_count).label("total_count"),
            func.max(KeywordSearchLog.last_searched_at).label("last_searched")
        )
        .where(KeywordSearchLog.date >= start_date)
        .group_by(KeywordSearchLog.keyword)
        .order_by(func.sum(KeywordSearchLog.search_count).desc())
        .limit(limit)
    )
    keywords = result.all()

    return {
        "period_days": days,
        "total": len(keywords),
        "keywords": [
            {
                "keyword": kw.keyword,
                "search_count": kw.total_count,
                "last_searched_at": kw.last_searched.isoformat() if kw.last_searched else None
            }
            for kw in keywords
        ]
    }


@router.post("/keywords/log")
async def log_keyword_search(
    keyword: str = Query(..., min_length=2, description="검색 키워드"),
    db: AsyncSession = Depends(get_db)
):
    """
    키워드 검색 로그 기록

    키워드 검색 시 호출하여 인기 키워드 집계에 사용됩니다.
    """
    today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)

    # 오늘 해당 키워드 기록이 있는지 확인
    result = await db.execute(
        select(KeywordSearchLog).where(
            and_(
                KeywordSearchLog.keyword == keyword,
                KeywordSearchLog.date == today
            )
        )
    )
    existing = result.scalar_one_or_none()

    if existing:
        existing.search_count += 1
        existing.last_searched_at = datetime.now()
    else:
        new_log = KeywordSearchLog(
            keyword=keyword,
            search_count=1,
            date=today,
            last_searched_at=datetime.now()
        )
        db.add(new_log)

    await db.commit()

    return {"message": "키워드 검색 기록 완료", "keyword": keyword}


# ============== 키워드 순위 비교 분석 API ==============

@router.post("/keywords/snapshot")
async def save_keyword_rank_snapshot(
    keyword: str = Query(..., min_length=2, description="키워드"),
    db: AsyncSession = Depends(get_db)
):
    """
    키워드 순위 스냅샷 저장

    현재 키워드의 순위 데이터를 저장하여 누적 분석에 사용합니다.
    """
    # 키워드 검색
    places = await naver_service.search_places(keyword, 50)

    if not places:
        raise HTTPException(status_code=404, detail="검색 결과가 없습니다")

    # 스냅샷 데이터 생성
    rank_data = [
        {
            "rank": idx + 1,
            "place_id": p.get("place_id"),
            "name": p.get("name"),
            "category": p.get("category"),
            "visitor_review_count": p.get("visitor_review_count", 0),
            "blog_review_count": p.get("blog_review_count", 0),
            "save_count": p.get("save_count", 0)
        }
        for idx, p in enumerate(places)
    ]

    # 스냅샷 저장
    snapshot = KeywordRankSnapshot(
        keyword=keyword,
        rank_data=rank_data,
        total_places=len(places),
        snapshot_at=datetime.now()
    )
    db.add(snapshot)

    # 키워드 검색 로그도 기록
    today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    result = await db.execute(
        select(KeywordSearchLog).where(
            and_(
                KeywordSearchLog.keyword == keyword,
                KeywordSearchLog.date == today
            )
        )
    )
    existing_log = result.scalar_one_or_none()

    if existing_log:
        existing_log.search_count += 1
        existing_log.last_searched_at = datetime.now()
    else:
        new_log = KeywordSearchLog(
            keyword=keyword,
            search_count=1,
            date=today,
            last_searched_at=datetime.now()
        )
        db.add(new_log)

    await db.commit()

    return {
        "message": "스냅샷 저장 완료",
        "keyword": keyword,
        "total_places": len(places),
        "snapshot_at": datetime.now().isoformat(),
        "top_5": rank_data[:5]
    }


@router.get("/keywords/{keyword}/snapshots")
async def get_keyword_snapshots(
    keyword: str,
    days: int = Query(7, ge=1, le=30, description="조회 기간 (일)"),
    db: AsyncSession = Depends(get_db)
):
    """
    키워드 순위 스냅샷 히스토리 조회

    해당 키워드의 과거 순위 데이터를 조회합니다.
    """
    start_date = datetime.now() - timedelta(days=days)

    result = await db.execute(
        select(KeywordRankSnapshot)
        .where(
            and_(
                KeywordRankSnapshot.keyword == keyword,
                KeywordRankSnapshot.snapshot_at >= start_date
            )
        )
        .order_by(KeywordRankSnapshot.snapshot_at.desc())
    )
    snapshots = result.scalars().all()

    return {
        "keyword": keyword,
        "period_days": days,
        "total_snapshots": len(snapshots),
        "snapshots": [
            {
                "snapshot_at": s.snapshot_at.isoformat(),
                "total_places": s.total_places,
                "rank_data": s.rank_data
            }
            for s in snapshots
        ]
    }


@router.get("/keywords/{keyword}/analysis")
async def analyze_keyword_history(
    keyword: str,
    place_id: Optional[str] = Query(None, description="특정 플레이스 순위 변화 추적"),
    days: int = Query(7, ge=1, le=30, description="분석 기간 (일)"),
    db: AsyncSession = Depends(get_db)
):
    """
    키워드 누적 데이터 분석

    키워드의 순위 변화, 특정 플레이스의 순위 추이 등을 분석합니다.
    """
    start_date = datetime.now() - timedelta(days=days)

    result = await db.execute(
        select(KeywordRankSnapshot)
        .where(
            and_(
                KeywordRankSnapshot.keyword == keyword,
                KeywordRankSnapshot.snapshot_at >= start_date
            )
        )
        .order_by(KeywordRankSnapshot.snapshot_at.asc())
    )
    snapshots = result.scalars().all()

    if not snapshots:
        return {
            "keyword": keyword,
            "has_data": False,
            "message": "누적된 데이터가 없습니다. 먼저 스냅샷을 저장해주세요."
        }

    analysis = {
        "keyword": keyword,
        "has_data": True,
        "period_days": days,
        "total_snapshots": len(snapshots),
        "first_snapshot": snapshots[0].snapshot_at.isoformat(),
        "last_snapshot": snapshots[-1].snapshot_at.isoformat()
    }

    # 특정 플레이스 순위 변화 추적
    if place_id:
        place_history = []
        for snapshot in snapshots:
            rank_data = snapshot.rank_data or []
            found_rank = None
            found_data = None
            for item in rank_data:
                if str(item.get("place_id")) == str(place_id):
                    found_rank = item.get("rank")
                    found_data = item
                    break

            place_history.append({
                "snapshot_at": snapshot.snapshot_at.isoformat(),
                "rank": found_rank,
                "data": found_data
            })

        # 순위 변화 계산
        ranks = [h["rank"] for h in place_history if h["rank"]]
        if len(ranks) >= 2:
            rank_change = ranks[0] - ranks[-1]  # 양수면 순위 하락, 음수면 상승
            best_rank = min(ranks)
            worst_rank = max(ranks)
        else:
            rank_change = None
            best_rank = ranks[0] if ranks else None
            worst_rank = ranks[0] if ranks else None

        analysis["place_analysis"] = {
            "place_id": place_id,
            "history": place_history,
            "rank_change": rank_change,
            "best_rank": best_rank,
            "worst_rank": worst_rank,
            "current_rank": ranks[-1] if ranks else None
        }

    # 전체 순위 변동 분석 (상위 10위)
    if len(snapshots) >= 2:
        first_snapshot = snapshots[0].rank_data or []
        last_snapshot = snapshots[-1].rank_data or []

        # 첫 스냅샷 대비 현재 순위 변화
        rank_changes = []
        last_ranks = {str(item.get("place_id")): item for item in last_snapshot}

        for item in first_snapshot[:20]:
            pid = str(item.get("place_id"))
            old_rank = item.get("rank")
            current = last_ranks.get(pid)

            if current:
                new_rank = current.get("rank")
                change = old_rank - new_rank  # 양수면 순위 상승
                rank_changes.append({
                    "place_id": pid,
                    "name": item.get("name"),
                    "old_rank": old_rank,
                    "new_rank": new_rank,
                    "change": change
                })

        # 상승/하락 업체 분류
        rising = sorted([r for r in rank_changes if r["change"] > 0], key=lambda x: x["change"], reverse=True)[:5]
        falling = sorted([r for r in rank_changes if r["change"] < 0], key=lambda x: x["change"])[:5]

        analysis["rank_movement"] = {
            "rising_places": rising,
            "falling_places": falling
        }

    # 현재 상위 10위
    if snapshots:
        latest = snapshots[-1].rank_data or []
        analysis["current_top_10"] = latest[:10]

    return analysis


@router.get("/keywords/{keyword}/compare-places")
async def compare_places_in_keyword(
    keyword: str,
    place_ids: str = Query(..., description="비교할 플레이스 ID (쉼표 구분)"),
    days: int = Query(7, ge=1, le=30, description="분석 기간 (일)"),
    db: AsyncSession = Depends(get_db)
):
    """
    키워드 내 여러 플레이스 순위 비교

    여러 플레이스의 순위 변화를 한눈에 비교합니다.
    """
    ids = [pid.strip() for pid in place_ids.split(",") if pid.strip()]

    if len(ids) > 10:
        raise HTTPException(status_code=400, detail="최대 10개까지 비교 가능합니다")

    start_date = datetime.now() - timedelta(days=days)

    result = await db.execute(
        select(KeywordRankSnapshot)
        .where(
            and_(
                KeywordRankSnapshot.keyword == keyword,
                KeywordRankSnapshot.snapshot_at >= start_date
            )
        )
        .order_by(KeywordRankSnapshot.snapshot_at.asc())
    )
    snapshots = result.scalars().all()

    if not snapshots:
        return {
            "keyword": keyword,
            "has_data": False,
            "message": "누적된 데이터가 없습니다."
        }

    # 각 플레이스별 순위 히스토리
    place_histories = {pid: [] for pid in ids}

    for snapshot in snapshots:
        rank_data = snapshot.rank_data or []
        rank_map = {str(item.get("place_id")): item for item in rank_data}

        for pid in ids:
            item = rank_map.get(pid)
            place_histories[pid].append({
                "snapshot_at": snapshot.snapshot_at.isoformat(),
                "rank": item.get("rank") if item else None,
                "name": item.get("name") if item else None
            })

    # 비교 결과
    comparison = []
    for pid in ids:
        history = place_histories[pid]
        ranks = [h["rank"] for h in history if h["rank"]]
        name = next((h["name"] for h in history if h["name"]), None)

        if ranks:
            comparison.append({
                "place_id": pid,
                "name": name,
                "current_rank": ranks[-1] if ranks else None,
                "best_rank": min(ranks),
                "worst_rank": max(ranks),
                "rank_change": ranks[0] - ranks[-1] if len(ranks) >= 2 else 0,
                "history": history
            })
        else:
            comparison.append({
                "place_id": pid,
                "name": None,
                "current_rank": None,
                "message": "순위권 밖 또는 데이터 없음"
            })

    # 현재 순위 기준 정렬
    comparison = sorted(
        comparison,
        key=lambda x: x.get("current_rank") or 999
    )

    return {
        "keyword": keyword,
        "period_days": days,
        "total_snapshots": len(snapshots),
        "comparison": comparison
    }


@router.get("/keywords/{keyword}/trend")
async def get_keyword_rank_trend(
    keyword: str,
    place_id: Optional[str] = Query(None, description="특정 플레이스 순위 추적"),
    db: AsyncSession = Depends(get_db)
):
    """
    키워드 순위 추세 분석

    1일전, 15일전, 20일전, 25일전, 30일전 순위를 한눈에 비교합니다.
    adlog.kr 추세 분석과 동일한 기능입니다.
    """
    # 비교할 기간들
    periods = [1, 15, 20, 25, 30]
    now = datetime.now()

    period_data = {}

    for days in periods:
        target_date = now - timedelta(days=days)
        start_of_day = target_date.replace(hour=0, minute=0, second=0, microsecond=0)
        end_of_day = target_date.replace(hour=23, minute=59, second=59, microsecond=999999)

        # 해당 날짜의 스냅샷 조회
        result = await db.execute(
            select(KeywordRankSnapshot)
            .where(
                and_(
                    KeywordRankSnapshot.keyword == keyword,
                    KeywordRankSnapshot.snapshot_at >= start_of_day,
                    KeywordRankSnapshot.snapshot_at <= end_of_day
                )
            )
            .order_by(KeywordRankSnapshot.snapshot_at.desc())
            .limit(1)
        )
        snapshot = result.scalar_one_or_none()

        if snapshot:
            period_data[f"{days}일전"] = {
                "date": snapshot.snapshot_at.isoformat(),
                "has_data": True,
                "rank_data": snapshot.rank_data,
                "total_places": snapshot.total_places
            }
        else:
            period_data[f"{days}일전"] = {
                "has_data": False,
                "message": "해당 날짜 데이터 없음"
            }

    # 현재 데이터도 추가
    current_result = await db.execute(
        select(KeywordRankSnapshot)
        .where(KeywordRankSnapshot.keyword == keyword)
        .order_by(KeywordRankSnapshot.snapshot_at.desc())
        .limit(1)
    )
    current_snapshot = current_result.scalar_one_or_none()

    if current_snapshot:
        period_data["현재"] = {
            "date": current_snapshot.snapshot_at.isoformat(),
            "has_data": True,
            "rank_data": current_snapshot.rank_data,
            "total_places": current_snapshot.total_places
        }

    # 특정 플레이스 순위 추적
    place_trend = None
    if place_id:
        place_trend = {
            "place_id": place_id,
            "ranks": {}
        }

        for period_name, data in period_data.items():
            if data.get("has_data") and data.get("rank_data"):
                for item in data["rank_data"]:
                    if str(item.get("place_id")) == str(place_id):
                        place_trend["ranks"][period_name] = {
                            "rank": item.get("rank"),
                            "name": item.get("name"),
                            "visitor_review_count": item.get("visitor_review_count"),
                            "blog_review_count": item.get("blog_review_count"),
                            "save_count": item.get("save_count")
                        }
                        break
                else:
                    place_trend["ranks"][period_name] = {"rank": None, "message": "순위권 밖"}
            else:
                place_trend["ranks"][period_name] = {"rank": None, "message": "데이터 없음"}

        # 순위 변화 계산
        current_rank = place_trend["ranks"].get("현재", {}).get("rank")
        day30_rank = place_trend["ranks"].get("30일전", {}).get("rank")

        if current_rank and day30_rank:
            place_trend["rank_change_30d"] = day30_rank - current_rank  # 양수면 상승
        else:
            place_trend["rank_change_30d"] = None

    # 전체 상위 10위 업체들의 기간별 순위 변화
    top_places_trend = []
    if current_snapshot and current_snapshot.rank_data:
        for item in current_snapshot.rank_data[:10]:
            pid = str(item.get("place_id"))
            place_info = {
                "place_id": pid,
                "name": item.get("name"),
                "category": item.get("category"),
                "current_rank": item.get("rank"),
                "period_ranks": {}
            }

            # 각 기간별 순위 찾기
            for period_name, data in period_data.items():
                if period_name == "현재":
                    continue
                if data.get("has_data") and data.get("rank_data"):
                    for past_item in data["rank_data"]:
                        if str(past_item.get("place_id")) == pid:
                            place_info["period_ranks"][period_name] = past_item.get("rank")
                            break
                    else:
                        place_info["period_ranks"][period_name] = None
                else:
                    place_info["period_ranks"][period_name] = None

            # 30일전 대비 변화
            rank_30d = place_info["period_ranks"].get("30일전")
            if rank_30d and place_info["current_rank"]:
                place_info["change_30d"] = rank_30d - place_info["current_rank"]
            else:
                place_info["change_30d"] = None

            top_places_trend.append(place_info)

    return {
        "keyword": keyword,
        "periods": ["현재", "1일전", "15일전", "20일전", "25일전", "30일전"],
        "period_data": period_data,
        "place_trend": place_trend,
        "top_places_trend": top_places_trend
    }


@router.post("/keywords/{keyword}/snapshot-periods")
async def save_multiple_snapshots_for_testing(
    keyword: str,
    db: AsyncSession = Depends(get_db)
):
    """
    테스트용: 여러 기간의 스냅샷 한번에 저장

    실제로는 스케줄러가 매일 저장하지만,
    테스트를 위해 현재 데이터를 여러 날짜로 저장합니다.
    """
    places = await naver_service.search_places(keyword, 50)

    if not places:
        raise HTTPException(status_code=404, detail="검색 결과가 없습니다")

    rank_data = [
        {
            "rank": idx + 1,
            "place_id": p.get("place_id"),
            "name": p.get("name"),
            "category": p.get("category"),
            "visitor_review_count": p.get("visitor_review_count", 0),
            "blog_review_count": p.get("blog_review_count", 0),
            "save_count": p.get("save_count", 0)
        }
        for idx, p in enumerate(places)
    ]

    # 여러 기간에 대해 스냅샷 저장 (테스트용)
    periods = [0, 1, 15, 20, 25, 30]
    saved = []

    for days in periods:
        snapshot_time = datetime.now() - timedelta(days=days)

        snapshot = KeywordRankSnapshot(
            keyword=keyword,
            rank_data=rank_data,
            total_places=len(places),
            snapshot_at=snapshot_time
        )
        db.add(snapshot)
        saved.append(f"{days}일전")

    await db.commit()

    return {
        "message": "테스트 스냅샷 저장 완료",
        "keyword": keyword,
        "saved_periods": saved
    }


# ============== 리뷰 목록 API ==============

@router.get("/reviews/{place_id}/visitor")
async def get_visitor_reviews(
    place_id: str,
    limit: int = Query(20, ge=1, le=50, description="조회 개수")
):
    """
    방문자 리뷰 목록 조회

    날짜, 예약/일반 구분, 리뷰 내용을 가져옵니다.
    """
    reviews = await naver_service.get_visitor_reviews(place_id, limit)

    return {
        "place_id": place_id,
        "total": len(reviews),
        "reviews": reviews
    }


@router.get("/reviews/{place_id}/blog")
async def get_blog_reviews(
    place_id: str,
    limit: int = Query(20, ge=1, le=50, description="조회 개수")
):
    """
    블로그 리뷰 목록 조회

    블로거명, 날짜, 제목, 링크를 가져옵니다.
    """
    reviews = await naver_service.get_blog_reviews(place_id, limit)

    return {
        "place_id": place_id,
        "total": len(reviews),
        "reviews": reviews
    }


@router.get("/reviews/{place_id}/all")
async def get_all_reviews(
    place_id: str,
    limit: int = Query(10, ge=1, le=30, description="각 타입별 조회 개수")
):
    """
    모든 리뷰 통합 조회 (방문자 + 블로그)
    """
    visitor_reviews = await naver_service.get_visitor_reviews(place_id, limit)
    blog_reviews = await naver_service.get_blog_reviews(place_id, limit)

    return {
        "place_id": place_id,
        "visitor_reviews": {
            "total": len(visitor_reviews),
            "reviews": visitor_reviews
        },
        "blog_reviews": {
            "total": len(blog_reviews),
            "reviews": blog_reviews
        }
    }


# ============== 히든 키워드 + 일별 순위 테이블 API ==============

@router.get("/hidden-keywords/{place_id}/full")
async def get_hidden_keywords_with_ranks(
    place_id: str,
    days: int = Query(15, ge=1, le=30, description="순위 히스토리 기간"),
    db: AsyncSession = Depends(get_db)
):
    """
    히든 키워드 + 일별 순위 테이블

    adlog.kr의 히든 키워드 페이지와 동일한 형태로
    발굴된 키워드들의 일별 순위를 테이블 형태로 제공합니다.
    """
    # 플레이스 정보 조회
    place_info = await naver_service.get_place_info(place_id)

    # 히든 키워드 발굴
    hidden_keywords = await analyzer.find_hidden_keywords(place_id, place_info, max_keywords=35)

    # 각 키워드별 일별 순위 조회
    keyword_ranks = []

    for kw_data in hidden_keywords:
        keyword = kw_data["keyword"]

        # 해당 키워드의 스냅샷 히스토리 조회
        start_date = datetime.now() - timedelta(days=days)
        result = await db.execute(
            select(KeywordRankSnapshot)
            .where(
                and_(
                    KeywordRankSnapshot.keyword == keyword,
                    KeywordRankSnapshot.snapshot_at >= start_date
                )
            )
            .order_by(KeywordRankSnapshot.snapshot_at.desc())
        )
        snapshots = result.scalars().all()

        # 날짜별 순위 매핑
        daily_ranks = {}
        for snapshot in snapshots:
            date_str = snapshot.snapshot_at.strftime("%m-%d")
            rank_data = snapshot.rank_data or []

            # 해당 place_id의 순위 찾기
            place_rank = None
            for item in rank_data:
                if str(item.get("place_id")) == str(place_id):
                    place_rank = item.get("rank")
                    break

            daily_ranks[date_str] = place_rank

        keyword_ranks.append({
            "keyword": keyword,
            "current_rank": kw_data["rank"],
            "total_results": kw_data["total_results"],
            "potential": kw_data["potential"],
            "daily_ranks": daily_ranks
        })

    # 날짜 리스트 생성 (최근 N일)
    date_list = []
    for i in range(days):
        date = datetime.now() - timedelta(days=i)
        date_list.append(date.strftime("%m-%d"))

    return {
        "place_id": place_id,
        "place_name": place_info.get("name", "") if place_info else "",
        "place_info": {
            "visitor_review_count": place_info.get("visitor_review_count", 0) if place_info else 0,
            "blog_review_count": place_info.get("blog_review_count", 0) if place_info else 0,
            "save_count": place_info.get("save_count", 0) if place_info else 0,
            "category": place_info.get("category", "") if place_info else "",
            "keywords": place_info.get("keywords", []) if place_info else []
        },
        "hidden_keyword_count": len(keyword_ranks),
        "date_columns": date_list,
        "keyword_ranks": keyword_ranks
    }


@router.post("/hidden-keywords/{place_id}/snapshot-all")
async def snapshot_all_hidden_keywords(
    place_id: str,
    db: AsyncSession = Depends(get_db)
):
    """
    히든 키워드 전체 스냅샷 저장

    발굴된 모든 히든 키워드에 대해 순위 스냅샷을 저장합니다.
    일별 순위 추적을 위해 매일 실행하면 됩니다.
    """
    # 플레이스 정보 조회
    place_info = await naver_service.get_place_info(place_id)

    # 히든 키워드 발굴
    hidden_keywords = await analyzer.find_hidden_keywords(place_id, place_info, max_keywords=35)

    saved_keywords = []

    for kw_data in hidden_keywords:
        keyword = kw_data["keyword"]

        # 해당 키워드로 검색하여 스냅샷 저장
        places = await naver_service.search_places(keyword, 50)

        if places:
            rank_data = [
                {
                    "rank": idx + 1,
                    "place_id": p.get("place_id"),
                    "name": p.get("name"),
                    "category": p.get("category"),
                    "visitor_review_count": p.get("visitor_review_count", 0),
                    "blog_review_count": p.get("blog_review_count", 0),
                    "save_count": p.get("save_count", 0)
                }
                for idx, p in enumerate(places)
            ]

            snapshot = KeywordRankSnapshot(
                keyword=keyword,
                rank_data=rank_data,
                total_places=len(places),
                snapshot_at=datetime.now()
            )
            db.add(snapshot)
            saved_keywords.append(keyword)

    await db.commit()

    return {
        "message": f"{len(saved_keywords)}개 키워드 스냅샷 저장 완료",
        "place_id": place_id,
        "saved_keywords": saved_keywords
    }


# ============== 플레이스명 분석 API ==============

@router.get("/analyze-by-name")
async def analyze_places_by_name(
    name: str = Query(..., min_length=2, description="플레이스명 (예: 아뜰리에 호수)"),
    max_results: int = Query(50, ge=10, le=100, description="최대 검색 결과 수")
):
    """
    플레이스명(브랜드명) 분석 - adlog.kr의 NA 플레이스 키워드 분석과 동일

    플레이스명을 검색하여 해당 이름을 가진 모든 지점들의:
    - N1, N2, N3 히든 지수
    - 방문자 리뷰수, 블로그 리뷰수, 저장수
    - 대표 키워드
    를 한눈에 비교 분석합니다.

    예: "아뜰리에 호수" 검색 시 전국 모든 지점의 데이터를 비교할 수 있습니다.
    """
    # 플레이스명으로 검색
    places = await naver_service.search_places(name, max_results)

    if not places:
        return {
            "search_name": name,
            "total": 0,
            "places": [],
            "message": "검색 결과가 없습니다"
        }

    # 각 플레이스에 대해 N1, N2, N3 지수 계산
    results = []

    for idx, place in enumerate(places):
        # 순위는 검색 결과 순서 기반
        rank = idx + 1

        # N1, N2, N3 계산 - 키워드 없이 순수 플레이스 데이터 기반
        hidden_scores = analyzer.calculate_hidden_scores(
            place,
            keyword=name,  # 검색어를 키워드로 사용
            rank=rank,
            total_places=len(places)
        )

        # 업종 정보 생성 (category 기반)
        category = place.get("category", "")
        business_type = f"생활,편의>{category}" if category else ""

        results.append({
            "rank": rank,
            "place_id": place.get("place_id"),
            "place_name": place.get("name", ""),
            "category": category,
            "business_type": business_type,
            "address": place.get("address", ""),
            "road_address": place.get("road_address", ""),
            "visitor_review_count": place.get("visitor_review_count", 0),
            "blog_review_count": place.get("blog_review_count", 0),
            "save_count": place.get("save_count", 0),
            "n1": hidden_scores["n1"],
            "n2": hidden_scores["n2"],
            "n3": hidden_scores["n3"],
            "keywords": place.get("keywords", [])
        })

    # 통계 정보
    total_visitor_reviews = sum(p.get("visitor_review_count", 0) for p in places)
    total_blog_reviews = sum(p.get("blog_review_count", 0) for p in places)
    avg_n1 = sum(r["n1"] for r in results) / len(results) if results else 0
    avg_n2 = sum(r["n2"] for r in results) / len(results) if results else 0
    avg_n3 = sum(r["n3"] for r in results) / len(results) if results else 0

    return {
        "search_name": name,
        "total": len(results),
        "statistics": {
            "total_visitor_reviews": total_visitor_reviews,
            "total_blog_reviews": total_blog_reviews,
            "avg_n1": round(avg_n1, 6),
            "avg_n2": round(avg_n2, 6),
            "avg_n3": round(avg_n3, 6)
        },
        "info": {
            "description": "플레이스명(브랜드명)으로 검색한 업체 분석 데이터입니다",
            "n1_description": "N1: 인기도 지수 (방문자리뷰, 블로그리뷰, 저장수 기반)",
            "n2_description": "N2: 관련성 지수 (키워드 및 정보 완성도 기반)",
            "n3_description": "N3: 랭킹 지수 (검색 순위 기반)"
        },
        "places": results
    }


@router.get("/analyze-by-name/compare")
async def compare_places_by_name(
    name: str = Query(..., min_length=2, description="플레이스명"),
    place_ids: str = Query(None, description="비교할 특정 플레이스 ID들 (쉼표 구분, 선택사항)"),
    top_n: int = Query(10, ge=1, le=50, description="상위 N개만 상세 비교")
):
    """
    플레이스명 분석 - 지점간 상세 비교

    특정 플레이스명으로 검색 후, 지정한 지점들 또는 상위 N개 지점을
    상세 비교 분석합니다.
    """
    # 플레이스명으로 검색
    places = await naver_service.search_places(name, 50)

    if not places:
        return {
            "search_name": name,
            "total": 0,
            "comparison": [],
            "message": "검색 결과가 없습니다"
        }

    # 특정 place_ids가 지정된 경우 필터링
    if place_ids:
        target_ids = [pid.strip() for pid in place_ids.split(",")]
        filtered_places = [p for p in places if str(p.get("place_id")) in target_ids]
        if filtered_places:
            places = filtered_places

    # 상위 N개만 선택
    places = places[:top_n]

    # 각 플레이스 상세 분석
    comparison = []

    for idx, place in enumerate(places):
        rank = idx + 1

        # N1, N2, N3 계산
        hidden_scores = analyzer.calculate_hidden_scores(
            place,
            keyword=name,
            rank=rank,
            total_places=len(places)
        )

        # AI 분석
        ai_analysis = analyzer.generate_ai_analysis(
            hidden_scores,
            place,
            keyword=name
        )

        comparison.append({
            "rank": rank,
            "place_id": place.get("place_id"),
            "place_name": place.get("name", ""),
            "category": place.get("category", ""),
            "address": place.get("address", ""),
            "metrics": {
                "visitor_review_count": place.get("visitor_review_count", 0),
                "blog_review_count": place.get("blog_review_count", 0),
                "save_count": place.get("save_count", 0)
            },
            "hidden_scores": {
                "n1": hidden_scores["n1"],
                "n2": hidden_scores["n2"],
                "n3": hidden_scores["n3"],
                "total": hidden_scores["total"],
                "details": hidden_scores["details"]
            },
            "ai_analysis": ai_analysis,
            "keywords": place.get("keywords", [])
        })

    # 순위별 랭킹
    rankings = {
        "by_n1": sorted(comparison, key=lambda x: x["hidden_scores"]["n1"], reverse=True),
        "by_n2": sorted(comparison, key=lambda x: x["hidden_scores"]["n2"], reverse=True),
        "by_n3": sorted(comparison, key=lambda x: x["hidden_scores"]["n3"], reverse=True),
        "by_visitor_reviews": sorted(comparison, key=lambda x: x["metrics"]["visitor_review_count"], reverse=True),
        "by_blog_reviews": sorted(comparison, key=lambda x: x["metrics"]["blog_review_count"], reverse=True),
        "by_saves": sorted(comparison, key=lambda x: x["metrics"]["save_count"], reverse=True)
    }

    # 각 랭킹에서 상위 3개만 추출
    top_rankings = {
        "n1_top3": [{"rank": i+1, "name": p["place_name"], "score": p["hidden_scores"]["n1"]} for i, p in enumerate(rankings["by_n1"][:3])],
        "n2_top3": [{"rank": i+1, "name": p["place_name"], "score": p["hidden_scores"]["n2"]} for i, p in enumerate(rankings["by_n2"][:3])],
        "n3_top3": [{"rank": i+1, "name": p["place_name"], "score": p["hidden_scores"]["n3"]} for i, p in enumerate(rankings["by_n3"][:3])],
        "visitor_review_top3": [{"rank": i+1, "name": p["place_name"], "count": p["metrics"]["visitor_review_count"]} for i, p in enumerate(rankings["by_visitor_reviews"][:3])],
        "blog_review_top3": [{"rank": i+1, "name": p["place_name"], "count": p["metrics"]["blog_review_count"]} for i, p in enumerate(rankings["by_blog_reviews"][:3])],
        "save_top3": [{"rank": i+1, "name": p["place_name"], "count": p["metrics"]["save_count"]} for i, p in enumerate(rankings["by_saves"][:3])]
    }

    return {
        "search_name": name,
        "total_compared": len(comparison),
        "top_rankings": top_rankings,
        "comparison": comparison
    }


@router.get("/analyze-by-name/keywords")
async def analyze_brand_keywords(
    name: str = Query(..., min_length=2, description="플레이스명 (브랜드명)"),
    max_places: int = Query(20, ge=5, le=50, description="분석할 최대 플레이스 수")
):
    """
    브랜드 대표 키워드 분석

    해당 브랜드명으로 검색된 모든 지점들에서
    공통적으로 사용되는 대표 키워드를 추출합니다.
    """
    # 플레이스명으로 검색
    places = await naver_service.search_places(name, max_places)

    if not places:
        return {
            "search_name": name,
            "total_places": 0,
            "keywords": [],
            "message": "검색 결과가 없습니다"
        }

    # 모든 키워드 수집 및 빈도 계산
    keyword_counts = {}
    place_with_keywords = 0

    for place in places:
        keywords = place.get("keywords", [])
        if keywords:
            place_with_keywords += 1
            for kw in keywords:
                keyword_counts[kw] = keyword_counts.get(kw, 0) + 1

    # 빈도순 정렬
    sorted_keywords = sorted(
        keyword_counts.items(),
        key=lambda x: x[1],
        reverse=True
    )

    # 결과 생성
    keyword_analysis = []
    for kw, count in sorted_keywords[:30]:  # 상위 30개
        # 해당 키워드가 포함된 플레이스 비율
        coverage = round(count / len(places) * 100, 1)

        keyword_analysis.append({
            "keyword": kw,
            "count": count,
            "coverage_percent": coverage,
            "is_common": coverage >= 50  # 50% 이상이면 공통 키워드
        })

    # 공통 키워드 (50% 이상 지점에서 사용)
    common_keywords = [k for k in keyword_analysis if k["is_common"]]

    return {
        "search_name": name,
        "total_places": len(places),
        "places_with_keywords": place_with_keywords,
        "common_keywords": common_keywords,
        "all_keywords": keyword_analysis,
        "recommendation": {
            "use_keywords": [k["keyword"] for k in common_keywords[:5]],
            "message": f"'{name}' 브랜드의 공통 키워드입니다. 이 키워드들을 플레이스 정보에 포함하세요."
        }
    }


# ============== 플레이스 저장 체크 API ==============

class SaveTrackerCreateRequest(BaseModel):
    place_url: str = Field(..., description="플레이스 URL")
    keyword: str = Field(..., description="검색 키워드")
    group_name: str = Field(default="기본", description="그룹명")
    memo: Optional[str] = Field(None, description="메모")


class SaveTrackerUpdateRequest(BaseModel):
    group_name: Optional[str] = None
    memo: Optional[str] = None
    is_active: Optional[int] = None


@router.post("/save-tracker")
async def create_save_tracker(
    request: SaveTrackerCreateRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    플레이스 저장 체크 등록

    플레이스 URL과 키워드를 등록하여 저장수 변화를 추적합니다.
    adlog.kr의 '플레이스 저장 체크' 기능과 동일합니다.
    """
    # place_id 추출
    place_id = naver_service.extract_place_id(request.place_url)
    if not place_id:
        raise HTTPException(status_code=400, detail="유효하지 않은 플레이스 URL입니다")

    # 이미 등록되어 있는지 확인
    existing = await db.execute(
        select(PlaceSaveTracker).where(
            and_(
                PlaceSaveTracker.place_id == place_id,
                PlaceSaveTracker.keyword == request.keyword
            )
        )
    )
    existing_tracker = existing.scalar_one_or_none()

    if existing_tracker:
        raise HTTPException(status_code=400, detail="이미 등록된 플레이스+키워드 조합입니다")

    # 현재 데이터 조회
    rank_result = await naver_service.get_place_rank(place_id, request.keyword)
    place_info = None

    # target_place에서 정보 가져오기
    if rank_result.get("target_place"):
        place_info = rank_result["target_place"]
    # 또는 competitors에서 찾기
    elif rank_result.get("competitors"):
        for comp in rank_result["competitors"]:
            if str(comp.get("place_id")) == str(place_id):
                place_info = comp
                break

    # 없으면 직접 조회
    if not place_info:
        place_info = await naver_service.get_place_info(place_id)

    if not place_info:
        raise HTTPException(status_code=404, detail="플레이스 정보를 찾을 수 없습니다")

    # 트래커 생성
    new_tracker = PlaceSaveTracker(
        place_id=place_id,
        place_name=place_info.get("name", ""),
        place_url=request.place_url,
        keyword=request.keyword,
        group_name=request.group_name,
        current_rank=rank_result.get("rank"),
        current_save_count=place_info.get("save_count", 0),
        visitor_review_count=place_info.get("visitor_review_count", 0),
        blog_review_count=place_info.get("blog_review_count", 0),
        memo=request.memo,
        is_active=1,
        last_checked_at=datetime.now()
    )
    db.add(new_tracker)
    await db.commit()
    await db.refresh(new_tracker)

    return {
        "message": "저장 체크 등록 완료",
        "tracker": {
            "id": new_tracker.id,
            "place_id": new_tracker.place_id,
            "place_name": new_tracker.place_name,
            "keyword": new_tracker.keyword,
            "group_name": new_tracker.group_name,
            "current_rank": new_tracker.current_rank,
            "current_save_count": new_tracker.current_save_count,
            "visitor_review_count": new_tracker.visitor_review_count,
            "blog_review_count": new_tracker.blog_review_count
        }
    }


@router.get("/save-tracker/groups")
async def get_save_tracker_groups(
    db: AsyncSession = Depends(get_db)
):
    """
    저장 체크 그룹 목록 조회

    등록된 모든 그룹과 각 그룹의 트래커 수를 반환합니다.
    """
    result = await db.execute(
        select(
            PlaceSaveTracker.group_name,
            func.count(PlaceSaveTracker.id).label("count"),
            func.sum(PlaceSaveTracker.is_active).label("active_count")
        )
        .group_by(PlaceSaveTracker.group_name)
    )
    groups = result.all()

    return {
        "total_groups": len(groups),
        "groups": [
            {
                "name": g.group_name or "기본",
                "count": g.count,
                "active_count": g.active_count or 0
            }
            for g in groups
        ]
    }


@router.get("/save-tracker/summary")
async def get_save_tracker_summary(
    db: AsyncSession = Depends(get_db)
):
    """
    저장 체크 요약 통계

    전체 트래커 현황과 최근 변화 요약을 제공합니다.
    """
    # 전체 트래커 수
    total_result = await db.execute(
        select(func.count(PlaceSaveTracker.id))
    )
    total_count = total_result.scalar()

    # 활성 트래커 수
    active_result = await db.execute(
        select(func.count(PlaceSaveTracker.id)).where(PlaceSaveTracker.is_active == 1)
    )
    active_count = active_result.scalar()

    # 최근 7일 히스토리 기록 수
    week_ago = datetime.now() - timedelta(days=7)
    history_result = await db.execute(
        select(func.count(PlaceSaveHistory.id)).where(PlaceSaveHistory.recorded_at >= week_ago)
    )
    recent_history_count = history_result.scalar()

    # 최근 히스토리에서 순위 상승/하락 업체
    recent_history = await db.execute(
        select(PlaceSaveHistory)
        .where(PlaceSaveHistory.recorded_at >= week_ago)
        .order_by(PlaceSaveHistory.recorded_at.desc())
    )
    histories = recent_history.scalars().all()

    rising_count = sum(1 for h in histories if h.rank_change and h.rank_change > 0)
    falling_count = sum(1 for h in histories if h.rank_change and h.rank_change < 0)
    save_increasing_count = sum(1 for h in histories if h.save_change and h.save_change > 0)

    return {
        "total_trackers": total_count,
        "active_trackers": active_count,
        "recent_7days": {
            "history_records": recent_history_count,
            "rank_rising": rising_count,
            "rank_falling": falling_count,
            "save_increasing": save_increasing_count
        },
        "info": {
            "description": "플레이스 저장 체크 현황입니다",
            "auto_check_schedule": "매주 월, 목요일 자동 체크"
        }
    }


@router.post("/save-tracker/check-all")
async def check_all_save_trackers(
    record_history: bool = Query(True, description="히스토리에 기록할지 여부"),
    db: AsyncSession = Depends(get_db)
):
    """
    모든 저장 체크 일괄 실행

    활성화된 모든 트래커의 현재 상태를 조회하고 히스토리에 기록합니다.
    스케줄러에서 주 2회 (월, 목) 자동 실행됩니다.
    """
    # 활성화된 트래커만 조회
    result = await db.execute(
        select(PlaceSaveTracker).where(PlaceSaveTracker.is_active == 1)
    )
    trackers = result.scalars().all()

    if not trackers:
        return {
            "message": "활성화된 트래커가 없습니다",
            "checked_count": 0,
            "results": []
        }

    results = []
    success_count = 0
    error_count = 0

    for tracker in trackers:
        try:
            # 현재 데이터 조회
            rank_result = await naver_service.get_place_rank(tracker.place_id, tracker.keyword)
            place_info = None

            if rank_result.get("target_place"):
                place_info = rank_result["target_place"]
            elif rank_result.get("competitors"):
                for comp in rank_result["competitors"]:
                    if str(comp.get("place_id")) == str(tracker.place_id):
                        place_info = comp
                        break

            if not place_info:
                place_info = await naver_service.get_place_info(tracker.place_id)

            if not place_info:
                results.append({
                    "tracker_id": tracker.id,
                    "place_name": tracker.place_name,
                    "keyword": tracker.keyword,
                    "status": "error",
                    "error": "플레이스 정보를 찾을 수 없습니다"
                })
                error_count += 1
                continue

            new_rank = rank_result.get("rank")
            new_save_count = place_info.get("save_count", 0)
            new_visitor_review = place_info.get("visitor_review_count", 0)
            new_blog_review = place_info.get("blog_review_count", 0)

            # 변화량 계산
            rank_change = None
            if tracker.current_rank and new_rank:
                rank_change = tracker.current_rank - new_rank

            save_change = new_save_count - tracker.current_save_count
            visitor_review_change = new_visitor_review - tracker.visitor_review_count
            blog_review_change = new_blog_review - tracker.blog_review_count

            # 트래커 업데이트
            tracker.current_rank = new_rank
            tracker.current_save_count = new_save_count
            tracker.visitor_review_count = new_visitor_review
            tracker.blog_review_count = new_blog_review
            tracker.last_checked_at = datetime.now()

            # 히스토리 기록
            if record_history:
                history = PlaceSaveHistory(
                    tracker_id=tracker.id,
                    rank=new_rank,
                    save_count=new_save_count,
                    visitor_review_count=new_visitor_review,
                    blog_review_count=new_blog_review,
                    rank_change=rank_change,
                    save_change=save_change,
                    visitor_review_change=visitor_review_change,
                    blog_review_change=blog_review_change,
                    recorded_at=datetime.now()
                )
                db.add(history)

            results.append({
                "tracker_id": tracker.id,
                "place_name": tracker.place_name,
                "keyword": tracker.keyword,
                "status": "success",
                "current_rank": new_rank,
                "current_save_count": new_save_count,
                "rank_change": rank_change,
                "save_change": save_change
            })
            success_count += 1

        except Exception as e:
            logger.error(f"Error checking tracker {tracker.id}: {e}")
            results.append({
                "tracker_id": tracker.id,
                "place_name": tracker.place_name,
                "keyword": tracker.keyword,
                "status": "error",
                "error": str(e)
            })
            error_count += 1

    await db.commit()

    return {
        "message": f"체크 완료: 성공 {success_count}개, 실패 {error_count}개",
        "checked_count": len(trackers),
        "success_count": success_count,
        "error_count": error_count,
        "checked_at": datetime.now().isoformat(),
        "results": results
    }


@router.get("/save-tracker")
async def list_save_trackers(
    group_name: Optional[str] = Query(None, description="그룹 필터"),
    is_active: Optional[int] = Query(None, description="활성화 상태 필터 (1: 활성, 0: 비활성)"),
    db: AsyncSession = Depends(get_db)
):
    """
    저장 체크 목록 조회

    등록된 모든 플레이스 저장 체크 목록을 조회합니다.
    """
    query = select(PlaceSaveTracker).order_by(PlaceSaveTracker.created_at.desc())

    if group_name:
        query = query.where(PlaceSaveTracker.group_name == group_name)
    if is_active is not None:
        query = query.where(PlaceSaveTracker.is_active == is_active)

    result = await db.execute(query)
    trackers = result.scalars().all()

    # 그룹별 통계
    group_stats = {}
    for t in trackers:
        g = t.group_name or "기본"
        if g not in group_stats:
            group_stats[g] = {"count": 0, "active_count": 0}
        group_stats[g]["count"] += 1
        if t.is_active:
            group_stats[g]["active_count"] += 1

    return {
        "total": len(trackers),
        "group_stats": group_stats,
        "trackers": [
            {
                "id": t.id,
                "place_id": t.place_id,
                "place_name": t.place_name,
                "keyword": t.keyword,
                "group_name": t.group_name,
                "current_rank": t.current_rank,
                "current_save_count": t.current_save_count,
                "visitor_review_count": t.visitor_review_count,
                "blog_review_count": t.blog_review_count,
                "memo": t.memo,
                "is_active": t.is_active,
                "last_checked_at": t.last_checked_at.isoformat() if t.last_checked_at else None,
                "created_at": t.created_at.isoformat()
            }
            for t in trackers
        ]
    }


@router.get("/save-tracker/{tracker_id}")
async def get_save_tracker_detail(
    tracker_id: int,
    history_days: int = Query(30, ge=1, le=90, description="히스토리 조회 기간 (일)"),
    db: AsyncSession = Depends(get_db)
):
    """
    저장 체크 상세 조회

    특정 트래커의 상세 정보와 히스토리를 조회합니다.
    """
    result = await db.execute(
        select(PlaceSaveTracker).where(PlaceSaveTracker.id == tracker_id)
    )
    tracker = result.scalar_one_or_none()

    if not tracker:
        raise HTTPException(status_code=404, detail="트래커를 찾을 수 없습니다")

    # 히스토리 조회
    start_date = datetime.now() - timedelta(days=history_days)
    history_result = await db.execute(
        select(PlaceSaveHistory)
        .where(
            and_(
                PlaceSaveHistory.tracker_id == tracker_id,
                PlaceSaveHistory.recorded_at >= start_date
            )
        )
        .order_by(PlaceSaveHistory.recorded_at.desc())
    )
    history = history_result.scalars().all()

    # 변화량 계산
    save_change_total = 0
    rank_change_total = 0
    if history:
        # 첫 기록과 마지막 기록 비교
        first = history[-1]
        last = history[0]
        save_change_total = last.save_count - first.save_count
        if first.rank and last.rank:
            rank_change_total = first.rank - last.rank  # 양수면 순위 상승

    return {
        "tracker": {
            "id": tracker.id,
            "place_id": tracker.place_id,
            "place_name": tracker.place_name,
            "place_url": tracker.place_url,
            "keyword": tracker.keyword,
            "group_name": tracker.group_name,
            "current_rank": tracker.current_rank,
            "current_save_count": tracker.current_save_count,
            "visitor_review_count": tracker.visitor_review_count,
            "blog_review_count": tracker.blog_review_count,
            "memo": tracker.memo,
            "is_active": tracker.is_active,
            "last_checked_at": tracker.last_checked_at.isoformat() if tracker.last_checked_at else None,
            "created_at": tracker.created_at.isoformat()
        },
        "summary": {
            "history_days": history_days,
            "record_count": len(history),
            "save_change_total": save_change_total,
            "rank_change_total": rank_change_total
        },
        "history": [
            {
                "recorded_at": h.recorded_at.isoformat(),
                "rank": h.rank,
                "save_count": h.save_count,
                "visitor_review_count": h.visitor_review_count,
                "blog_review_count": h.blog_review_count,
                "rank_change": h.rank_change,
                "save_change": h.save_change
            }
            for h in history
        ]
    }


@router.put("/save-tracker/{tracker_id}")
async def update_save_tracker(
    tracker_id: int,
    request: SaveTrackerUpdateRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    저장 체크 정보 수정

    그룹, 메모, 활성화 상태를 수정합니다.
    """
    result = await db.execute(
        select(PlaceSaveTracker).where(PlaceSaveTracker.id == tracker_id)
    )
    tracker = result.scalar_one_or_none()

    if not tracker:
        raise HTTPException(status_code=404, detail="트래커를 찾을 수 없습니다")

    if request.group_name is not None:
        tracker.group_name = request.group_name
    if request.memo is not None:
        tracker.memo = request.memo
    if request.is_active is not None:
        tracker.is_active = request.is_active

    await db.commit()

    return {
        "message": "수정 완료",
        "tracker": {
            "id": tracker.id,
            "place_id": tracker.place_id,
            "place_name": tracker.place_name,
            "keyword": tracker.keyword,
            "group_name": tracker.group_name,
            "memo": tracker.memo,
            "is_active": tracker.is_active
        }
    }


@router.delete("/save-tracker/{tracker_id}")
async def delete_save_tracker(
    tracker_id: int,
    db: AsyncSession = Depends(get_db)
):
    """
    저장 체크 삭제

    트래커와 관련된 모든 히스토리도 함께 삭제됩니다.
    """
    result = await db.execute(
        select(PlaceSaveTracker).where(PlaceSaveTracker.id == tracker_id)
    )
    tracker = result.scalar_one_or_none()

    if not tracker:
        raise HTTPException(status_code=404, detail="트래커를 찾을 수 없습니다")

    await db.delete(tracker)
    await db.commit()

    return {"message": "삭제 완료", "tracker_id": tracker_id}


@router.post("/save-tracker/{tracker_id}/check")
async def check_save_tracker(
    tracker_id: int,
    record_history: bool = Query(True, description="히스토리에 기록할지 여부"),
    db: AsyncSession = Depends(get_db)
):
    """
    저장 체크 즉시 실행

    현재 순위와 저장수를 조회하고 히스토리에 기록합니다.
    """
    result = await db.execute(
        select(PlaceSaveTracker).where(PlaceSaveTracker.id == tracker_id)
    )
    tracker = result.scalar_one_or_none()

    if not tracker:
        raise HTTPException(status_code=404, detail="트래커를 찾을 수 없습니다")

    # 현재 데이터 조회
    rank_result = await naver_service.get_place_rank(tracker.place_id, tracker.keyword)
    place_info = None

    # target_place에서 정보 가져오기
    if rank_result.get("target_place"):
        place_info = rank_result["target_place"]
    # 또는 competitors에서 찾기
    elif rank_result.get("competitors"):
        for comp in rank_result["competitors"]:
            if str(comp.get("place_id")) == str(tracker.place_id):
                place_info = comp
                break

    if not place_info:
        place_info = await naver_service.get_place_info(tracker.place_id)

    if not place_info:
        raise HTTPException(status_code=404, detail="플레이스 정보를 찾을 수 없습니다")

    new_rank = rank_result.get("rank")
    new_save_count = place_info.get("save_count", 0)
    new_visitor_review = place_info.get("visitor_review_count", 0)
    new_blog_review = place_info.get("blog_review_count", 0)

    # 변화량 계산
    rank_change = None
    save_change = None
    visitor_review_change = None
    blog_review_change = None

    if tracker.current_rank and new_rank:
        rank_change = tracker.current_rank - new_rank  # 양수면 순위 상승

    save_change = new_save_count - tracker.current_save_count
    visitor_review_change = new_visitor_review - tracker.visitor_review_count
    blog_review_change = new_blog_review - tracker.blog_review_count

    # 트래커 업데이트
    old_data = {
        "rank": tracker.current_rank,
        "save_count": tracker.current_save_count,
        "visitor_review_count": tracker.visitor_review_count,
        "blog_review_count": tracker.blog_review_count
    }

    tracker.current_rank = new_rank
    tracker.current_save_count = new_save_count
    tracker.visitor_review_count = new_visitor_review
    tracker.blog_review_count = new_blog_review
    tracker.last_checked_at = datetime.now()

    # 히스토리 기록
    if record_history:
        history = PlaceSaveHistory(
            tracker_id=tracker.id,
            rank=new_rank,
            save_count=new_save_count,
            visitor_review_count=new_visitor_review,
            blog_review_count=new_blog_review,
            rank_change=rank_change,
            save_change=save_change,
            visitor_review_change=visitor_review_change,
            blog_review_change=blog_review_change,
            recorded_at=datetime.now()
        )
        db.add(history)

    await db.commit()

    return {
        "message": "체크 완료",
        "tracker_id": tracker_id,
        "place_name": tracker.place_name,
        "keyword": tracker.keyword,
        "previous": old_data,
        "current": {
            "rank": new_rank,
            "save_count": new_save_count,
            "visitor_review_count": new_visitor_review,
            "blog_review_count": new_blog_review
        },
        "changes": {
            "rank_change": rank_change,
            "save_change": save_change,
            "visitor_review_change": visitor_review_change,
            "blog_review_change": blog_review_change
        },
        "checked_at": datetime.now().isoformat()
    }


# ============== 키워드 검색 트렌드 API (네이버 데이터랩) ==============

@router.get("/keyword-trend")
async def get_keyword_trend(
    keyword: str = Query(..., min_length=2, description="검색 키워드"),
    days: int = Query(30, ge=7, le=365, description="조회 기간 (일)")
):
    """
    키워드 검색 트렌드 조회

    네이버 데이터랩 API를 사용하여 키워드의 검색 트렌드를 조회합니다.
    - 일별 검색량 추이 (상대값 0-100)
    - 평균, 최고, 최저 검색량
    - 트렌드 방향 (상승/하락/유지)
    """
    end_date = datetime.now().strftime("%Y-%m-%d")
    start_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")

    result = await datalab_service.get_search_trend([keyword], start_date, end_date)

    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])

    return result


@router.get("/keyword-trend/compare")
async def compare_keyword_trends(
    keywords: str = Query(..., description="비교할 키워드들 (쉼표 구분, 최대 5개)"),
    days: int = Query(30, ge=7, le=365, description="조회 기간 (일)")
):
    """
    키워드 검색 트렌드 비교

    여러 키워드의 검색 트렌드를 비교 분석합니다.
    - 키워드별 검색량 추이
    - 키워드 간 순위
    - 가장 강한/약한 키워드
    """
    keyword_list = [k.strip() for k in keywords.split(",") if k.strip()]

    if len(keyword_list) < 2:
        raise HTTPException(status_code=400, detail="최소 2개 키워드가 필요합니다")

    if len(keyword_list) > 5:
        raise HTTPException(status_code=400, detail="최대 5개 키워드까지 비교 가능합니다")

    result = await datalab_service.compare_keywords(keyword_list, days)

    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])

    return result


@router.get("/keyword-trend/weekly-pattern")
async def get_weekly_pattern(
    keyword: str = Query(..., min_length=2, description="검색 키워드")
):
    """
    키워드 요일별 검색 패턴 분석

    최근 4주 데이터를 기반으로 요일별 평균 검색량을 분석합니다.
    - 요일별 평균 검색량
    - 가장 검색이 많은/적은 요일
    - 주중/주말 패턴 인사이트
    """
    result = await datalab_service.get_weekly_pattern(keyword)

    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])

    return result


@router.get("/keyword-trend/seasonal")
async def get_seasonal_trend(
    keyword: str = Query(..., min_length=2, description="검색 키워드"),
    months: int = Query(12, ge=3, le=24, description="조회 기간 (개월)")
):
    """
    키워드 월별 시즌 트렌드 분석

    월별 검색량 추이를 분석하여 시즌성을 파악합니다.
    - 월별 검색량 추이
    - 시즌성 여부 판단
    - 피크 시즌 / 비수기 파악
    """
    result = await datalab_service.get_seasonal_trend(keyword, months)

    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])

    return result


@router.get("/keyword-trend/place-keywords")
async def analyze_place_keywords_trend(
    place_url: str = Query(..., description="플레이스 URL"),
    days: int = Query(30, ge=7, le=90, description="조회 기간 (일)")
):
    """
    플레이스 대표 키워드 트렌드 분석

    플레이스에 등록된 대표 키워드들의 검색 트렌드를 비교 분석합니다.
    """
    place_id = naver_service.extract_place_id(place_url)
    if not place_id:
        raise HTTPException(status_code=400, detail="유효하지 않은 플레이스 URL입니다")

    # 플레이스 정보 조회
    place_info = await naver_service.get_place_info(place_id)
    if not place_info:
        raise HTTPException(status_code=404, detail="플레이스를 찾을 수 없습니다")

    keywords = place_info.get("keywords", [])
    if not keywords:
        return {
            "place_id": place_id,
            "place_name": place_info.get("name", ""),
            "message": "등록된 키워드가 없습니다",
            "keywords": []
        }

    # 최대 5개 키워드만
    keywords = keywords[:5]

    # 트렌드 비교
    trend_result = await datalab_service.compare_keywords(keywords, days)

    return {
        "place_id": place_id,
        "place_name": place_info.get("name", ""),
        "analyzed_keywords": keywords,
        "trend_data": trend_result
    }


@router.get("/keyword-volume")
async def get_keyword_volume(
    keywords: str = Query(..., description="검색할 키워드 (쉼표로 구분, 최대 5개)")
):
    """
    키워드 월간 검색량 조회

    네이버 검색광고 API를 통해 실제 월간 검색량을 조회합니다.
    API 키가 없으면 DataLab 지수 기반 추정치를 반환합니다.

    Returns:
        - monthly_pc: PC 월간 검색량
        - monthly_mobile: 모바일 월간 검색량
        - monthly_total: 총 월간 검색량
        - competition: 경쟁 정도 (HIGH/MEDIUM/LOW)
        - is_estimated: 추정치 여부 (API 키 없을 때 True)
    """
    from app.services.keyword_volume import keyword_volume_service

    keyword_list = [k.strip() for k in keywords.split(",") if k.strip()]

    if not keyword_list:
        raise HTTPException(status_code=400, detail="키워드를 입력해주세요")

    if len(keyword_list) > 5:
        raise HTTPException(status_code=400, detail="최대 5개 키워드만 조회 가능합니다")

    result = await keyword_volume_service.get_keyword_volume(keyword_list)

    return {
        "keywords": result,
        "total_keywords": len(result)
    }


@router.get("/related-keywords")
async def get_related_keywords(
    keyword: str = Query(..., description="기준 키워드 (예: 서울반지공방)"),
    place_name: str = Query("", description="업체명 (예: 아뜰리에 호수 홍대점) - 지역 추출용"),
    my_visitor_reviews: int = Query(0, description="내 업체 방문자 리뷰 수"),
    my_blog_reviews: int = Query(0, description="내 업체 블로그 리뷰 수"),
    limit: int = Query(10, description="최대 결과 수", ge=1, le=20)
):
    """
    연관 키워드 + 검색량 + 공략 가능성 조회

    업체명에서 지역 추출 → 근처 지역 + 업종 조합 키워드 추천
    내 리뷰 수와 경쟁도를 비교해서 공략 가능성 분석

    예: 업체 "아뜰리에 호수 홍대점" (리뷰 8000개)
    → 홍대반지공방: 공략 가능성 높음 ✓
    → 연남커플링: 공략 가능성 중간 △
    """
    from app.services.keyword_volume import keyword_volume_service

    if not keyword.strip():
        raise HTTPException(status_code=400, detail="키워드를 입력해주세요")

    result = await keyword_volume_service.get_related_keywords(
        keyword.strip(),
        place_name.strip(),
        limit,
        my_visitor_reviews,
        my_blog_reviews
    )

    return {
        "hint_keyword": keyword,
        "place_name": place_name,
        "my_reviews": my_visitor_reviews + my_blog_reviews,
        "related_keywords": result,
        "total_count": len(result)
    }
