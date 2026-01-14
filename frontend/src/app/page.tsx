"use client";

import { useState, useEffect, useCallback } from "react";
import { usePathname } from "next/navigation";
import { Search, Bell, TrendingUp, TrendingDown, Building2, ChevronDown, Clock, Target, Zap, RefreshCw, ExternalLink, Minus, Star, BarChart3, Sparkles } from "lucide-react";
import { keywordsApi, SavedKeyword, trendApi } from "@/lib/api";
import { useRouter } from "next/navigation";
import { toast } from "sonner";
import { useAuth } from "@/contexts/AuthContext";

interface RecentSearch {
  placeId: string;
  placeName: string;
  category: string;
  keyword: string;
  rank: number | null;
  searchedAt: string;
}

interface RegisteredBusiness {
  placeId: string;
  placeName: string;
  category: string;
}

interface KeywordTrendData {
  keyword: string;
  average: number;
  trend: string;
  ratio?: number;
  monthlyVolume?: number;  // 실제 월간 검색량
  isEstimated?: boolean;   // 추정치 여부
}

interface RelatedKeyword {
  keyword: string;
  searchVolume: number;
  type: 'variation' | 'location' | 'category';
  chance?: string;  // 높음/중간/낮음
  chanceDesc?: string;  // 설명
  chanceColor?: string;  // 색상 코드
  competition?: string;  // 경쟁도
  // 경쟁력 분석 (가중치: 방문자 50% + 블로그 50%)
  avgVisitor?: number;  // 상위 3개 방문자리뷰 평균
  avgBlog?: number;  // 상위 3개 블로그리뷰 평균
  avgTotal?: number;  // 상위 3개 총 리뷰 평균
  myVisitor?: number;  // 내 방문자리뷰
  myBlog?: number;  // 내 블로그리뷰
  myTotal?: number;  // 내 총 리뷰
  visitorRatio?: number;  // 방문자 달성률 (%)
  blogRatio?: number;  // 블로그 달성률 (%)
  competitiveness?: number;  // 종합 경쟁력 (%)
  top3?: Array<{name: string; visitor: number; blog: number; total: number}>;
}

// 공통 스타일 정의
const styles = {
  card: {
    background: 'white',
    borderRadius: '16px',
    padding: '24px',
    border: '1px solid #e2e8f0'
  } as React.CSSProperties,
  input: {
    width: '100%',
    padding: '12px 16px',
    borderRadius: '12px',
    border: '1px solid #e2e8f0',
    fontSize: '14px',
    background: 'white',
    outline: 'none',
    transition: 'border-color 0.2s, box-shadow 0.2s'
  } as React.CSSProperties,
  inputWhite: {
    padding: '12px 16px',
    borderRadius: '12px',
    border: 'none',
    fontSize: '14px',
    background: 'rgba(255,255,255,0.95)',
    outline: 'none'
  } as React.CSSProperties,
  btnPrimary: {
    background: 'linear-gradient(135deg, #6366f1, #8b5cf6)',
    color: 'white',
    padding: '12px 24px',
    borderRadius: '12px',
    fontWeight: '600' as const,
    fontSize: '14px',
    border: 'none',
    cursor: 'pointer',
    display: 'flex' as const,
    alignItems: 'center' as const,
    gap: '8px'
  } as React.CSSProperties,
  btnSecondary: {
    background: 'white',
    color: '#64748b',
    padding: '10px 20px',
    borderRadius: '12px',
    fontWeight: '500' as const,
    fontSize: '14px',
    border: '1px solid #e2e8f0',
    cursor: 'pointer'
  } as React.CSSProperties,
  iconButton: {
    padding: '10px',
    borderRadius: '12px',
    border: '1px solid #e2e8f0',
    background: 'white',
    cursor: 'pointer'
  } as React.CSSProperties
};

export default function Dashboard() {
  const router = useRouter();
  const pathname = usePathname();
  const { user, loading: authLoading } = useAuth();
  const [selectedBusiness, setSelectedBusiness] = useState<RegisteredBusiness | null>(null);
  const [businesses, setBusinesses] = useState<RegisteredBusiness[]>([]);
  const [recentSearches, setRecentSearches] = useState<RecentSearch[]>([]);
  const [allTrackedKeywords, setAllTrackedKeywords] = useState<SavedKeyword[]>([]);
  const [keywordTrends, setKeywordTrends] = useState<KeywordTrendData[]>([]);
  const [relatedKeywords, setRelatedKeywords] = useState<RelatedKeyword[]>([]);
  const [loading, setLoading] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const [trendLoading, setTrendLoading] = useState(false);
  const [relatedLoading, setRelatedLoading] = useState(false);
  const [businessDropdownOpen, setBusinessDropdownOpen] = useState(false);

  // 빠른 조회 폼
  const [quickPlaceName, setQuickPlaceName] = useState("");
  const [quickKeyword, setQuickKeyword] = useState("");
  const [quickTraffic, setQuickTraffic] = useState("");

  // localStorage에서 데이터 로드하는 함수
  const loadLocalStorageData = useCallback(() => {
    const savedSearches = localStorage.getItem('recentSearches');
    if (savedSearches) {
      setRecentSearches(JSON.parse(savedSearches));
    }

    const savedBusinesses = localStorage.getItem('registeredBusinesses');
    if (savedBusinesses) {
      const parsed = JSON.parse(savedBusinesses);
      setBusinesses(parsed);
      if (parsed.length > 0 && !selectedBusiness) {
        setSelectedBusiness(parsed[0]);
      }
    }
  }, [selectedBusiness]);

  // 페이지 마운트 시 데이터 로드 (인증 후)
  useEffect(() => {
    loadLocalStorageData();
  }, [pathname]);

  // 인증 완료 후 키워드 로드
  useEffect(() => {
    if (!authLoading && user) {
      loadAllTrackedKeywords();
    }
  }, [authLoading, user]);

  // 윈도우 포커스 시 데이터 다시 로드
  useEffect(() => {
    const handleFocus = () => {
      loadLocalStorageData();
      loadAllTrackedKeywords();
    };
    window.addEventListener('focus', handleFocus);
    return () => window.removeEventListener('focus', handleFocus);
  }, [loadLocalStorageData]);

  // 모든 추적 키워드 로드 (업체 필터 없이)
  const loadAllTrackedKeywords = async () => {
    setLoading(true);
    try {
      const keywords = await keywordsApi.getAll();
      setAllTrackedKeywords(keywords);
      // 트렌드 로드는 useEffect에서 selectedBusiness에 맞춰 처리
    } catch (error) {
      console.error('키워드 로드 실패:', error);
    } finally {
      setLoading(false);
    }
  };

  // 최근 조회 키워드 기반으로 트렌드 로드
  useEffect(() => {
    if (recentSearches.length > 0 && allTrackedKeywords.length === 0) {
      const recentKeywords = [...new Set(recentSearches.slice(0, 5).map(s => s.keyword))];
      if (recentKeywords.length > 0) {
        loadKeywordTrends(recentKeywords);
      }
    }
  }, [recentSearches, allTrackedKeywords]);

  const loadKeywordTrends = async (keywords: string[]) => {
    // 빈 배열이거나 유효하지 않은 키워드면 스킵
    const validKeywords = keywords.filter(k => k && k.trim());
    if (validKeywords.length === 0) {
      setKeywordTrends([]);
      return;
    }
    setTrendLoading(true);
    try {
      // 먼저 검색량 조회 (최대 5개)
      const volumeKeywords = validKeywords.slice(0, 5);
      let volumeData: Record<string, any> = {};

      try {
        if (volumeKeywords.length > 0) {
          const volumeResult = await trendApi.getVolume(volumeKeywords);
          volumeData = volumeResult?.keywords || {};
        }
      } catch (e) {
        console.error('검색량 조회 실패:', e);
      }

      // 트렌드 조회
      if (validKeywords.length === 1) {
        const result = await trendApi.getTrend(validKeywords[0], 30);
        if (result?.keywords?.[0]) {
          const kw = result.keywords[0];
          const vol = volumeData[kw.keyword];
          setKeywordTrends([{
            keyword: kw.keyword,
            average: kw.stats?.average || 0,
            trend: kw.stats?.trend || 'stable',
            ratio: 100,
            monthlyVolume: vol?.monthly_total || 0,
            isEstimated: vol?.is_estimated
          }]);
        }
      } else {
        const result = await trendApi.compare(validKeywords.slice(0, 5), 30);
        if (result?.keywords) {
          const trends = result.keywords.map((k: any) => {
            const vol = volumeData[k.keyword];
            return {
              keyword: k.keyword,
              average: k.stats?.average || 0,
              trend: k.stats?.trend || 'stable',
              ratio: k.ratio || 0,
              monthlyVolume: vol?.monthly_total || 0,
              isEstimated: vol?.is_estimated
            };
          });
          // 검색량 높은 순으로 정렬
          trends.sort((a: KeywordTrendData, b: KeywordTrendData) =>
            (b.monthlyVolume || 0) - (a.monthlyVolume || 0)
          );
          setKeywordTrends(trends);
        }
      }
    } catch (error) {
      console.error('트렌드 로드 실패:', error);
    } finally {
      setTrendLoading(false);
    }
  };

  // 관련 키워드 추천 (지역 + 업종 기반 + 공략 가능성 분석)
  const loadRelatedKeywords = async (trackedKeywordData: SavedKeyword[]) => {
    if (trackedKeywordData.length === 0) return;
    setRelatedLoading(true);

    try {
      // 첫 번째 추적 키워드 + 업체명 + 리뷰 수로 연관 키워드 조회
      const baseKeyword = trackedKeywordData[0].keyword;
      const placeName = trackedKeywordData[0].place_name || "";
      const myVisitorReviews = trackedKeywordData[0].visitor_review_count || 0;
      const myBlogReviews = trackedKeywordData[0].blog_review_count || 0;

      // 내 리뷰 수 기반으로 공략 가능성 분석
      const result = await trendApi.getRelated(
        baseKeyword,
        placeName,
        myVisitorReviews,
        myBlogReviews,
        8
      );

      if (result?.related_keywords?.length > 0) {
        const related = result.related_keywords
          .filter((k: any) => k.keyword !== baseKeyword.replace(/\s/g, ''))
          .slice(0, 6)
          .map((k: any) => ({
            keyword: k.keyword,
            searchVolume: k.monthly_total,
            type: 'variation' as const,
            chance: k.chance,
            chanceDesc: k.chance_desc,
            chanceColor: k.chance_color,
            competition: k.competition,
            avgVisitor: k.avg_visitor,
            avgBlog: k.avg_blog,
            avgTotal: k.avg_total,
            myVisitor: k.my_visitor,
            myBlog: k.my_blog,
            myTotal: k.my_total,
            visitorRatio: k.visitor_ratio,
            blogRatio: k.blog_ratio,
            competitiveness: k.competitiveness,
            top3: k.top3
          }));

        setRelatedKeywords(related);
      }
    } catch (error) {
      console.error('관련 키워드 로드 실패:', error);
    } finally {
      setRelatedLoading(false);
    }
  };

  // 추적 키워드가 로드되거나 선택된 업체가 변경되면 관련 키워드도 로드
  useEffect(() => {
    try {
      // 선택된 업체의 키워드만 필터링
      const filteredKeywords = selectedBusiness
        ? allTrackedKeywords.filter(k => String(k.place_id) === String(selectedBusiness.placeId))
        : allTrackedKeywords;

      if (filteredKeywords.length > 0) {
        loadRelatedKeywords(filteredKeywords.slice(0, 5)).catch(console.error);

        // 트렌드도 해당 업체 키워드로 갱신
        const keywordNames = filteredKeywords.slice(0, 5).map(k => k.keyword);
        loadKeywordTrends(keywordNames).catch(console.error);
      } else {
        // 선택된 업체에 키워드가 없으면 모두 비움
        setRelatedKeywords([]);
        setKeywordTrends([]);
      }
    } catch (error) {
      console.error('키워드 필터링 에러:', error);
    }
  }, [allTrackedKeywords, selectedBusiness]);

  const handleRefreshAll = async () => {
    setRefreshing(true);
    try {
      await keywordsApi.refreshAll();
      await loadAllTrackedKeywords();
      toast.success('순위 새로고침 완료!');
    } catch (error) {
      toast.error('새로고침 실패');
    } finally {
      setRefreshing(false);
    }
  };

  const handleQuickSearch = () => {
    if (!quickPlaceName.trim() || !quickKeyword.trim()) {
      toast.error('업체명과 키워드를 입력해주세요');
      return;
    }
    const params = new URLSearchParams();
    params.set('placeName', quickPlaceName);
    params.set('keyword', quickKeyword);
    if (quickTraffic) {
      params.set('traffic', quickTraffic);
    }
    router.push(`/inquiry?${params.toString()}`);
  };

  const handleRecentSearchClick = (search: RecentSearch) => {
    router.push(`/inquiry?placeId=${search.placeId}&keyword=${encodeURIComponent(search.keyword)}`);
  };

  const getRankChange = (keyword: SavedKeyword) => {
    if (!keyword.weekly_data || keyword.weekly_data.length < 2) return null;
    const today = keyword.weekly_data[keyword.weekly_data.length - 1];
    const yesterday = keyword.weekly_data[keyword.weekly_data.length - 2];
    if (!today?.rank || !yesterday?.rank) return null;
    return yesterday.rank - today.rank;
  };

  const getRankBadgeStyle = (rank: number | null | undefined): React.CSSProperties => {
    if (!rank) return { background: '#f1f5f9', color: '#64748b' };
    if (rank <= 3) return { background: 'linear-gradient(135deg, #fbbf24, #f59e0b)', color: 'white' };
    if (rank <= 10) return { background: '#dcfce7', color: '#16a34a' };
    if (rank <= 20) return { background: '#dbeafe', color: '#2563eb' };
    return { background: '#f1f5f9', color: '#64748b' };
  };

  // 선택된 업체의 키워드만 필터링
  const trackedKeywords = selectedBusiness
    ? allTrackedKeywords.filter(k => String(k.place_id) === String(selectedBusiness.placeId))
    : allTrackedKeywords;

  // 1위 근접 키워드 (10위 이내) - 선택된 업체 기준
  const nearFirstKeywords = trackedKeywords.filter(k =>
    k.last_rank && k.last_rank > 1 && k.last_rank <= 10
  );

  // 순위 상승 키워드 - 선택된 업체 기준
  const risingKeywords = trackedKeywords.filter(k => {
    const change = getRankChange(k);
    return change !== null && change > 0;
  });

  // 순위 하락 키워드 - 선택된 업체 기준
  const fallingKeywords = trackedKeywords.filter(k => {
    const change = getRankChange(k);
    return change !== null && change < 0;
  });

  return (
    <div>
      {/* Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '32px', flexWrap: 'wrap', gap: '16px' }}>
        <div>
          <h1 style={{ fontSize: '24px', fontWeight: 'bold', color: '#1e293b' }}>대시보드</h1>
          <p style={{ fontSize: '14px', color: '#64748b', marginTop: '4px' }}>내 업체의 플레이스 순위를 한눈에</p>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px', flexWrap: 'wrap' }}>
          {/* 업체 선택 드롭다운 */}
          <div style={{ position: 'relative' }}>
            <button
              onClick={() => setBusinessDropdownOpen(!businessDropdownOpen)}
              style={{
                display: 'flex', alignItems: 'center', gap: '8px',
                padding: '10px 16px', borderRadius: '12px', border: '1px solid #e2e8f0',
                background: 'white', cursor: 'pointer', minWidth: '200px'
              }}
            >
              <Building2 style={{ width: '18px', height: '18px', color: '#6366f1' }} />
              <span style={{ flex: 1, textAlign: 'left', fontWeight: '500', color: '#1e293b' }}>
                {selectedBusiness?.placeName || '전체 업체'}
              </span>
              <ChevronDown style={{ width: '16px', height: '16px', color: '#64748b' }} />
            </button>
            {businessDropdownOpen && (
              <div style={{
                position: 'absolute', top: '100%', left: 0, right: 0, marginTop: '4px',
                background: 'white', borderRadius: '12px', border: '1px solid #e2e8f0',
                boxShadow: '0 4px 12px rgba(0,0,0,0.1)', zIndex: 10, overflow: 'hidden'
              }}>
                <div
                  onClick={() => { setSelectedBusiness(null); setBusinessDropdownOpen(false); }}
                  style={{
                    padding: '12px 16px', cursor: 'pointer',
                    background: !selectedBusiness ? '#eef2ff' : 'white',
                    fontWeight: '500', color: '#6366f1'
                  }}
                >
                  전체 업체 보기
                </div>
                {businesses.map((b) => (
                  <div
                    key={b.placeId}
                    onClick={() => { setSelectedBusiness(b); setBusinessDropdownOpen(false); }}
                    style={{
                      padding: '12px 16px', cursor: 'pointer',
                      background: selectedBusiness?.placeId === b.placeId ? '#eef2ff' : 'white'
                    }}
                  >
                    <div style={{ fontWeight: '500', color: '#1e293b' }}>{b.placeName}</div>
                    <div style={{ fontSize: '12px', color: '#64748b' }}>{b.category}</div>
                  </div>
                ))}
                <div
                  onClick={() => { router.push('/inquiry'); setBusinessDropdownOpen(false); }}
                  style={{
                    padding: '12px 16px', cursor: 'pointer', borderTop: '1px solid #e2e8f0',
                    background: '#f8fafc', color: '#6366f1', fontWeight: '500', textAlign: 'center'
                  }}
                >
                  + 새 업체 조회하기
                </div>
              </div>
            )}
          </div>

          <button
            onClick={handleRefreshAll}
            disabled={refreshing || trackedKeywords.length === 0}
            style={{
              ...styles.btnPrimary,
              padding: '10px 16px',
              opacity: refreshing || trackedKeywords.length === 0 ? 0.6 : 1
            }}
          >
            <RefreshCw style={{ width: '16px', height: '16px', animation: refreshing ? 'spin 1s linear infinite' : 'none' }} />
            {refreshing ? '새로고침 중...' : '순위 새로고침'}
          </button>

          <button style={styles.iconButton}>
            <Bell style={{ width: '20px', height: '20px', color: '#64748b' }} />
          </button>
        </div>
      </div>

      {/* 빠른 조회 */}
      <div style={{ ...styles.card, marginBottom: '24px', background: 'linear-gradient(135deg, #6366f1, #8b5cf6)' }}>
        <div style={{ marginBottom: '16px' }}>
          <h2 style={{ fontSize: '18px', fontWeight: '600', color: 'white', marginBottom: '4px' }}>빠른 순위 조회</h2>
          <p style={{ fontSize: '14px', color: 'rgba(255,255,255,0.8)' }}>업체명, 키워드, 유입수를 입력하고 바로 순위를 확인하세요</p>
        </div>
        {/* 반응형 그리드 - 모바일에서는 세로로 쌓임 */}
        <div className="quick-search-grid" style={{ display: 'grid', gap: '10px', alignItems: 'center' }}>
          <input
            type="text"
            placeholder="업체명 (예: 스타벅스 강남점)"
            value={quickPlaceName}
            onChange={(e) => setQuickPlaceName(e.target.value)}
            style={{ ...styles.inputWhite, gridArea: 'place' }}
          />
          <input
            type="text"
            placeholder="키워드 (예: 강남 카페)"
            value={quickKeyword}
            onChange={(e) => setQuickKeyword(e.target.value)}
            style={{ ...styles.inputWhite, gridArea: 'keyword' }}
          />
          <input
            type="number"
            placeholder="유입수 (선택)"
            value={quickTraffic}
            onChange={(e) => setQuickTraffic(e.target.value)}
            style={{ ...styles.inputWhite, gridArea: 'traffic' }}
          />
          <button
            onClick={handleQuickSearch}
            style={{
              padding: '12px 24px', borderRadius: '12px', border: 'none',
              background: 'white', color: '#6366f1', fontWeight: '600', cursor: 'pointer',
              whiteSpace: 'nowrap', gridArea: 'button',
              display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '6px'
            }}
          >
            <Search style={{ width: '16px', height: '16px' }} />
            조회
          </button>
        </div>
      </div>

      {/* KPI 요약 - 반응형 그리드 */}
      <div className="kpi-grid" style={{ display: 'grid', gap: '20px', marginBottom: '24px' }}>
        <div style={styles.card}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginBottom: '12px' }}>
            <div style={{ width: '40px', height: '40px', borderRadius: '12px', background: '#dbeafe', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
              <Target style={{ width: '20px', height: '20px', color: '#3b82f6' }} />
            </div>
            <span style={{ fontSize: '14px', color: '#64748b' }}>추적 키워드</span>
          </div>
          <span style={{ fontSize: '28px', fontWeight: 'bold', color: '#1e293b' }}>{trackedKeywords.length}</span>
          <span style={{ fontSize: '14px', color: '#64748b', marginLeft: '4px' }}>개</span>
        </div>

        <div style={styles.card}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginBottom: '12px' }}>
            <div style={{ width: '40px', height: '40px', borderRadius: '12px', background: '#dcfce7', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
              <TrendingUp style={{ width: '20px', height: '20px', color: '#22c55e' }} />
            </div>
            <span style={{ fontSize: '14px', color: '#64748b' }}>순위 상승</span>
          </div>
          <span style={{ fontSize: '28px', fontWeight: 'bold', color: '#22c55e' }}>{risingKeywords.length}</span>
          <span style={{ fontSize: '14px', color: '#64748b', marginLeft: '4px' }}>개</span>
        </div>

        <div style={styles.card}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginBottom: '12px' }}>
            <div style={{ width: '40px', height: '40px', borderRadius: '12px', background: '#fee2e2', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
              <TrendingDown style={{ width: '20px', height: '20px', color: '#ef4444' }} />
            </div>
            <span style={{ fontSize: '14px', color: '#64748b' }}>순위 하락</span>
          </div>
          <span style={{ fontSize: '28px', fontWeight: 'bold', color: '#ef4444' }}>{fallingKeywords.length}</span>
          <span style={{ fontSize: '14px', color: '#64748b', marginLeft: '4px' }}>개</span>
        </div>

        <div style={styles.card}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginBottom: '12px' }}>
            <div style={{ width: '40px', height: '40px', borderRadius: '12px', background: '#fef3c7', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
              <Star style={{ width: '20px', height: '20px', color: '#f59e0b' }} />
            </div>
            <span style={{ fontSize: '14px', color: '#64748b' }}>1위 근접</span>
          </div>
          <span style={{ fontSize: '28px', fontWeight: 'bold', color: '#f59e0b' }}>{nearFirstKeywords.length}</span>
          <span style={{ fontSize: '14px', color: '#64748b', marginLeft: '4px' }}>개</span>
        </div>
      </div>

      {/* 메인 콘텐츠 - 반응형 2열/1열 */}
      <div className="main-grid" style={{ display: 'grid', gap: '24px' }}>
        {/* 추적 키워드 현황 */}
        <div style={styles.card}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
            <h2 style={{ fontSize: '18px', fontWeight: '600', color: '#1e293b' }}>
              {selectedBusiness?.placeName || '전체'} 키워드 현황
            </h2>
            <button
              onClick={() => router.push('/tracking')}
              style={{ fontSize: '14px', color: '#6366f1', fontWeight: '500', background: 'none', border: 'none', cursor: 'pointer' }}
            >
              전체보기
            </button>
          </div>

          {loading ? (
            <div style={{ padding: '40px', textAlign: 'center', color: '#64748b' }}>로딩 중...</div>
          ) : trackedKeywords.length > 0 ? (
            <div style={{ overflowX: 'auto' }}>
              <table style={{ width: '100%', borderCollapse: 'collapse', minWidth: '500px' }}>
                <thead>
                  <tr style={{ borderBottom: '1px solid #e2e8f0' }}>
                    <th style={{ textAlign: 'left', padding: '12px 0', fontSize: '12px', fontWeight: '500', color: '#64748b' }}>키워드</th>
                    <th style={{ textAlign: 'center', padding: '12px 0', fontSize: '12px', fontWeight: '500', color: '#64748b' }}>현재 순위</th>
                    <th style={{ textAlign: 'center', padding: '12px 0', fontSize: '12px', fontWeight: '500', color: '#64748b' }}>변동</th>
                    <th style={{ textAlign: 'center', padding: '12px 0', fontSize: '12px', fontWeight: '500', color: '#64748b' }}>월간 검색량</th>
                  </tr>
                </thead>
                <tbody>
                  {trackedKeywords.slice(0, 5).map((kw) => {
                    const change = getRankChange(kw);
                    const trend = keywordTrends.find(t => t.keyword === kw.keyword);
                    return (
                      <tr key={kw.id} style={{ borderBottom: '1px solid #f1f5f9' }}>
                        <td style={{ padding: '12px 0' }}>
                          <div style={{ fontWeight: '500', color: '#1e293b' }}>{kw.keyword}</div>
                          <div style={{ fontSize: '12px', color: '#94a3b8' }}>{kw.place_name}</div>
                        </td>
                        <td style={{ padding: '12px 0', textAlign: 'center' }}>
                          <span style={{ ...getRankBadgeStyle(kw.last_rank), padding: '4px 10px', borderRadius: '12px', fontSize: '12px', fontWeight: '500' }}>
                            {kw.last_rank ? `${kw.last_rank}위` : '-'}
                          </span>
                        </td>
                        <td style={{ padding: '12px 0', textAlign: 'center' }}>
                          {change !== null ? (
                            <span style={{
                              fontWeight: '500',
                              color: change > 0 ? '#22c55e' : change < 0 ? '#ef4444' : '#64748b',
                              display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '2px'
                            }}>
                              {change > 0 ? <TrendingUp style={{ width: '14px', height: '14px' }} /> :
                               change < 0 ? <TrendingDown style={{ width: '14px', height: '14px' }} /> :
                               <Minus style={{ width: '14px', height: '14px' }} />}
                              {change > 0 ? `+${change}` : change < 0 ? change : '-'}
                            </span>
                          ) : '-'}
                        </td>
                        <td style={{ padding: '12px 0', textAlign: 'center', color: '#64748b', fontSize: '13px' }}>
                          {trend?.monthlyVolume ? `${trend.monthlyVolume.toLocaleString()}` : '-'}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          ) : (
            <div style={{ padding: '40px', textAlign: 'center', color: '#64748b' }}>
              <Target style={{ width: '48px', height: '48px', color: '#e2e8f0', margin: '0 auto 12px' }} />
              <p>추적 중인 키워드가 없습니다</p>
              <button
                onClick={() => router.push('/tracking')}
                style={{
                  marginTop: '12px', padding: '8px 16px', borderRadius: '8px',
                  background: '#6366f1', color: 'white', border: 'none', cursor: 'pointer', fontSize: '14px'
                }}
              >
                키워드 추적하기
              </button>
            </div>
          )}
        </div>

        {/* 최근 조회 기록 */}
        <div style={styles.card}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
            <h2 style={{ fontSize: '18px', fontWeight: '600', color: '#1e293b', display: 'flex', alignItems: 'center', gap: '8px' }}>
              <Clock style={{ width: '18px', height: '18px', color: '#64748b' }} />
              최근 조회
            </h2>
          </div>

          {recentSearches.length > 0 ? (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
              {recentSearches.slice(0, 5).map((search, idx) => (
                <div
                  key={idx}
                  onClick={() => handleRecentSearchClick(search)}
                  style={{
                    padding: '12px', borderRadius: '10px', background: '#f8fafc',
                    cursor: 'pointer', display: 'flex', justifyContent: 'space-between', alignItems: 'center'
                  }}
                >
                  <div>
                    <div style={{ fontWeight: '500', color: '#1e293b', fontSize: '14px' }}>{search.keyword}</div>
                    <div style={{ fontSize: '12px', color: '#64748b' }}>{search.placeName}</div>
                  </div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                    <span style={{ ...getRankBadgeStyle(search.rank), padding: '4px 8px', borderRadius: '8px', fontSize: '12px', fontWeight: '500' }}>
                      {search.rank ? `${search.rank}위` : '-'}
                    </span>
                    <ExternalLink style={{ width: '14px', height: '14px', color: '#94a3b8' }} />
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div style={{ padding: '40px', textAlign: 'center', color: '#64748b' }}>
              <Clock style={{ width: '48px', height: '48px', color: '#e2e8f0', margin: '0 auto 12px' }} />
              <p>최근 조회 기록이 없습니다</p>
            </div>
          )}
        </div>
      </div>

      {/* 1위 기회 키워드 - 항상 표시 */}
      <div style={{ ...styles.card, marginTop: '24px' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
          <h2 style={{ fontSize: '18px', fontWeight: '600', color: '#1e293b', display: 'flex', alignItems: 'center', gap: '8px' }}>
            <Zap style={{ width: '18px', height: '18px', color: '#f59e0b' }} />
            1위 기회 키워드
          </h2>
          <span style={{ fontSize: '14px', color: '#64748b' }}>10위 이내 키워드</span>
        </div>

        {nearFirstKeywords.length > 0 ? (
          <div className="opportunity-grid" style={{ display: 'grid', gap: '16px' }}>
            {nearFirstKeywords.slice(0, 6).map((kw) => {
              const trend = keywordTrends.find(t => t.keyword === kw.keyword);
              return (
                <div
                  key={kw.id}
                  onClick={() => router.push(`/inquiry?placeId=${kw.place_id}&keyword=${encodeURIComponent(kw.keyword)}`)}
                  style={{
                    padding: '16px', borderRadius: '12px', background: '#fffbeb',
                    border: '1px solid #fde68a', cursor: 'pointer'
                  }}
                >
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
                    <span style={{ fontWeight: '600', color: '#1e293b' }}>{kw.keyword}</span>
                    <span style={{ ...getRankBadgeStyle(kw.last_rank), padding: '4px 10px', borderRadius: '8px', fontSize: '12px', fontWeight: '600' }}>
                      {kw.last_rank}위
                    </span>
                  </div>
                  <div style={{ fontSize: '12px', color: '#64748b', marginBottom: '4px' }}>{kw.place_name}</div>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <span style={{ fontSize: '13px', color: '#92400e' }}>
                      1위까지 {(kw.last_rank || 1) - 1}단계
                    </span>
                    {trend?.monthlyVolume && (
                      <span style={{ fontSize: '12px', color: '#64748b' }}>
                        {trend.monthlyVolume.toLocaleString()}회/월
                      </span>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        ) : (
          <div style={{ padding: '32px', textAlign: 'center', color: '#64748b', background: '#f8fafc', borderRadius: '12px' }}>
            <Zap style={{ width: '40px', height: '40px', color: '#e2e8f0', margin: '0 auto 12px' }} />
            <p style={{ marginBottom: '8px' }}>아직 1위 기회 키워드가 없습니다</p>
            <p style={{ fontSize: '13px', color: '#94a3b8' }}>순위 조회 후 키워드를 추적하면 10위 이내 키워드가 여기에 표시됩니다</p>
          </div>
        )}
      </div>

      {/* 키워드 검색량 트렌드 - 항상 표시 */}
      <div style={{ ...styles.card, marginTop: '24px' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
          <h2 style={{ fontSize: '18px', fontWeight: '600', color: '#1e293b', display: 'flex', alignItems: 'center', gap: '8px' }}>
            <BarChart3 style={{ width: '18px', height: '18px', color: '#6366f1' }} />
            키워드 검색량 트렌드
          </h2>
          <span style={{ fontSize: '12px', color: '#64748b' }}>월간 검색량 (추정)</span>
        </div>

        {trendLoading ? (
          <div style={{ padding: '32px', textAlign: 'center', color: '#64748b' }}>검색량 로딩 중...</div>
        ) : keywordTrends.length > 0 ? (
          <div className="trend-grid" style={{ display: 'grid', gap: '12px' }}>
            {keywordTrends.map((trend, idx) => (
              <div
                key={idx}
                style={{
                  padding: '16px', borderRadius: '12px',
                  background: trend.trend === 'rising' ? '#f0fdf4' : trend.trend === 'falling' ? '#fef2f2' : '#f8fafc',
                  border: `1px solid ${trend.trend === 'rising' ? '#bbf7d0' : trend.trend === 'falling' ? '#fecaca' : '#e2e8f0'}`
                }}
              >
                <div style={{ fontSize: '13px', fontWeight: '600', color: '#1e293b', marginBottom: '8px', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                  {trend.keyword}
                </div>
                <div style={{ fontSize: '20px', fontWeight: '700', color: '#1e293b', marginBottom: '4px' }}>
                  {(trend.monthlyVolume || 0).toLocaleString()}
                  <span style={{ fontSize: '12px', fontWeight: '400', color: '#64748b', marginLeft: '4px' }}>회/월</span>
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                  {trend.trend === 'rising' ? (
                    <TrendingUp style={{ width: '14px', height: '14px', color: '#22c55e' }} />
                  ) : trend.trend === 'falling' ? (
                    <TrendingDown style={{ width: '14px', height: '14px', color: '#ef4444' }} />
                  ) : (
                    <Minus style={{ width: '14px', height: '14px', color: '#64748b' }} />
                  )}
                  <span style={{
                    fontSize: '12px', fontWeight: '500',
                    color: trend.trend === 'rising' ? '#22c55e' : trend.trend === 'falling' ? '#ef4444' : '#64748b'
                  }}>
                    {trend.trend === 'rising' ? '상승' : trend.trend === 'falling' ? '하락' : '유지'}
                  </span>
                </div>
              </div>
            ))}
          </div>
        ) : (
          <div style={{ padding: '32px', textAlign: 'center', color: '#64748b', background: '#f8fafc', borderRadius: '12px' }}>
            <BarChart3 style={{ width: '40px', height: '40px', color: '#e2e8f0', margin: '0 auto 12px' }} />
            <p style={{ marginBottom: '8px' }}>검색량 트렌드 데이터가 없습니다</p>
            <p style={{ fontSize: '13px', color: '#94a3b8' }}>키워드를 추적하면 네이버 검색량 트렌드가 표시됩니다</p>
          </div>
        )}
      </div>

      {/* 관련 키워드 추천 - 조회수만 표시 */}
      <div style={{ ...styles.card, marginTop: '24px' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
          <h2 style={{ fontSize: '18px', fontWeight: '600', color: '#1e293b', display: 'flex', alignItems: 'center', gap: '8px' }}>
            <Sparkles style={{ width: '18px', height: '18px', color: '#8b5cf6' }} />
            추천 관련 키워드
          </h2>
          <span style={{ fontSize: '12px', color: '#64748b' }}>월간 검색량</span>
        </div>

        {relatedLoading ? (
          <div style={{ padding: '32px', textAlign: 'center', color: '#64748b' }}>관련 키워드 분석 중...</div>
        ) : relatedKeywords.length > 0 ? (
          <div className="related-grid" style={{ display: 'grid', gap: '12px' }}>
            {relatedKeywords.map((rk, idx) => (
              <div
                key={idx}
                onClick={() => {
                  setQuickKeyword(rk.keyword);
                  window.scrollTo({ top: 0, behavior: 'smooth' });
                }}
                style={{
                  padding: '16px', borderRadius: '12px', cursor: 'pointer',
                  background: '#f8fafc',
                  border: '1px solid #e2e8f0',
                  transition: 'transform 0.2s, box-shadow 0.2s'
                }}
                onMouseOver={(e) => {
                  e.currentTarget.style.transform = 'translateY(-2px)';
                  e.currentTarget.style.boxShadow = '0 4px 12px rgba(0, 0, 0, 0.1)';
                }}
                onMouseOut={(e) => {
                  e.currentTarget.style.transform = 'translateY(0)';
                  e.currentTarget.style.boxShadow = 'none';
                }}
              >
                <div style={{ fontWeight: '600', color: '#1e293b', marginBottom: '8px' }}>{rk.keyword}</div>
                <div style={{ display: 'flex', alignItems: 'baseline', gap: '4px' }}>
                  <span style={{ fontSize: '20px', fontWeight: '700', color: '#6366f1' }}>
                    {rk.searchVolume.toLocaleString()}
                  </span>
                  <span style={{ fontSize: '12px', color: '#64748b' }}>회/월</span>
                </div>
              </div>
            ))}
          </div>
        ) : (
          <div style={{ padding: '32px', textAlign: 'center', color: '#64748b', background: '#f8fafc', borderRadius: '12px' }}>
            <Sparkles style={{ width: '40px', height: '40px', color: '#e2e8f0', margin: '0 auto 12px' }} />
            <p style={{ marginBottom: '8px' }}>추천 키워드가 없습니다</p>
            <p style={{ fontSize: '13px', color: '#94a3b8' }}>키워드를 추적하면 업종에 맞는 관련 키워드를 추천해드립니다</p>
          </div>
        )}
      </div>

      {/* 로그인 안내 */}
      {!authLoading && !user && (
        <div style={{ ...styles.card, marginTop: '24px', textAlign: 'center', padding: '48px' }}>
          <Sparkles style={{ width: '48px', height: '48px', color: '#6366f1', margin: '0 auto 16px' }} />
          <h3 style={{ fontSize: '18px', fontWeight: '600', color: '#1e293b', marginBottom: '8px' }}>
            로그인하고 모든 기능을 사용하세요
          </h3>
          <p style={{ fontSize: '14px', color: '#64748b', marginBottom: '16px' }}>
            키워드 추적, 순위 분석, 검색량 트렌드 등 다양한 기능을 이용할 수 있습니다
          </p>
          <button
            onClick={() => router.push('/login')}
            style={styles.btnPrimary}
          >
            로그인하기
          </button>
        </div>
      )}

      {/* 반응형 스타일 + 애니메이션 */}
      <style>{`
        @keyframes spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }

        /* 빠른 조회 그리드 */
        .quick-search-grid {
          grid-template-columns: 2fr 2fr 1fr auto;
          grid-template-areas: "place keyword traffic button";
        }

        /* KPI 그리드 */
        .kpi-grid {
          grid-template-columns: repeat(4, 1fr);
        }

        /* 메인 그리드 */
        .main-grid {
          grid-template-columns: 2fr 1fr;
        }

        /* 기회 키워드 그리드 */
        .opportunity-grid {
          grid-template-columns: repeat(3, 1fr);
        }

        /* 트렌드 그리드 */
        .trend-grid {
          grid-template-columns: repeat(5, 1fr);
        }

        /* 관련 키워드 그리드 */
        .related-grid {
          grid-template-columns: repeat(4, 1fr);
        }

        /* 태블릿 (1024px 이하) */
        @media (max-width: 1024px) {
          .quick-search-grid {
            grid-template-columns: 1fr 1fr;
            grid-template-areas:
              "place keyword"
              "traffic button";
          }

          .kpi-grid {
            grid-template-columns: repeat(2, 1fr);
          }

          .main-grid {
            grid-template-columns: 1fr;
          }

          .opportunity-grid {
            grid-template-columns: repeat(2, 1fr);
          }

          .trend-grid {
            grid-template-columns: repeat(3, 1fr);
          }

          .related-grid {
            grid-template-columns: repeat(2, 1fr);
          }
        }

        /* 모바일 (640px 이하) */
        @media (max-width: 640px) {
          .quick-search-grid {
            grid-template-columns: 1fr;
            grid-template-areas:
              "place"
              "keyword"
              "traffic"
              "button";
          }

          .kpi-grid {
            grid-template-columns: repeat(2, 1fr);
          }

          .opportunity-grid {
            grid-template-columns: 1fr;
          }

          .trend-grid {
            grid-template-columns: repeat(2, 1fr);
          }

          .related-grid {
            grid-template-columns: 1fr;
          }
        }
      `}</style>
    </div>
  );
}
