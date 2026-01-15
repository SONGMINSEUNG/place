"use client";

import { useState, useEffect, useRef, Suspense } from "react";
import { useSearchParams } from "next/navigation";
import { Search, Loader2, ChevronRight, CheckCircle, TrendingUp, Target, Eye, Star, Trophy, BarChart3, Activity, Zap, Play, Sliders, PenLine, AlertTriangle, Save, MousePointerClick } from "lucide-react";
import { toast } from "sonner";
import { placeApi, analyzeApi, AnalyzeResponse, SimulateResponse, SimulateInputs, TargetRankResponse, userDataApi, CorrelationResponse, activityApi, ActivityLogRequest } from "@/lib/api";

interface SearchResult {
  place_id: string;
  name: string;
  category: string;
}

// 공통 스타일 정의 (page.tsx와 동일하게 통일)
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
  } as React.CSSProperties
};

export default function InquiryPage() {
  return (
    <Suspense fallback={<div style={{ padding: '40px', textAlign: 'center' }}>로딩 중...</div>}>
      <InquiryPageContent />
    </Suspense>
  );
}

function InquiryPageContent() {
  const searchParams = useSearchParams();
  const initialLoadDone = useRef(false);

  const [placeName, setPlaceName] = useState("");
  const [keywords, setKeywords] = useState("");
  const [trafficCount, setTrafficCount] = useState<string>("");
  const [loading, setLoading] = useState(false);
  const [searching, setSearching] = useState(false);
  const [analyzeResult, setAnalyzeResult] = useState<AnalyzeResponse | null>(null);
  const [searchResults, setSearchResults] = useState<SearchResult[]>([]);
  const [selectedPlace, setSelectedPlace] = useState<SearchResult | null>(null);
  const [userTrafficCount, setUserTrafficCount] = useState<number | null>(null);

  // 목표 순위 시뮬레이션 관련 상태
  const [targetRank, setTargetRank] = useState<number>(1);
  const [targetSimLoading, setTargetSimLoading] = useState(false);
  const [targetSimResult, setTargetSimResult] = useState<TargetRankResponse | null>(null);

  // 기존 시뮬레이션 관련 상태 (숨김 처리)
  const [simBlogReview, setSimBlogReview] = useState<number>(0);
  const [simVisitReview, setSimVisitReview] = useState<number>(0);
  const [simInflow, setSimInflow] = useState<number>(0);
  const [simLoading, setSimLoading] = useState(false);
  const [simResult, setSimResult] = useState<SimulateResponse | null>(null);

  // 활동 기입 관련 상태
  const [activityBlogChecked, setActivityBlogChecked] = useState(false);
  const [activityBlogCount, setActivityBlogCount] = useState<number>(0);
  const [activitySaveChecked, setActivitySaveChecked] = useState(false);
  const [activitySaveCount, setActivitySaveCount] = useState<number>(0);
  const [activityInflowChecked, setActivityInflowChecked] = useState(false);
  const [activityInflowCount, setActivityInflowCount] = useState<number>(0);
  const [activityLogging, setActivityLogging] = useState(false);
  const [activityLogged, setActivityLogged] = useState(false);

  // URL 파라미터에서 초기값 설정 및 자동 검색
  // 의존성 배열을 빈 배열로 변경하여 무한 렌더링 방지
  // searchParams 객체 참조가 매 렌더링마다 변경되어 무한 루프 유발
  useEffect(() => {
    if (initialLoadDone.current) return;

    const urlPlaceName = searchParams.get('placeName');
    const urlKeyword = searchParams.get('keyword');
    const urlTraffic = searchParams.get('traffic');

    if (urlPlaceName) {
      setPlaceName(urlPlaceName);
      // 자동으로 업체 검색 시작
      autoSearchPlace(urlPlaceName, urlKeyword || '', urlTraffic || '');
    }
    if (urlKeyword) {
      setKeywords(urlKeyword);
    }
    if (urlTraffic) {
      setTrafficCount(urlTraffic);
    }

    initialLoadDone.current = true;
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // 자동 업체 검색 함수
  const autoSearchPlace = async (name: string, keyword: string, traffic: string) => {
    setSearching(true);
    try {
      const response = await placeApi.search(name, 20);
      if (response.places && response.places.length > 0) {
        setSearchResults(response.places);
        // 첫 번째 결과 자동 선택하고 바로 순위 조회
        const firstPlace = response.places[0];
        setSelectedPlace(firstPlace);
        setSearchResults([]);

        if (keyword) {
          // 바로 순위 조회 실행
          setTimeout(() => {
            autoRankSearch(firstPlace, keyword, traffic);
          }, 100);
        }
      } else {
        toast.info("업체를 검색 결과에서 선택해주세요");
      }
    } catch (error) {
      console.error('자동 검색 실패:', error);
    } finally {
      setSearching(false);
    }
  };

  // 자동 순위 조회 함수 (ADLOG API 사용)
  const autoRankSearch = async (place: SearchResult, keyword: string, traffic: string) => {
    setLoading(true);
    try {
      const trafficNum = traffic ? parseInt(traffic, 10) : undefined;

      setUserTrafficCount(trafficNum || null);

      // ADLOG API 호출 (정규화된 점수 반환)
      const analyzeData = await analyzeApi.analyze(
        keyword,
        place.name,
        trafficNum
      );
      setAnalyzeResult(analyzeData);

      // localStorage에 최근 조회 기록 저장
      const recentSearch = {
        placeId: place.place_id,
        placeName: place.name,
        category: place.category,
        keyword: keyword,
        rank: analyzeData.my_place?.rank || null,
        searchedAt: new Date().toISOString(),
      };
      const savedSearches = JSON.parse(localStorage.getItem('recentSearches') || '[]');
      const updatedSearches = [recentSearch, ...savedSearches.filter((s: any) =>
        !(s.placeId === recentSearch.placeId && s.keyword === recentSearch.keyword)
      )].slice(0, 10);
      localStorage.setItem('recentSearches', JSON.stringify(updatedSearches));

      // localStorage에 업체 등록
      const business = {
        placeId: place.place_id,
        placeName: place.name,
        category: place.category,
      };
      const savedBusinesses = JSON.parse(localStorage.getItem('registeredBusinesses') || '[]');
      if (!savedBusinesses.find((b: any) => b.placeId === business.placeId)) {
        const updatedBusinesses = [business, ...savedBusinesses].slice(0, 10);
        localStorage.setItem('registeredBusinesses', JSON.stringify(updatedBusinesses));
      }

      toast.success("분석 완료!");
    } catch (error: any) {
      toast.error(error.response?.data?.detail || "분석 중 오류가 발생했습니다");
    } finally {
      setLoading(false);
    }
  };

  const handlePlaceSearch = async () => {
    if (!placeName.trim()) {
      toast.error("업체명을 입력해주세요");
      return;
    }
    setSearching(true);
    try {
      const response = await placeApi.search(placeName, 20);
      setSearchResults(response.places || []);
      if (response.places?.length === 0) {
        toast.error("검색 결과가 없습니다");
      }
    } catch (error: any) {
      toast.error("검색 중 오류가 발생했습니다");
    } finally {
      setSearching(false);
    }
  };

  const handleSelectPlace = (place: SearchResult) => {
    setSelectedPlace(place);
    setSearchResults([]);
  };

  // 순위 조회 함수 (ADLOG API 사용)
  const handleRankSearch = async () => {
    if (!selectedPlace || !keywords.trim()) {
      toast.error("업체와 키워드를 입력해주세요");
      return;
    }
    setLoading(true);
    try {
      const trafficNum = trafficCount ? parseInt(trafficCount, 10) : undefined;

      setUserTrafficCount(trafficNum || null);

      // ADLOG API 호출 (정규화된 점수 반환)
      const analyzeData = await analyzeApi.analyze(
        keywords.trim(),
        selectedPlace.name,
        trafficNum
      );
      setAnalyzeResult(analyzeData);

      // localStorage에 최근 조회 기록 저장
      const recentSearch = {
        placeId: selectedPlace.place_id,
        placeName: selectedPlace.name,
        category: selectedPlace.category,
        keyword: keywords.trim(),
        rank: analyzeData.my_place?.rank || null,
        searchedAt: new Date().toISOString(),
      };
      const savedSearches = JSON.parse(localStorage.getItem('recentSearches') || '[]');
      const updatedSearches = [recentSearch, ...savedSearches.filter((s: any) =>
        !(s.placeId === recentSearch.placeId && s.keyword === recentSearch.keyword)
      )].slice(0, 10);
      localStorage.setItem('recentSearches', JSON.stringify(updatedSearches));

      // localStorage에 업체 등록
      const business = {
        placeId: selectedPlace.place_id,
        placeName: selectedPlace.name,
        category: selectedPlace.category,
      };
      const savedBusinesses = JSON.parse(localStorage.getItem('registeredBusinesses') || '[]');
      if (!savedBusinesses.find((b: any) => b.placeId === business.placeId)) {
        const updatedBusinesses = [business, ...savedBusinesses].slice(0, 10);
        localStorage.setItem('registeredBusinesses', JSON.stringify(updatedBusinesses));
      }

      toast.success("분석 완료!");
    } catch (error: any) {
      toast.error(error.response?.data?.detail || "분석 중 오류가 발생했습니다");
    } finally {
      setLoading(false);
    }
  };

  const handleReset = () => {
    setSelectedPlace(null);
    setSearchResults([]);
    setAnalyzeResult(null);
    setPlaceName("");
    setKeywords("");
    setTrafficCount("");
    setUserTrafficCount(null);
    // 목표 순위 시뮬레이션 상태 초기화
    setTargetRank(1);
    setTargetSimResult(null);
    // 기존 시뮬레이션 상태 초기화
    setSimBlogReview(0);
    setSimVisitReview(0);
    setSimInflow(0);
    setSimResult(null);
    // 활동 기입 상태 초기화
    setActivityBlogChecked(false);
    setActivityBlogCount(0);
    setActivitySaveChecked(false);
    setActivitySaveCount(0);
    setActivityInflowChecked(false);
    setActivityInflowCount(0);
    setActivityLogged(false);
  };

  // 시뮬레이션 실행
  const handleSimulate = async () => {
    if (!selectedPlace || !analyzeResult?.keyword) {
      toast.error("분석 결과가 없습니다");
      return;
    }

    if (simBlogReview === 0 && simVisitReview === 0 && simInflow === 0) {
      toast.error("시뮬레이션할 값을 입력해주세요");
      return;
    }

    setSimLoading(true);
    try {
      const inputs: SimulateInputs = {
        blog_review: simBlogReview,
        visit_review: simVisitReview,
        inflow: simInflow,
      };

      const result = await analyzeApi.simulate(
        analyzeResult.keyword,
        selectedPlace.name,
        inputs
      );
      setSimResult(result);
      toast.success("시뮬레이션 완료!");
    } catch (error: any) {
      toast.error(error.response?.data?.detail || "시뮬레이션 중 오류가 발생했습니다");
    } finally {
      setSimLoading(false);
    }
  };

  // 시뮬레이션 초기화
  const handleSimReset = () => {
    setSimBlogReview(0);
    setSimVisitReview(0);
    setSimInflow(0);
    setSimResult(null);
  };

  // 목표 순위 시뮬레이션 실행
  const handleTargetRankSimulate = async () => {
    if (!selectedPlace || !analyzeResult?.keyword || !analyzeResult?.my_place) {
      toast.error("분석 결과가 없습니다");
      return;
    }

    const currentRank = analyzeResult.my_place.rank;

    if (targetRank >= currentRank) {
      toast.error("목표 순위는 현재 순위보다 높아야 합니다");
      return;
    }

    setTargetSimLoading(true);
    try {
      const result = await analyzeApi.simulateTargetRank(
        analyzeResult.keyword,
        selectedPlace.name,
        currentRank,
        targetRank
      );
      setTargetSimResult(result);
      toast.success("목표 순위 시뮬레이션 완료!");
    } catch (error: any) {
      toast.error(error.response?.data?.detail || "시뮬레이션 중 오류가 발생했습니다");
    } finally {
      setTargetSimLoading(false);
    }
  };

  // 목표 순위 시뮬레이션 초기화
  const handleTargetSimReset = () => {
    setTargetRank(1);
    setTargetSimResult(null);
  };

  // 활동 기록 제출
  const handleActivityLog = async () => {
    if (!selectedPlace || !analyzeResult?.keyword) {
      toast.error("분석 결과가 없습니다");
      return;
    }

    const hasActivity = (activityBlogChecked && activityBlogCount > 0) ||
                       (activitySaveChecked && activitySaveCount > 0) ||
                       (activityInflowChecked && activityInflowCount > 0);

    if (!hasActivity) {
      toast.error("최소 1개 이상의 활동을 입력해주세요");
      return;
    }

    setActivityLogging(true);
    try {
      const request: ActivityLogRequest = {
        keyword: analyzeResult.keyword,
        place_id: selectedPlace.place_id,
        place_name: selectedPlace.name,
        blog_review_added: activityBlogChecked ? activityBlogCount : 0,
        visit_review_added: 0,  // 현재 UI에서는 미사용
        save_added: activitySaveChecked ? activitySaveCount : 0,
        inflow_added: activityInflowChecked ? activityInflowCount : 0,
      };

      await activityApi.log(request);
      setActivityLogged(true);
      toast.success("활동이 기록되었습니다! D+1, D+7 후 결과가 자동으로 측정됩니다.");

      // 입력값 초기화
      setActivityBlogChecked(false);
      setActivityBlogCount(0);
      setActivitySaveChecked(false);
      setActivitySaveCount(0);
      setActivityInflowChecked(false);
      setActivityInflowCount(0);
    } catch (error: any) {
      toast.error(error.response?.data?.detail || "활동 기록 중 오류가 발생했습니다");
    } finally {
      setActivityLogging(false);
    }
  };

  const getRankBadgeStyle = (rank: number | null | undefined): React.CSSProperties => {
    if (!rank) return { background: '#f1f5f9', color: '#64748b' };
    if (rank <= 3) return { background: 'linear-gradient(135deg, #fbbf24, #f59e0b)', color: 'white' };
    if (rank <= 10) return { background: '#dcfce7', color: '#16a34a' };
    if (rank <= 20) return { background: '#dbeafe', color: '#2563eb' };
    return { background: '#f1f5f9', color: '#64748b' };
  };

  // 검색 전 화면
  if (!selectedPlace || !analyzeResult) {
    return (
      <div>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '32px', flexWrap: 'wrap', gap: '16px' }}>
          <h1 style={{ fontSize: '24px', fontWeight: 'bold', color: '#1e293b' }}>순위 조회</h1>
          <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
            <div style={{ position: 'relative' }}>
              <Search style={{ position: 'absolute', left: '16px', top: '50%', transform: 'translateY(-50%)', width: '16px', height: '16px', color: '#94a3b8' }} />
              <input type="text" placeholder="검색..." style={{ ...styles.input, paddingLeft: '44px', width: '240px' }} />
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '12px', paddingLeft: '16px', borderLeft: '1px solid #e2e8f0' }}>
              <div style={{ width: '40px', height: '40px', borderRadius: '50%', background: 'linear-gradient(135deg, #f472b6, #a855f7)' }} />
              <div>
                <p style={{ fontSize: '14px', fontWeight: '600', color: '#1e293b' }}>사용자</p>
                <p style={{ fontSize: '12px', color: '#64748b' }}>Pro 플랜</p>
              </div>
            </div>
          </div>
        </div>

        <div style={{ width: '100%' }}>
          <div style={{ ...styles.card, padding: '32px' }}>
            {!selectedPlace ? (
              <>
                <div style={{ display: 'flex', alignItems: 'center', gap: '16px', marginBottom: '24px' }}>
                  <div style={{ width: '48px', height: '48px', borderRadius: '16px', background: 'linear-gradient(135deg, #6366f1, #8b5cf6)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                    <Search style={{ width: '24px', height: '24px', color: 'white' }} />
                  </div>
                  <div>
                    <h2 style={{ fontSize: '18px', fontWeight: '600', color: '#1e293b' }}>업체 검색</h2>
                    <p style={{ fontSize: '14px', color: '#64748b' }}>분석할 업체를 검색해서 선택하세요</p>
                  </div>
                </div>

                <div style={{ display: 'flex', gap: '12px', marginBottom: '16px', flexWrap: 'wrap' }}>
                  <input
                    type="text"
                    placeholder="업체명을 입력하세요"
                    value={placeName}
                    onChange={(e) => setPlaceName(e.target.value)}
                    onKeyDown={(e) => e.key === "Enter" && handlePlaceSearch()}
                    style={{ ...styles.input, flex: '1', minWidth: '200px' }}
                  />
                  <button onClick={handlePlaceSearch} disabled={searching} style={{ ...styles.btnPrimary, opacity: searching ? 0.6 : 1 }}>
                    {searching ? <Loader2 style={{ width: '16px', height: '16px', animation: 'spin 1s linear infinite' }} /> : <Search style={{ width: '16px', height: '16px' }} />}
                    검색
                  </button>
                </div>

                {searchResults.length > 0 && (
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', maxHeight: '300px', overflowY: 'auto' }}>
                    {searchResults.map((place) => (
                      <div
                        key={place.place_id}
                        onClick={() => handleSelectPlace(place)}
                        style={{ padding: '16px', borderRadius: '12px', border: '1px solid #e2e8f0', cursor: 'pointer', display: 'flex', justifyContent: 'space-between', alignItems: 'center', transition: 'background 0.2s' }}
                        onMouseOver={(e) => e.currentTarget.style.background = '#f8fafc'}
                        onMouseOut={(e) => e.currentTarget.style.background = 'white'}
                      >
                        <div>
                          <p style={{ fontWeight: '600', color: '#1e293b' }}>{place.name}</p>
                          <p style={{ fontSize: '14px', color: '#64748b' }}>{place.category}</p>
                        </div>
                        <ChevronRight style={{ width: '20px', height: '20px', color: '#94a3b8' }} />
                      </div>
                    ))}
                  </div>
                )}
              </>
            ) : (
              <>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '16px', borderRadius: '12px', background: '#eef2ff', border: '1px solid #c7d2fe', marginBottom: '24px' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                    <CheckCircle style={{ width: '20px', height: '20px', color: '#6366f1' }} />
                    <div>
                      <p style={{ fontWeight: '600', color: '#1e293b' }}>{selectedPlace.name}</p>
                      <p style={{ fontSize: '14px', color: '#64748b' }}>{selectedPlace.category}</p>
                    </div>
                  </div>
                  <button onClick={handleReset} style={{ fontSize: '14px', color: '#6366f1', fontWeight: '500', background: 'none', border: 'none', cursor: 'pointer' }}>변경</button>
                </div>

                <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
                  <div>
                    <label style={{ fontSize: '14px', fontWeight: '500', color: '#374151', display: 'block', marginBottom: '8px' }}>검색 키워드</label>
                    <input
                      type="text"
                      placeholder="강남 맛집, 강남역 카페"
                      value={keywords}
                      onChange={(e) => setKeywords(e.target.value)}
                      style={styles.input}
                    />
                    <p style={{ fontSize: '12px', color: '#94a3b8', marginTop: '4px' }}>쉼표로 구분하여 여러 키워드 입력</p>
                  </div>

                  {/* 오늘 어떤 작업을 하셨나요? - 활동 기입 섹션 (조회 전) */}
                  <div style={{ padding: '20px', background: 'linear-gradient(135deg, #faf5ff, #f3e8ff)', borderRadius: '12px', border: '1px solid #e9d5ff' }}>
                    <h4 style={{ fontSize: '16px', fontWeight: '600', color: '#7c3aed', marginBottom: '12px', display: 'flex', alignItems: 'center', gap: '8px' }}>
                      <PenLine style={{ width: '18px', height: '18px', color: '#7c3aed' }} />
                      오늘 어떤 작업을 하셨나요?
                    </h4>

                    {/* 경고 배너 */}
                    <div style={{
                      padding: '10px 14px',
                      background: '#fef3c7',
                      borderRadius: '8px',
                      border: '1px solid #fcd34d',
                      marginBottom: '12px',
                      display: 'flex',
                      alignItems: 'center',
                      gap: '8px',
                    }}>
                      <AlertTriangle style={{ width: '16px', height: '16px', color: '#d97706', flexShrink: 0 }} />
                      <span style={{ fontSize: '12px', color: '#92400e' }}>
                        모르거나 안했으면 체크하지 마세요.
                      </span>
                    </div>

                    {/* 활동 체크박스 */}
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                      {/* 블로그 리뷰 */}
                      <div style={{
                        padding: '12px',
                        background: activityBlogChecked ? '#ede9fe' : 'white',
                        borderRadius: '8px',
                        border: activityBlogChecked ? '2px solid #8b5cf6' : '1px solid #e5e7eb',
                      }}>
                        <label style={{ display: 'flex', alignItems: 'center', gap: '10px', cursor: 'pointer' }}>
                          <input
                            type="checkbox"
                            checked={activityBlogChecked}
                            onChange={(e) => {
                              setActivityBlogChecked(e.target.checked);
                              if (!e.target.checked) setActivityBlogCount(0);
                            }}
                            style={{ width: '18px', height: '18px', accentColor: '#7c3aed' }}
                          />
                          <span style={{ flex: 1, fontSize: '14px', fontWeight: '500', color: '#1e293b' }}>블로그 리뷰</span>
                          {activityBlogChecked && (
                            <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                              <input
                                type="number"
                                min="0"
                                value={activityBlogCount || ''}
                                onChange={(e) => setActivityBlogCount(parseInt(e.target.value) || 0)}
                                style={{ width: '60px', padding: '6px 10px', borderRadius: '6px', border: '1px solid #d1d5db', fontSize: '13px', textAlign: 'center' }}
                              />
                              <span style={{ fontSize: '13px', color: '#6b7280' }}>개</span>
                            </div>
                          )}
                        </label>
                      </div>

                      {/* 저장수 */}
                      <div style={{
                        padding: '12px',
                        background: activitySaveChecked ? '#ede9fe' : 'white',
                        borderRadius: '8px',
                        border: activitySaveChecked ? '2px solid #8b5cf6' : '1px solid #e5e7eb',
                      }}>
                        <label style={{ display: 'flex', alignItems: 'center', gap: '10px', cursor: 'pointer' }}>
                          <input
                            type="checkbox"
                            checked={activitySaveChecked}
                            onChange={(e) => {
                              setActivitySaveChecked(e.target.checked);
                              if (!e.target.checked) setActivitySaveCount(0);
                            }}
                            style={{ width: '18px', height: '18px', accentColor: '#7c3aed' }}
                          />
                          <span style={{ flex: 1, fontSize: '14px', fontWeight: '500', color: '#1e293b' }}>저장수</span>
                          {activitySaveChecked && (
                            <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                              <input
                                type="number"
                                min="0"
                                value={activitySaveCount || ''}
                                onChange={(e) => setActivitySaveCount(parseInt(e.target.value) || 0)}
                                style={{ width: '60px', padding: '6px 10px', borderRadius: '6px', border: '1px solid #d1d5db', fontSize: '13px', textAlign: 'center' }}
                              />
                              <span style={{ fontSize: '13px', color: '#6b7280' }}>개</span>
                            </div>
                          )}
                        </label>
                      </div>

                      {/* 유입수 */}
                      <div style={{
                        padding: '12px',
                        background: activityInflowChecked ? '#ede9fe' : 'white',
                        borderRadius: '8px',
                        border: activityInflowChecked ? '2px solid #8b5cf6' : '1px solid #e5e7eb',
                      }}>
                        <label style={{ display: 'flex', alignItems: 'center', gap: '10px', cursor: 'pointer' }}>
                          <input
                            type="checkbox"
                            checked={activityInflowChecked}
                            onChange={(e) => {
                              setActivityInflowChecked(e.target.checked);
                              if (!e.target.checked) setActivityInflowCount(0);
                            }}
                            style={{ width: '18px', height: '18px', accentColor: '#7c3aed' }}
                          />
                          <span style={{ flex: 1, fontSize: '14px', fontWeight: '500', color: '#1e293b' }}>유입수</span>
                          {activityInflowChecked && (
                            <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                              <input
                                type="number"
                                min="0"
                                value={activityInflowCount || ''}
                                onChange={(e) => setActivityInflowCount(parseInt(e.target.value) || 0)}
                                style={{ width: '60px', padding: '6px 10px', borderRadius: '6px', border: '1px solid #d1d5db', fontSize: '13px', textAlign: 'center' }}
                              />
                              <span style={{ fontSize: '13px', color: '#6b7280' }}>회</span>
                            </div>
                          )}
                        </label>
                      </div>
                    </div>
                  </div>

                  <button onClick={handleRankSearch} disabled={loading} style={{ ...styles.btnPrimary, width: '100%', justifyContent: 'center', opacity: loading ? 0.6 : 1 }}>
                    {loading ? <Loader2 style={{ width: '20px', height: '20px', animation: 'spin 1s linear infinite' }} /> : <Search style={{ width: '20px', height: '20px' }} />}
                    {loading ? "분석 중..." : "순위 분석하기"}
                  </button>

                  {loading && <p style={{ textAlign: 'center', fontSize: '14px', color: '#64748b' }}>ADLOG API 분석 중...</p>}
                </div>
              </>
            )}
          </div>
        </div>

        {/* 반응형 스타일 + 애니메이션 */}
        <style>{`
          @keyframes spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }

          .input-grid {
            grid-template-columns: 1fr 1fr;
          }

          @media (max-width: 640px) {
            .input-grid {
              grid-template-columns: 1fr;
            }
          }
        `}</style>
      </div>
    );
  }

  // 결과 화면 (ADLOG 정규화 점수 기반)
  const myPlace = analyzeResult.my_place;
  const comparison = analyzeResult.comparison;
  const competitors = analyzeResult.competitors || [];
  const recommendations = analyzeResult.recommendations || [];
  const allPlaces = analyzeResult.all_places || [];

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '32px', flexWrap: 'wrap', gap: '16px' }}>
        <div>
          <h1 style={{ fontSize: '24px', fontWeight: 'bold', color: '#1e293b' }}>분석 결과</h1>
          <p style={{ color: '#64748b', marginTop: '4px' }}>{analyzeResult.keyword} - {selectedPlace.name}</p>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          <button onClick={handleReset} style={styles.btnSecondary}>다른 업체 조회</button>
        </div>
      </div>

      {/* 내 업체 정보 - 반응형 그리드 */}
      {myPlace && (
        <div className="result-kpi-grid" style={{ display: 'grid', gap: '20px', marginBottom: '28px' }}>
          <div style={styles.card}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginBottom: '12px' }}>
              <div style={{ width: '40px', height: '40px', borderRadius: '12px', background: 'linear-gradient(135deg, #6366f1, #8b5cf6)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                <Trophy style={{ width: '20px', height: '20px', color: 'white' }} />
              </div>
              <span style={{ fontSize: '14px', color: '#64748b' }}>현재 순위</span>
            </div>
            <span style={{ fontSize: '32px', fontWeight: 'bold', color: '#1e293b' }}>{myPlace.rank}위</span>
          </div>

          <div style={styles.card}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginBottom: '12px' }}>
              <div style={{ width: '40px', height: '40px', borderRadius: '12px', background: '#dbeafe', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                <Target style={{ width: '20px', height: '20px', color: '#3b82f6' }} />
              </div>
              <span style={{ fontSize: '14px', color: '#64748b' }}>품질점수 (N2 정규화)</span>
            </div>
            <span style={{ fontSize: '28px', fontWeight: 'bold', color: '#3b82f6' }}>{myPlace.scores.quality_score.toFixed(2)}</span>
            <span style={{ fontSize: '12px', color: '#94a3b8', marginLeft: '4px' }}>/ 100</span>
          </div>

          <div style={styles.card}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginBottom: '12px' }}>
              <div style={{ width: '40px', height: '40px', borderRadius: '12px', background: '#dcfce7', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                <Eye style={{ width: '20px', height: '20px', color: '#22c55e' }} />
              </div>
              <span style={{ fontSize: '14px', color: '#64748b' }}>유입수 (입력값)</span>
            </div>
            <span style={{ fontSize: '28px', fontWeight: 'bold', color: '#1e293b' }}>{userTrafficCount?.toLocaleString() || '-'}</span>
          </div>

          <div style={styles.card}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginBottom: '12px' }}>
              <div style={{ width: '40px', height: '40px', borderRadius: '12px', background: '#fef3c7', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                <Zap style={{ width: '20px', height: '20px', color: '#f59e0b' }} />
              </div>
              <span style={{ fontSize: '14px', color: '#64748b' }}>경쟁력 (N3)</span>
            </div>
            <span style={{ fontSize: '28px', fontWeight: 'bold', color: '#f59e0b' }}>{myPlace.scores.competition_score.toFixed(1)}</span>
          </div>
        </div>
      )}

      {/* ADLOG 3가지 지표 (N1, N2, N3 정규화 점수) */}
      {myPlace && (
        <div style={{ ...styles.card, marginBottom: '24px' }}>
          <h3 style={{ fontSize: '16px', fontWeight: '600', color: '#1e293b', marginBottom: '16px', display: 'flex', alignItems: 'center', gap: '8px' }}>
            <BarChart3 style={{ width: '18px', height: '18px', color: '#6366f1' }} />
            ADLOG 분석 지표 (0-100 정규화)
          </h3>
          <div className="adlog-scores-grid" style={{ display: 'grid', gap: '16px' }}>
            <div style={{ padding: '16px', background: '#f0f9ff', borderRadius: '12px', border: '1px solid #bae6fd' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '8px' }}>
                <Activity style={{ width: '16px', height: '16px', color: '#0284c7' }} />
                <span style={{ fontSize: '14px', fontWeight: '500', color: '#0c4a6e' }}>키워드 지수 (N1)</span>
              </div>
              <div style={{ fontSize: '24px', fontWeight: 'bold', color: '#0284c7' }}>{myPlace.scores.keyword_score.toFixed(2)}</div>
              <div style={{ fontSize: '12px', color: '#64748b', marginTop: '4px' }}>키워드와의 관련성</div>
            </div>
            <div style={{ padding: '16px', background: '#f0fdf4', borderRadius: '12px', border: '1px solid #bbf7d0' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '8px' }}>
                <Target style={{ width: '16px', height: '16px', color: '#16a34a' }} />
                <span style={{ fontSize: '14px', fontWeight: '500', color: '#14532d' }}>품질 점수 (N2)</span>
              </div>
              <div style={{ fontSize: '24px', fontWeight: 'bold', color: '#16a34a' }}>{myPlace.scores.quality_score.toFixed(2)}</div>
              <div style={{ fontSize: '12px', color: '#64748b', marginTop: '4px' }}>리뷰, 저장수 등 품질</div>
            </div>
            <div style={{ padding: '16px', background: '#fefce8', borderRadius: '12px', border: '1px solid #fef08a' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '8px' }}>
                <Zap style={{ width: '16px', height: '16px', color: '#ca8a04' }} />
                <span style={{ fontSize: '14px', fontWeight: '500', color: '#713f12' }}>종합 경쟁력 (N3)</span>
              </div>
              <div style={{ fontSize: '24px', fontWeight: 'bold', color: '#ca8a04' }}>{myPlace.scores.competition_score.toFixed(2)}</div>
              <div style={{ fontSize: '12px', color: '#64748b', marginTop: '4px' }}>N1 + N2 종합 점수</div>
            </div>
          </div>
        </div>
      )}

      {/* 1위 비교 */}
      {comparison && myPlace && myPlace.rank !== 1 && (
        <div style={{ ...styles.card, marginBottom: '24px', background: '#fffbeb', border: '1px solid #fde68a' }}>
          <h3 style={{ fontSize: '16px', fontWeight: '600', color: '#92400e', marginBottom: '16px', display: 'flex', alignItems: 'center', gap: '8px' }}>
            <Trophy style={{ width: '18px', height: '18px', color: '#f59e0b' }} />
            1위와의 비교
          </h3>
          <div className="comparison-grid" style={{ display: 'grid', gap: '16px', textAlign: 'center' }}>
            <div>
              <div style={{ fontSize: '12px', color: '#92400e', marginBottom: '4px' }}>내 품질점수</div>
              <div style={{ fontSize: '24px', fontWeight: 'bold', color: '#1e293b' }}>{myPlace.scores.quality_score.toFixed(4)}</div>
            </div>
            <div>
              <div style={{ fontSize: '12px', color: '#92400e', marginBottom: '4px' }}>1위 품질점수</div>
              <div style={{ fontSize: '24px', fontWeight: 'bold', color: '#1e293b' }}>{comparison.rank_1_score.toFixed(4)}</div>
            </div>
            <div>
              <div style={{ fontSize: '12px', color: '#92400e', marginBottom: '4px' }}>점수 차이</div>
              <div style={{ fontSize: '24px', fontWeight: 'bold', color: '#dc2626' }}>-{comparison.rank_1_gap.toFixed(4)}</div>
            </div>
          </div>
        </div>
      )}

      {/* 경쟁사 순위 테이블 (상세 정보 포함) */}
      {allPlaces.length > 0 && (
        <div style={{ ...styles.card, marginBottom: '24px' }}>
          <h3 style={{ fontSize: '16px', fontWeight: '600', color: '#1e293b', marginBottom: '16px', display: 'flex', alignItems: 'center', gap: '8px' }}>
            <TrendingUp style={{ width: '18px', height: '18px', color: '#22c55e' }} />
            경쟁사 비교 분석 (상위 {Math.min(allPlaces.length, 50)}개)
          </h3>
          <div style={{ background: '#f8fafc', borderRadius: '12px', overflow: 'hidden', overflowX: 'auto' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', minWidth: '800px' }}>
              <thead>
                <tr style={{ background: '#f1f5f9' }}>
                  <th style={{ padding: '12px 12px', textAlign: 'left', fontSize: '12px', fontWeight: '600', color: '#64748b' }}>순위</th>
                  <th style={{ padding: '12px 12px', textAlign: 'left', fontSize: '12px', fontWeight: '600', color: '#64748b' }}>업체명</th>
                  <th style={{ padding: '12px 12px', textAlign: 'center', fontSize: '12px', fontWeight: '600', color: '#0284c7' }}>N1 (키워드)</th>
                  <th style={{ padding: '12px 12px', textAlign: 'center', fontSize: '12px', fontWeight: '600', color: '#16a34a' }}>N2 (품질)</th>
                  <th style={{ padding: '12px 12px', textAlign: 'center', fontSize: '12px', fontWeight: '600', color: '#ca8a04' }}>N3 (경쟁력)</th>
                  <th style={{ padding: '12px 12px', textAlign: 'center', fontSize: '12px', fontWeight: '600', color: '#64748b' }}>방문리뷰</th>
                  <th style={{ padding: '12px 12px', textAlign: 'center', fontSize: '12px', fontWeight: '600', color: '#64748b' }}>블로그</th>
                  <th style={{ padding: '12px 12px', textAlign: 'center', fontSize: '12px', fontWeight: '600', color: '#64748b' }}>저장수</th>
                </tr>
              </thead>
              <tbody>
                {allPlaces.slice(0, 50).map((place: any) => {
                  const isMyPlace = myPlace && place.name === myPlace.name;
                  return (
                    <tr key={place.place_id} style={{
                      background: isMyPlace ? '#eef2ff' : 'white',
                      borderBottom: '1px solid #e2e8f0'
                    }}>
                      <td style={{ padding: '12px 12px', fontSize: '14px' }}>
                        <span style={{ ...getRankBadgeStyle(place.rank), padding: '4px 10px', borderRadius: '8px', fontSize: '12px', fontWeight: '600' }}>
                          {place.rank}위
                        </span>
                      </td>
                      <td style={{ padding: '12px 12px', fontSize: '14px', fontWeight: isMyPlace ? '600' : '500', color: isMyPlace ? '#4f46e5' : '#1e293b', maxWidth: '150px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                        {place.name} {isMyPlace && <span style={{ color: '#6366f1', fontSize: '12px' }}>(ME)</span>}
                      </td>
                      <td style={{ padding: '12px 12px', textAlign: 'center', fontSize: '14px', fontWeight: '500', color: '#0284c7' }}>
                        {place.scores.keyword_score.toFixed(1)}
                      </td>
                      <td style={{ padding: '12px 12px', textAlign: 'center', fontSize: '14px', fontWeight: '600', color: '#16a34a' }}>
                        {place.scores.quality_score.toFixed(1)}
                      </td>
                      <td style={{ padding: '12px 12px', textAlign: 'center', fontSize: '14px', fontWeight: '500', color: '#ca8a04' }}>
                        {place.scores.competition_score.toFixed(1)}
                      </td>
                      <td style={{ padding: '12px 12px', textAlign: 'center', fontSize: '13px', color: '#64748b' }}>
                        {place.metrics.visit_count?.toLocaleString() || '0'}
                      </td>
                      <td style={{ padding: '12px 12px', textAlign: 'center', fontSize: '13px', color: '#64748b' }}>
                        {place.metrics.blog_count?.toLocaleString() || '0'}
                      </td>
                      <td style={{ padding: '12px 12px', textAlign: 'center', fontSize: '13px', color: '#64748b' }}>
                        {place.metrics.save_count?.toLocaleString() || '0'}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
          <div style={{ marginTop: '12px', padding: '12px', background: '#f1f5f9', borderRadius: '8px', fontSize: '12px', color: '#64748b' }}>
            <strong>지표 설명:</strong> N1=키워드 관련성, N2=품질(리뷰/저장 등), N3=종합 경쟁력. 모든 점수는 0-100 정규화.
          </div>
        </div>
      )}

      {/* 목표 순위 시뮬레이션 섹션 */}
      {myPlace && myPlace.rank > 1 && (
        <div style={{ ...styles.card, marginBottom: '24px', background: 'linear-gradient(135deg, #faf5ff, #f3e8ff)', border: '1px solid #e9d5ff' }}>
          <h3 style={{ fontSize: '18px', fontWeight: '600', color: '#7c3aed', marginBottom: '20px', display: 'flex', alignItems: 'center', gap: '10px' }}>
            <Target style={{ width: '20px', height: '20px', color: '#7c3aed' }} />
            목표 순위 시뮬레이션
          </h3>
          <p style={{ fontSize: '14px', color: '#6b7280', marginBottom: '20px' }}>
            목표 순위를 선택하면 필요한 점수 변화를 예측해드립니다.
          </p>

          {/* 현재 순위 표시 */}
          <div style={{ padding: '16px', background: 'white', borderRadius: '12px', border: '1px solid #e5e7eb', marginBottom: '16px' }}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
              <div>
                <div style={{ fontSize: '12px', color: '#64748b', marginBottom: '4px' }}>현재 순위</div>
                <div style={{ fontSize: '28px', fontWeight: 'bold', color: '#7c3aed' }}>{myPlace.rank}위</div>
              </div>
              <div style={{ textAlign: 'right' }}>
                <div style={{ fontSize: '12px', color: '#64748b', marginBottom: '4px' }}>목표 순위 선택</div>
                <select
                  value={targetRank}
                  onChange={(e) => {
                    setTargetRank(Number(e.target.value));
                    setTargetSimResult(null);
                  }}
                  style={{
                    padding: '10px 16px',
                    borderRadius: '10px',
                    border: '2px solid #7c3aed',
                    fontSize: '16px',
                    fontWeight: '600',
                    color: '#7c3aed',
                    background: 'white',
                    cursor: 'pointer',
                    minWidth: '100px',
                  }}
                >
                  {Array.from({ length: myPlace.rank - 1 }, (_, i) => i + 1).map((rank) => (
                    <option key={rank} value={rank}>
                      {rank}위
                    </option>
                  ))}
                </select>
              </div>
            </div>
          </div>

          {/* 버튼 그룹 */}
          <div style={{ display: 'flex', gap: '12px', marginBottom: '20px' }}>
            <button
              onClick={handleTargetRankSimulate}
              disabled={targetSimLoading}
              style={{
                ...styles.btnPrimary,
                background: 'linear-gradient(135deg, #7c3aed, #9333ea)',
                flex: 1,
                justifyContent: 'center',
                opacity: targetSimLoading ? 0.6 : 1,
              }}
            >
              {targetSimLoading ? (
                <Loader2 style={{ width: '18px', height: '18px', animation: 'spin 1s linear infinite' }} />
              ) : (
                <Play style={{ width: '18px', height: '18px' }} />
              )}
              {targetSimLoading ? '분석 중...' : `${targetRank}위 달성 분석`}
            </button>
            <button
              onClick={handleTargetSimReset}
              style={{ ...styles.btnSecondary }}
            >
              초기화
            </button>
          </div>

          {/* 시뮬레이션 결과 */}
          {targetSimResult && (
            <div style={{ background: 'white', borderRadius: '12px', padding: '20px', border: '1px solid #e5e7eb' }}>
              <h4 style={{ fontSize: '16px', fontWeight: '600', color: '#1e293b', marginBottom: '16px', display: 'flex', alignItems: 'center', gap: '8px' }}>
                <BarChart3 style={{ width: '18px', height: '18px', color: '#7c3aed' }} />
                {targetSimResult.target_rank}위 달성을 위한 분석
              </h4>

              {/* 순위 변화 미리보기 */}
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: '16px', marginBottom: '20px' }}>
                <div style={{ padding: '16px', background: '#f8fafc', borderRadius: '10px', textAlign: 'center' }}>
                  <div style={{ fontSize: '12px', color: '#64748b', marginBottom: '4px' }}>현재 순위</div>
                  <div style={{ fontSize: '28px', fontWeight: 'bold', color: '#1e293b' }}>{targetSimResult.current_rank}위</div>
                </div>
                <div style={{ padding: '16px', background: 'linear-gradient(135deg, #fef3c7, #fde68a)', borderRadius: '10px', textAlign: 'center', border: '1px solid #fde68a' }}>
                  <div style={{ fontSize: '12px', color: '#92400e', marginBottom: '4px' }}>목표 순위</div>
                  <div style={{ fontSize: '28px', fontWeight: 'bold', color: '#ca8a04' }}>{targetSimResult.target_rank}위</div>
                  <div style={{ fontSize: '12px', color: '#f59e0b', marginTop: '4px' }}>
                    {targetSimResult.current_rank - targetSimResult.target_rank}단계 상승 목표
                  </div>
                </div>
              </div>

              {/* N2 점수 변화 */}
              <div style={{ marginBottom: '16px', padding: '16px', background: '#f0fdf4', borderRadius: '12px', border: '1px solid #bbf7d0' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '12px' }}>
                  <Target style={{ width: '18px', height: '18px', color: '#16a34a' }} />
                  <span style={{ fontSize: '14px', fontWeight: '600', color: '#14532d' }}>품질점수 (N2) 변화 필요</span>
                </div>
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '12px', textAlign: 'center' }}>
                  <div>
                    <div style={{ fontSize: '11px', color: '#14532d', marginBottom: '4px' }}>현재 N2</div>
                    <div style={{ fontSize: '20px', fontWeight: 'bold', color: '#166534' }}>{targetSimResult.n2_change.current.toFixed(2)}</div>
                  </div>
                  <div>
                    <div style={{ fontSize: '11px', color: '#14532d', marginBottom: '4px' }}>목표 N2</div>
                    <div style={{ fontSize: '20px', fontWeight: 'bold', color: '#166534' }}>{targetSimResult.n2_change.target.toFixed(2)}</div>
                  </div>
                  <div>
                    <div style={{ fontSize: '11px', color: '#14532d', marginBottom: '4px' }}>필요 증가</div>
                    <div style={{ fontSize: '20px', fontWeight: 'bold', color: targetSimResult.n2_change.change > 0 ? '#dc2626' : '#16a34a' }}>
                      {targetSimResult.n2_change.change > 0 ? '+' : ''}{targetSimResult.n2_change.change.toFixed(2)}
                    </div>
                  </div>
                </div>
              </div>

              {/* N3 점수 변화 */}
              <div style={{ marginBottom: '16px', padding: '16px', background: 'linear-gradient(135deg, #fef3c7, #fde68a)', borderRadius: '12px', border: '1px solid #fcd34d' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '12px' }}>
                  <Zap style={{ width: '18px', height: '18px', color: '#ca8a04' }} />
                  <span style={{ fontSize: '14px', fontWeight: '600', color: '#92400e' }}>경쟁력점수 (N3) 예상 변화</span>
                </div>
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '12px', textAlign: 'center' }}>
                  <div>
                    <div style={{ fontSize: '11px', color: '#92400e', marginBottom: '4px' }}>현재 N3</div>
                    <div style={{ fontSize: '20px', fontWeight: 'bold', color: '#78350f' }}>{targetSimResult.n3_change.current.toFixed(2)}</div>
                  </div>
                  <div>
                    <div style={{ fontSize: '11px', color: '#92400e', marginBottom: '4px' }}>예상 N3</div>
                    <div style={{ fontSize: '20px', fontWeight: 'bold', color: '#78350f' }}>{targetSimResult.n3_change.target.toFixed(2)}</div>
                  </div>
                  <div>
                    <div style={{ fontSize: '11px', color: '#92400e', marginBottom: '4px' }}>예상 증가</div>
                    <div style={{ fontSize: '20px', fontWeight: 'bold', color: targetSimResult.n3_change.change > 0 ? '#16a34a' : '#78350f' }}>
                      {targetSimResult.n3_change.change > 0 ? '+' : ''}{targetSimResult.n3_change.change.toFixed(2)}
                    </div>
                  </div>
                </div>
              </div>

              {/* 메시지 */}
              <div style={{ padding: '16px', background: targetSimResult.is_achievable ? '#eff6ff' : '#fef2f2', borderRadius: '12px', border: `1px solid ${targetSimResult.is_achievable ? '#bfdbfe' : '#fecaca'}` }}>
                <div style={{ fontSize: '14px', color: targetSimResult.is_achievable ? '#1e40af' : '#991b1b', lineHeight: '1.6' }}>
                  {targetSimResult.message}
                </div>
                {!targetSimResult.is_achievable && (
                  <div style={{ marginTop: '8px', fontSize: '12px', color: '#dc2626' }}>
                    목표 달성이 어려울 수 있습니다. 더 현실적인 목표 순위를 설정해보세요.
                  </div>
                )}
              </div>

              {/* 안내 문구 */}
              <div style={{ marginTop: '16px', padding: '12px', background: '#f8fafc', borderRadius: '8px', fontSize: '12px', color: '#64748b' }}>
                <strong>분석 기준:</strong> {targetSimResult.data_source === 'cache' ? '캐싱된 키워드 파라미터' : 'ADLOG API 실시간 데이터'}<br />
                * 실제 순위는 경쟁사 변동에 따라 달라질 수 있습니다.
              </div>
            </div>
          )}
        </div>
      )}

      {/* 1위인 경우 축하 메시지 (시뮬레이션 대신) */}
      {myPlace && myPlace.rank === 1 && (
        <div style={{ ...styles.card, marginBottom: '24px', background: 'linear-gradient(135deg, #fef3c7, #fde68a)', textAlign: 'center', padding: '32px' }}>
          <Trophy style={{ width: '48px', height: '48px', color: '#f59e0b', margin: '0 auto 12px' }} />
          <h3 style={{ fontSize: '20px', fontWeight: 'bold', color: '#92400e', marginBottom: '8px' }}>축하합니다! 1위입니다!</h3>
          <p style={{ fontSize: '14px', color: '#a16207' }}>현재 순위를 유지하기 위해 지속적인 관리를 권장합니다.</p>
        </div>
      )}

      {/* 반응형 스타일 */}
      <style>{`
        @keyframes spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }

        .result-kpi-grid {
          grid-template-columns: repeat(4, 1fr);
        }

        .adlog-scores-grid {
          grid-template-columns: repeat(3, 1fr);
        }

        .comparison-grid {
          grid-template-columns: repeat(3, 1fr);
        }

        .recommendations-grid {
          grid-template-columns: repeat(2, 1fr);
        }

        .simulation-inputs-grid {
          grid-template-columns: repeat(2, 1fr);
        }

        .simulation-result-grid {
          grid-template-columns: repeat(4, 1fr);
        }

        .activity-grid {
          grid-template-columns: repeat(3, 1fr);
        }

        @media (max-width: 1024px) {
          .activity-grid {
            grid-template-columns: 1fr;
          }
          .result-kpi-grid {
            grid-template-columns: repeat(2, 1fr);
          }

          .adlog-scores-grid {
            grid-template-columns: repeat(3, 1fr);
          }

          .recommendations-grid {
            grid-template-columns: 1fr;
          }

          .simulation-inputs-grid {
            grid-template-columns: repeat(2, 1fr);
          }

          .simulation-result-grid {
            grid-template-columns: repeat(2, 1fr);
          }
        }

        @media (max-width: 640px) {
          .result-kpi-grid {
            grid-template-columns: 1fr;
          }

          .adlog-scores-grid {
            grid-template-columns: 1fr;
          }

          .comparison-grid {
            grid-template-columns: 1fr;
          }

          .simulation-inputs-grid {
            grid-template-columns: 1fr;
          }

          .simulation-result-grid {
            grid-template-columns: 1fr;
          }
        }
      `}</style>
    </div>
  );
}
