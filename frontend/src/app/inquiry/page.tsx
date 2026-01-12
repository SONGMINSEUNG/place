"use client";

import { useState, useEffect, useRef, Suspense } from "react";
import { useSearchParams } from "next/navigation";
import { Search, Loader2, ChevronRight, CheckCircle, TrendingUp, Target, Eye, Star, Trophy, BarChart3, Activity, Zap, Play, Sliders } from "lucide-react";
import { toast } from "sonner";
import { placeApi, analyzeApi, AnalyzeResponse, SimulateResponse, SimulateInputs, userDataApi, CorrelationResponse } from "@/lib/api";

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
  const [reservationCount, setReservationCount] = useState<string>("");
  const [loading, setLoading] = useState(false);
  const [searching, setSearching] = useState(false);
  const [analyzeResult, setAnalyzeResult] = useState<AnalyzeResponse | null>(null);
  const [searchResults, setSearchResults] = useState<SearchResult[]>([]);
  const [selectedPlace, setSelectedPlace] = useState<SearchResult | null>(null);
  const [userTrafficCount, setUserTrafficCount] = useState<number | null>(null);
  const [userReservationCount, setUserReservationCount] = useState<number | null>(null);

  // 시뮬레이션 관련 상태
  const [simBlogReview, setSimBlogReview] = useState<number>(0);
  const [simVisitReview, setSimVisitReview] = useState<number>(0);
  const [simInflow, setSimInflow] = useState<number>(0);
  const [simReservation, setSimReservation] = useState<number>(0);
  const [simLoading, setSimLoading] = useState(false);
  const [simResult, setSimResult] = useState<SimulateResponse | null>(null);

  // URL 파라미터에서 초기값 설정 및 자동 검색
  // 의존성 배열을 빈 배열로 변경하여 무한 렌더링 방지
  // searchParams 객체 참조가 매 렌더링마다 변경되어 무한 루프 유발
  useEffect(() => {
    if (initialLoadDone.current) return;

    const urlPlaceName = searchParams.get('placeName');
    const urlKeyword = searchParams.get('keyword');
    const urlTraffic = searchParams.get('traffic');
    const urlReservation = searchParams.get('reservation');

    if (urlPlaceName) {
      setPlaceName(urlPlaceName);
      // 자동으로 업체 검색 시작
      autoSearchPlace(urlPlaceName, urlKeyword || '', urlTraffic || '', urlReservation || '');
    }
    if (urlKeyword) {
      setKeywords(urlKeyword);
    }
    if (urlTraffic) {
      setTrafficCount(urlTraffic);
    }
    if (urlReservation) {
      setReservationCount(urlReservation);
    }

    initialLoadDone.current = true;
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // 자동 업체 검색 함수
  const autoSearchPlace = async (name: string, keyword: string, traffic: string, reservation: string) => {
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
            autoRankSearch(firstPlace, keyword, traffic, reservation);
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
  const autoRankSearch = async (place: SearchResult, keyword: string, traffic: string, reservation: string) => {
    setLoading(true);
    try {
      const trafficNum = traffic ? parseInt(traffic, 10) : undefined;
      const reservationNum = reservation ? parseInt(reservation, 10) : undefined;

      setUserTrafficCount(trafficNum || null);
      setUserReservationCount(reservationNum || null);

      // ADLOG API 호출 (정규화된 점수 반환)
      const analyzeData = await analyzeApi.analyze(
        keyword,
        place.name,
        trafficNum,
        reservationNum
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
      const reservationNum = reservationCount ? parseInt(reservationCount, 10) : undefined;

      setUserTrafficCount(trafficNum || null);
      setUserReservationCount(reservationNum || null);

      // ADLOG API 호출 (정규화된 점수 반환)
      const analyzeData = await analyzeApi.analyze(
        keywords.trim(),
        selectedPlace.name,
        trafficNum,
        reservationNum
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
    setReservationCount("");
    setUserTrafficCount(null);
    setUserReservationCount(null);
    // 시뮬레이션 상태 초기화
    setSimBlogReview(0);
    setSimVisitReview(0);
    setSimInflow(0);
    setSimReservation(0);
    setSimResult(null);
  };

  // 시뮬레이션 실행
  const handleSimulate = async () => {
    if (!selectedPlace || !analyzeResult?.keyword) {
      toast.error("분석 결과가 없습니다");
      return;
    }

    if (simBlogReview === 0 && simVisitReview === 0 && simInflow === 0 && simReservation === 0) {
      toast.error("시뮬레이션할 값을 입력해주세요");
      return;
    }

    setSimLoading(true);
    try {
      const inputs: SimulateInputs = {
        blog_review: simBlogReview,
        visit_review: simVisitReview,
        inflow: simInflow,
        reservation: simReservation,
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
    setSimReservation(0);
    setSimResult(null);
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

                  {/* 반응형 그리드 */}
                  <div className="input-grid" style={{ display: 'grid', gap: '12px' }}>
                    <div>
                      <label style={{ fontSize: '14px', fontWeight: '500', color: '#374151', display: 'block', marginBottom: '8px' }}>
                        유입수 <span style={{ color: '#94a3b8', fontWeight: '400' }}>(선택)</span>
                      </label>
                      <input
                        type="number"
                        placeholder="네이버 통계 유입수"
                        value={trafficCount}
                        onChange={(e) => setTrafficCount(e.target.value)}
                        style={styles.input}
                      />
                    </div>
                    <div>
                      <label style={{ fontSize: '14px', fontWeight: '500', color: '#374151', display: 'block', marginBottom: '8px' }}>
                        예약건수 <span style={{ color: '#94a3b8', fontWeight: '400' }}>(선택)</span>
                      </label>
                      <input
                        type="number"
                        placeholder="일 예약 건수"
                        value={reservationCount}
                        onChange={(e) => setReservationCount(e.target.value)}
                        style={styles.input}
                      />
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
                <Star style={{ width: '20px', height: '20px', color: '#f59e0b' }} />
              </div>
              <span style={{ fontSize: '14px', color: '#64748b' }}>예약건수 (입력값)</span>
            </div>
            <span style={{ fontSize: '28px', fontWeight: 'bold', color: '#1e293b' }}>{userReservationCount?.toLocaleString() || '-'}</span>
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

      {/* 1위인 경우 축하 */}
      {myPlace && myPlace.rank === 1 && (
        <div style={{ ...styles.card, marginBottom: '24px', background: 'linear-gradient(135deg, #fef3c7, #fde68a)', textAlign: 'center', padding: '32px' }}>
          <Trophy style={{ width: '48px', height: '48px', color: '#f59e0b', margin: '0 auto 12px' }} />
          <h3 style={{ fontSize: '20px', fontWeight: 'bold', color: '#92400e', marginBottom: '8px' }}>축하합니다! 1위입니다!</h3>
          <p style={{ fontSize: '14px', color: '#a16207' }}>현재 순위를 유지하기 위해 지속적인 관리를 권장합니다.</p>
        </div>
      )}

      {/* 경쟁사 순위 테이블 (상세 정보 포함) */}
      {allPlaces.length > 0 && (
        <div style={{ ...styles.card, marginBottom: '24px' }}>
          <h3 style={{ fontSize: '16px', fontWeight: '600', color: '#1e293b', marginBottom: '16px', display: 'flex', alignItems: 'center', gap: '8px' }}>
            <TrendingUp style={{ width: '18px', height: '18px', color: '#22c55e' }} />
            경쟁사 비교 분석 (상위 {Math.min(allPlaces.length, 10)}개)
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
                {allPlaces.slice(0, 10).map((place: any) => {
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

      {/* 마케팅 제언 */}
      {recommendations.length > 0 && (
        <div style={{ ...styles.card, marginBottom: '24px' }}>
          <h3 style={{ fontSize: '16px', fontWeight: '600', color: '#1e293b', marginBottom: '16px', display: 'flex', alignItems: 'center', gap: '8px' }}>
            <Target style={{ width: '18px', height: '18px', color: '#6366f1' }} />
            마케팅 제언
          </h3>
          <p style={{ fontSize: '13px', color: '#64748b', marginBottom: '16px', padding: '12px', background: '#eff6ff', borderRadius: '8px', border: '1px solid #bfdbfe' }}>
            <strong>N3(경쟁력 점수)</strong>가 올라가면 순위가 상승합니다. 아래 활동으로 N3를 높여보세요.
          </p>
          <div className="recommendations-grid" style={{ display: 'grid', gap: '12px' }}>
            {recommendations.map((rec: any, idx: number) => (
              <div key={idx} style={{ padding: '16px', background: '#f8fafc', borderRadius: '12px', border: '1px solid #e2e8f0' }}>
                <div style={{ fontWeight: '600', color: '#1e293b', marginBottom: '8px' }}>{rec.type}</div>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '8px' }}>
                  <span style={{ fontSize: '14px', color: '#64748b' }}>{rec.amount}{rec.unit} 추가 시</span>
                  <div style={{ textAlign: 'right' }}>
                    {rec.n3_effect !== undefined && (
                      <div style={{ fontSize: '16px', fontWeight: 'bold', color: '#ca8a04' }}>N3 +{rec.n3_effect.toFixed(2)}점</div>
                    )}
                    <div style={{ fontSize: '13px', color: '#22c55e' }}>N2 +{rec.effect.toFixed(2)}점</div>
                  </div>
                </div>
                {rec.description && (
                  <div style={{ marginTop: '8px', fontSize: '12px', color: '#6366f1', fontWeight: '500' }}>
                    {rec.description}
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* 시뮬레이션 섹션 */}
      {myPlace && (
        <div style={{ ...styles.card, marginBottom: '24px', background: 'linear-gradient(135deg, #faf5ff, #f3e8ff)', border: '1px solid #e9d5ff' }}>
          <h3 style={{ fontSize: '18px', fontWeight: '600', color: '#7c3aed', marginBottom: '20px', display: 'flex', alignItems: 'center', gap: '10px' }}>
            <Sliders style={{ width: '20px', height: '20px', color: '#7c3aed' }} />
            순위 시뮬레이션
          </h3>
          <p style={{ fontSize: '14px', color: '#6b7280', marginBottom: '20px' }}>
            각 항목의 예상 증가량을 입력하고 순위 변화를 예측해보세요.
          </p>

          {/* 입력 필드 */}
          <div className="simulation-inputs-grid" style={{ display: 'grid', gap: '16px', marginBottom: '20px' }}>
            {/* 블로그 리뷰 */}
            <div style={{ padding: '16px', background: 'white', borderRadius: '12px', border: '1px solid #e5e7eb' }}>
              <label style={{ fontSize: '14px', fontWeight: '500', color: '#374151', display: 'block', marginBottom: '8px' }}>
                블로그 리뷰 추가
              </label>
              <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                <input
                  type="range"
                  min="0"
                  max="50"
                  value={simBlogReview}
                  onChange={(e) => setSimBlogReview(Number(e.target.value))}
                  style={{ flex: 1, accentColor: '#7c3aed' }}
                />
                <input
                  type="number"
                  min="0"
                  value={simBlogReview}
                  onChange={(e) => setSimBlogReview(Math.max(0, Number(e.target.value)))}
                  style={{ ...styles.input, width: '80px', textAlign: 'center' }}
                />
                <span style={{ fontSize: '14px', color: '#6b7280' }}>개</span>
              </div>
            </div>

            {/* 방문자 리뷰 */}
            <div style={{ padding: '16px', background: 'white', borderRadius: '12px', border: '1px solid #e5e7eb' }}>
              <label style={{ fontSize: '14px', fontWeight: '500', color: '#374151', display: 'block', marginBottom: '8px' }}>
                방문자 리뷰 추가
              </label>
              <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                <input
                  type="range"
                  min="0"
                  max="100"
                  value={simVisitReview}
                  onChange={(e) => setSimVisitReview(Number(e.target.value))}
                  style={{ flex: 1, accentColor: '#7c3aed' }}
                />
                <input
                  type="number"
                  min="0"
                  value={simVisitReview}
                  onChange={(e) => setSimVisitReview(Math.max(0, Number(e.target.value)))}
                  style={{ ...styles.input, width: '80px', textAlign: 'center' }}
                />
                <span style={{ fontSize: '14px', color: '#6b7280' }}>개</span>
              </div>
            </div>

            {/* 유입수 */}
            <div style={{ padding: '16px', background: 'white', borderRadius: '12px', border: '1px solid #e5e7eb' }}>
              <label style={{ fontSize: '14px', fontWeight: '500', color: '#374151', display: 'block', marginBottom: '8px' }}>
                유입수 증가량
              </label>
              <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                <input
                  type="range"
                  min="0"
                  max="500"
                  step="10"
                  value={simInflow}
                  onChange={(e) => setSimInflow(Number(e.target.value))}
                  style={{ flex: 1, accentColor: '#7c3aed' }}
                />
                <input
                  type="number"
                  min="0"
                  value={simInflow}
                  onChange={(e) => setSimInflow(Math.max(0, Number(e.target.value)))}
                  style={{ ...styles.input, width: '80px', textAlign: 'center' }}
                />
                <span style={{ fontSize: '14px', color: '#6b7280' }}>명</span>
              </div>
            </div>

            {/* 예약수 */}
            <div style={{ padding: '16px', background: 'white', borderRadius: '12px', border: '1px solid #e5e7eb' }}>
              <label style={{ fontSize: '14px', fontWeight: '500', color: '#374151', display: 'block', marginBottom: '8px' }}>
                예약수 증가량
              </label>
              <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                <input
                  type="range"
                  min="0"
                  max="100"
                  value={simReservation}
                  onChange={(e) => setSimReservation(Number(e.target.value))}
                  style={{ flex: 1, accentColor: '#7c3aed' }}
                />
                <input
                  type="number"
                  min="0"
                  value={simReservation}
                  onChange={(e) => setSimReservation(Math.max(0, Number(e.target.value)))}
                  style={{ ...styles.input, width: '80px', textAlign: 'center' }}
                />
                <span style={{ fontSize: '14px', color: '#6b7280' }}>건</span>
              </div>
            </div>
          </div>

          {/* 버튼 그룹 */}
          <div style={{ display: 'flex', gap: '12px', marginBottom: '20px' }}>
            <button
              onClick={handleSimulate}
              disabled={simLoading}
              style={{
                ...styles.btnPrimary,
                background: 'linear-gradient(135deg, #7c3aed, #9333ea)',
                flex: 1,
                justifyContent: 'center',
                opacity: simLoading ? 0.6 : 1,
              }}
            >
              {simLoading ? (
                <Loader2 style={{ width: '18px', height: '18px', animation: 'spin 1s linear infinite' }} />
              ) : (
                <Play style={{ width: '18px', height: '18px' }} />
              )}
              {simLoading ? '시뮬레이션 중...' : '시뮬레이션 실행'}
            </button>
            <button
              onClick={handleSimReset}
              style={{ ...styles.btnSecondary }}
            >
              초기화
            </button>
          </div>

          {/* 시뮬레이션 결과 */}
          {simResult && (
            <div style={{ background: 'white', borderRadius: '12px', padding: '20px', border: '1px solid #e5e7eb' }}>
              <h4 style={{ fontSize: '16px', fontWeight: '600', color: '#1e293b', marginBottom: '16px', display: 'flex', alignItems: 'center', gap: '8px' }}>
                <BarChart3 style={{ width: '18px', height: '18px', color: '#7c3aed' }} />
                시뮬레이션 결과
              </h4>

              {/* N3 경쟁력 점수 (핵심 지표) */}
              {simResult.current_n3 !== undefined && simResult.predicted_n3 !== undefined && (
                <div style={{ marginBottom: '20px', padding: '16px', background: 'linear-gradient(135deg, #fef3c7, #fde68a)', borderRadius: '12px', border: '1px solid #fcd34d' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '12px' }}>
                    <Zap style={{ width: '18px', height: '18px', color: '#ca8a04' }} />
                    <span style={{ fontSize: '14px', fontWeight: '600', color: '#92400e' }}>경쟁력점수 (N3) - 순위 결정 핵심 지표</span>
                  </div>
                  <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '12px', textAlign: 'center' }}>
                    <div>
                      <div style={{ fontSize: '11px', color: '#92400e', marginBottom: '4px' }}>현재 N3</div>
                      <div style={{ fontSize: '22px', fontWeight: 'bold', color: '#78350f' }}>{simResult.current_n3.toFixed(2)}</div>
                    </div>
                    <div>
                      <div style={{ fontSize: '11px', color: '#92400e', marginBottom: '4px' }}>예상 N3</div>
                      <div style={{ fontSize: '22px', fontWeight: 'bold', color: '#78350f' }}>{simResult.predicted_n3.toFixed(2)}</div>
                    </div>
                    <div>
                      <div style={{ fontSize: '11px', color: '#92400e', marginBottom: '4px' }}>N3 변화</div>
                      <div style={{ fontSize: '22px', fontWeight: 'bold', color: simResult.n3_change && simResult.n3_change > 0 ? '#16a34a' : '#78350f' }}>
                        {simResult.n3_change && simResult.n3_change > 0 ? '+' : ''}{(simResult.n3_change || 0).toFixed(2)}
                      </div>
                    </div>
                  </div>
                  <div style={{ marginTop: '12px', fontSize: '12px', color: '#92400e', textAlign: 'center' }}>
                    N3가 올라가면 순위가 상승합니다
                  </div>
                </div>
              )}

              {/* 순위 변화 */}
              <div className="simulation-result-grid" style={{ display: 'grid', gap: '16px', marginBottom: '20px' }}>
                <div style={{ padding: '16px', background: '#f8fafc', borderRadius: '10px', textAlign: 'center' }}>
                  <div style={{ fontSize: '12px', color: '#64748b', marginBottom: '4px' }}>현재 순위</div>
                  <div style={{ fontSize: '24px', fontWeight: 'bold', color: '#1e293b' }}>{simResult.current_rank}위</div>
                </div>
                <div style={{ padding: '16px', background: simResult.predicted_rank < simResult.current_rank ? '#fef3c7' : '#f8fafc', borderRadius: '10px', textAlign: 'center', border: simResult.predicted_rank < simResult.current_rank ? '1px solid #fde68a' : 'none' }}>
                  <div style={{ fontSize: '12px', color: simResult.predicted_rank < simResult.current_rank ? '#ca8a04' : '#64748b', marginBottom: '4px' }}>예상 순위</div>
                  <div style={{ fontSize: '24px', fontWeight: 'bold', color: simResult.predicted_rank < simResult.current_rank ? '#ca8a04' : '#1e293b' }}>{simResult.predicted_rank}위</div>
                  {simResult.predicted_rank < simResult.current_rank && (
                    <div style={{ fontSize: '12px', color: '#f59e0b', marginTop: '4px' }}>
                      {simResult.current_rank - simResult.predicted_rank}순위 상승
                    </div>
                  )}
                </div>
                <div style={{ padding: '16px', background: '#f8fafc', borderRadius: '10px', textAlign: 'center' }}>
                  <div style={{ fontSize: '12px', color: '#64748b', marginBottom: '4px' }}>현재 N2</div>
                  <div style={{ fontSize: '24px', fontWeight: 'bold', color: '#1e293b' }}>{simResult.current_score.toFixed(2)}</div>
                </div>
                <div style={{ padding: '16px', background: '#f0fdf4', borderRadius: '10px', textAlign: 'center', border: '1px solid #bbf7d0' }}>
                  <div style={{ fontSize: '12px', color: '#16a34a', marginBottom: '4px' }}>예상 N2</div>
                  <div style={{ fontSize: '24px', fontWeight: 'bold', color: '#16a34a' }}>{simResult.predicted_score.toFixed(2)}</div>
                  <div style={{ fontSize: '12px', color: '#22c55e', marginTop: '4px' }}>+{simResult.total_effect.toFixed(2)}점</div>
                </div>
              </div>

              {/* 항목별 효과 */}
              <div style={{ marginTop: '16px' }}>
                <h5 style={{ fontSize: '14px', fontWeight: '600', color: '#374151', marginBottom: '12px' }}>항목별 예상 효과</h5>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                  {simResult.effects.blog_review && simResult.effects.blog_review.amount > 0 && (
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '10px 12px', background: '#f8fafc', borderRadius: '8px' }}>
                      <span style={{ fontSize: '14px', color: '#64748b' }}>블로그 리뷰 +{simResult.effects.blog_review.amount}개</span>
                      <span style={{ fontSize: '14px', fontWeight: '600', color: '#22c55e' }}>+{simResult.effects.blog_review.effect.toFixed(2)}점</span>
                    </div>
                  )}
                  {simResult.effects.visit_review && simResult.effects.visit_review.amount > 0 && (
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '10px 12px', background: '#f8fafc', borderRadius: '8px' }}>
                      <span style={{ fontSize: '14px', color: '#64748b' }}>방문자 리뷰 +{simResult.effects.visit_review.amount}개</span>
                      <span style={{ fontSize: '14px', fontWeight: '600', color: '#22c55e' }}>+{simResult.effects.visit_review.effect.toFixed(2)}점</span>
                    </div>
                  )}
                  {simResult.effects.inflow && simResult.effects.inflow.amount > 0 && (
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '10px 12px', background: '#f8fafc', borderRadius: '8px' }}>
                      <span style={{ fontSize: '14px', color: '#64748b' }}>유입수 +{simResult.effects.inflow.amount}명</span>
                      <span style={{ fontSize: '14px', fontWeight: '600', color: '#22c55e' }}>+{simResult.effects.inflow.effect.toFixed(2)}점</span>
                    </div>
                  )}
                  {simResult.effects.reservation && simResult.effects.reservation.amount > 0 && (
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '10px 12px', background: '#f8fafc', borderRadius: '8px' }}>
                      <span style={{ fontSize: '14px', color: '#64748b' }}>예약수 +{simResult.effects.reservation.amount}건</span>
                      <span style={{ fontSize: '14px', fontWeight: '600', color: '#22c55e' }}>+{simResult.effects.reservation.effect.toFixed(2)}점</span>
                    </div>
                  )}
                </div>
              </div>

              {/* 안내 문구 */}
              <div style={{ marginTop: '16px', padding: '12px', background: '#eff6ff', borderRadius: '8px', fontSize: '12px', color: '#2563eb' }}>
                <strong>순위 = N3(경쟁력점수) 내림차순</strong><br />
                * N3는 N1(키워드지수)과 N2(품질점수)의 조합으로 계산됩니다.<br />
                * 시뮬레이션 결과는 현재 데이터 기준 예측값이며, 실제 결과와 다를 수 있습니다.
              </div>
            </div>
          )}
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

        @media (max-width: 1024px) {
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
