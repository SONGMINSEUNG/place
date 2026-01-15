import axios from 'axios';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8001/api';

const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

// 토큰 인터셉터
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// 응답 인터셉터
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem('token');
      window.location.href = '/login';
    }
    return Promise.reject(error);
  }
);

// Types
export interface PlaceInfo {
  place_id: string;
  name: string;
  category?: string;
  address?: string;
  road_address?: string;
  phone?: string;
  visitor_review_count: number;
  blog_review_count: number;
  save_count: number;
  place_score: number;
  description?: string;
  keywords: string[];
}

// 4가지 요소별 가중치 (%) - 키워드별로 다름
export interface FactorWeights {
  visitor_review: number;  // 방문자 리뷰 가중치
  blog_review: number;     // 블로그 리뷰 가중치
  freshness: number;       // 최신성(1주일 내 리뷰) 가중치
  hidden: number;          // 히든(저장수+유입수) 가중치
}

// 요소별 개별 점수 (100점 만점)
export interface FactorScores {
  visitor_review: number;
  blog_review: number;
  freshness: number;
  hidden: number;
}

// 추천 방안 타입
export interface Recommendation {
  type: 'summary' | 'visitor_review' | 'blog_review' | 'freshness' | 'hidden' | 'advantage';
  priority: 'critical' | 'high' | 'medium' | 'good' | 'info';
  title?: string;
  message: string;
  detail?: string;
  action?: string;
  score_gap?: number;
  weight?: number;
}

// 업체별 데이터 (place_data 배열 항목)
export interface PlaceData {
  place_id: string;
  name: string;
  rank: number;
  visitor_review_count: number;
  blog_review_count: number;
  freshness_count: number;
  // 개별 점수 (0-100)
  visitor_score: number;
  blog_score: number;
  freshness_score: number;
  hidden_score: number;
  visible_score: number;
  // 기여 점수 (가중치 적용, 합계 = total_score)
  visitor_contribution: number;
  blog_contribution: number;
  freshness_contribution: number;
  hidden_contribution: number;
  total_score: number;
}

// 비교 차이값
export interface ComparisonDiff {
  visitor_review: number;
  blog_review: number;
  freshness: number;
  visitor_score?: number;
  blog_score?: number;
  freshness_score?: number;
  hidden_score?: number;
}

// 비교 대상 업체 (위)
export interface ComparisonAbove {
  rank: number;
  name: string;
  place_id: string;
  scores: FactorScores;
  counts: {
    visitor_review: number;
    blog_review: number;
    freshness: number;
  };
  diff: ComparisonDiff;
}

// 비교 대상 업체 (아래)
export interface ComparisonBelow {
  rank: number;
  name: string;
  place_id: string;
  scores: FactorScores;
  counts: {
    visitor_review: number;
    blog_review: number;
    freshness: number;
  };
  diff: ComparisonDiff;
}

// 최적 전략 액션
export interface OptimalAction {
  factor: string;
  name: string;
  needed: number;
  gain: number;
  action: string;
}

// 효율성 순위
export interface EfficiencyRank {
  factor: string;
  name: string;
  potential_gain: number;
  points_per_unit: number;
  needed_for_first: number | null;
}

// 최적 전략
export interface OptimalStrategy {
  current_score: number;
  target_score: number;
  gap: number;
  actions: OptimalAction[];
  total_expected_gain: number;
  remaining_gap: number;
  achievable: boolean;
  efficiency_rank: EfficiencyRank[];
}

// 타겟 분석 결과
export interface TargetAnalysis {
  rank: number;
  total_places: number;
  total_score: number;
  scores: FactorScores;
  counts: {
    visitor_review: number;
    blog_review: number;
    freshness: number;
  };
  contributions?: {
    visitor_review: number;
    blog_review: number;
    freshness: number;
    hidden: number;
  };
  first_counts?: {
    visitor_review: number;
    blog_review: number;
    freshness: number;
  };
  max_counts?: {
    visitor_review: number;
    blog_review: number;
    freshness: number;
  };
  needed_for_first?: {
    visitor_review: number;
    blog_review: number;
    freshness: number;
  };
  optimal_strategy?: OptimalStrategy;
  user_traffic_count?: number;
  estimated_traffic_count?: number;
  estimated_first_traffic?: number;
  traffic_gap?: number;
  is_first: boolean;
  comparison_above: ComparisonAbove[];
  comparison_below: ComparisonBelow[];
}

// 키워드 분석 결과 (4가지 요소 구조)
export interface KeywordAnalysis {
  factor_weights: FactorWeights;     // 4가지 요소별 가중치 (%)
  place_data: PlaceData[];           // 업체별 데이터
  correlations: {                    // 상관계수
    visitor_review: number;
    blog_review: number;
    freshness: number;
  };
  ranking_explanation: string;
  target_analysis: TargetAnalysis | null;
  recommendations: Recommendation[];
}

export interface PlaceRankResult {
  place_id: string;
  keyword: string;
  rank: number | null;
  total_results: number;
  target_place: any;
  competitors: any[];
  analysis?: KeywordAnalysis | null;
}

export interface HiddenKeyword {
  keyword: string;
  rank: number;
  total_results: number;
  potential: string;
}

export interface DailyData {
  date: string;
  rank: number | null;
  visitor_review_count: number;
  blog_review_count: number;
  place_score?: number;
}

export interface SavedKeyword {
  id: number;
  place_id: string;
  place_name?: string;
  keyword: string;
  last_rank?: number;
  best_rank?: number;
  visitor_review_count: number;
  blog_review_count: number;
  place_score?: number;
  weekly_data: DailyData[];
  is_active: boolean;
  created_at: string;
}

export interface Competitor {
  rank: number;
  place_id: string;
  name: string;
  category?: string;
  visitor_review_count: number;
  blog_review_count: number;
  save_count: number;
}

export interface AnalysisResult {
  place_info: PlaceInfo;
  keyword_ranks: Array<{
    keyword: string;
    rank: number | null;
    total_results: number;
  }>;
  competitiveness: {
    target_score: number;
    average_competitor_score: number;
    score_rank: number;
    total_competitors: number;
    strengths: string[];
    weaknesses: string[];
    top_competitors: any[];
  };
}

// API Functions
export const placeApi = {
  // 플레이스 순위 조회
  getRank: async (placeIdOrUrl: string, keywords: string[], trafficCount?: number): Promise<PlaceRankResult[]> => {
    // place_id만 받으면 URL로 변환
    const place_url = placeIdOrUrl.includes('place.naver.com')
      ? placeIdOrUrl
      : `https://m.place.naver.com/restaurant/${placeIdOrUrl}`;

    const { data } = await api.post('/place/rank', {
      place_url,
      keywords,
      traffic_count: trafficCount || null,
    });
    return data;
  },

  // 플레이스 정보 조회
  getInfo: async (placeId: string): Promise<PlaceInfo> => {
    const { data } = await api.get(`/place/info/${placeId}`);
    return data;
  },

  // URL로 플레이스 정보 조회
  getInfoByUrl: async (url: string): Promise<PlaceInfo> => {
    const { data } = await api.get('/place/info-by-url', { params: { url } });
    return data;
  },

  // 종합 분석
  analyze: async (placeIdOrUrl: string, keywords: string[]): Promise<AnalysisResult> => {
    const place_url = placeIdOrUrl.includes('place.naver.com')
      ? placeIdOrUrl
      : `https://m.place.naver.com/restaurant/${placeIdOrUrl}`;

    const { data } = await api.post('/place/analysis', {
      place_url,
      keywords,
    });
    return data;
  },

  // 히든 키워드 분석
  getHiddenKeywords: async (placeIdOrUrl: string): Promise<HiddenKeyword[]> => {
    const place_url = placeIdOrUrl.includes('place.naver.com')
      ? placeIdOrUrl
      : `https://m.place.naver.com/restaurant/${placeIdOrUrl}`;

    const { data } = await api.post('/place/hidden-keywords', {
      place_url,
    });
    return data;
  },

  // 리포트 생성
  generateReport: async (placeIdOrUrl: string, keywords: string[]) => {
    const place_url = placeIdOrUrl.includes('place.naver.com')
      ? placeIdOrUrl
      : `https://m.place.naver.com/restaurant/${placeIdOrUrl}`;

    const { data } = await api.post('/place/report', {
      place_url,
      keywords,
    });
    return data;
  },

  // 플레이스 검색
  search: async (keyword: string, limit = 50) => {
    const { data } = await api.get('/place/search', {
      params: { keyword, limit },
    });
    return data;
  },

  // 경쟁사 조회
  getCompetitors: async (placeIdOrUrl: string, keyword: string, limit = 20) => {
    const place_url = placeIdOrUrl.includes('place.naver.com')
      ? placeIdOrUrl
      : `https://m.place.naver.com/restaurant/${placeIdOrUrl}`;

    const { data } = await api.get('/place/competitors', {
      params: { place_url, keyword, limit },
    });
    return data;
  },
};

export const keywordsApi = {
  // 키워드 저장
  save: async (placeIdOrUrl: string, keyword: string, placeName?: string): Promise<SavedKeyword> => {
    const place_url = placeIdOrUrl.includes('place.naver.com')
      ? placeIdOrUrl
      : `https://m.place.naver.com/restaurant/${placeIdOrUrl}`;

    const { data } = await api.post('/keywords/save', {
      place_url,
      keyword,
      place_name: placeName,
    });
    return data;
  },

  // 저장된 키워드 목록
  getAll: async (): Promise<SavedKeyword[]> => {
    const { data } = await api.get('/keywords/');
    return data;
  },

  // 키워드 삭제
  delete: async (keywordId: number): Promise<void> => {
    await api.delete(`/keywords/${keywordId}`);
  },

  // 순위 새로고침
  refresh: async (keywordId: number) => {
    const { data } = await api.post(`/keywords/${keywordId}/refresh`);
    return data;
  },

  // 히스토리 조회
  getHistory: async (keywordId: number, days = 30) => {
    const { data } = await api.get(`/keywords/${keywordId}/history`, {
      params: { days },
    });
    return data;
  },

  // 전체 새로고침
  refreshAll: async () => {
    const { data } = await api.post('/keywords/refresh-all');
    return data;
  },
};

// 브랜드(플레이스명) 분석 API
export const brandApi = {
  // 플레이스명으로 검색
  analyzeByName: async (name: string, maxResults = 50) => {
    const { data } = await api.get('/place/analyze-by-name', {
      params: { name, max_results: maxResults },
    });
    return data;
  },

  // 상세 비교
  compareByName: async (name: string, maxResults = 30) => {
    const { data } = await api.get('/place/analyze-by-name/compare', {
      params: { name, max_results: maxResults },
    });
    return data;
  },

  // 브랜드 키워드 분석
  getKeywords: async (name: string, maxResults = 30) => {
    const { data } = await api.get('/place/analyze-by-name/keywords', {
      params: { name, max_results: maxResults },
    });
    return data;
  },
};

// 저장 체크 API
export const saveTrackerApi = {
  // 트래커 등록
  create: async (placeUrl: string, keyword: string, groupName = '기본', memo?: string) => {
    const { data } = await api.post('/place/save-tracker', {
      place_url: placeUrl,
      keyword,
      group_name: groupName,
      memo,
    });
    return data;
  },

  // 목록 조회
  getAll: async (groupName?: string, isActive?: number) => {
    const { data } = await api.get('/place/save-tracker', {
      params: { group_name: groupName, is_active: isActive },
    });
    return data;
  },

  // 상세 조회
  getDetail: async (trackerId: number, historyDays = 30) => {
    const { data } = await api.get(`/place/save-tracker/${trackerId}`, {
      params: { history_days: historyDays },
    });
    return data;
  },

  // 수정
  update: async (trackerId: number, updates: { group_name?: string; memo?: string; is_active?: number }) => {
    const { data } = await api.put(`/place/save-tracker/${trackerId}`, updates);
    return data;
  },

  // 삭제
  delete: async (trackerId: number) => {
    const { data } = await api.delete(`/place/save-tracker/${trackerId}`);
    return data;
  },

  // 즉시 체크
  check: async (trackerId: number, recordHistory = true) => {
    const { data } = await api.post(`/place/save-tracker/${trackerId}/check`, null, {
      params: { record_history: recordHistory },
    });
    return data;
  },

  // 전체 체크
  checkAll: async (recordHistory = true) => {
    const { data } = await api.post('/place/save-tracker/check-all', null, {
      params: { record_history: recordHistory },
    });
    return data;
  },

  // 그룹 목록
  getGroups: async () => {
    const { data } = await api.get('/place/save-tracker/groups');
    return data;
  },

  // 요약 통계
  getSummary: async () => {
    const { data } = await api.get('/place/save-tracker/summary');
    return data;
  },
};

// 키워드 트렌드 API
export const trendApi = {
  // 키워드 트렌드
  getTrend: async (keyword: string, days = 30) => {
    const { data } = await api.get('/place/keyword-trend', {
      params: { keyword, days },
    });
    return data;
  },

  // 키워드 비교
  compare: async (keywords: string[], days = 30) => {
    const { data } = await api.get('/place/keyword-trend/compare', {
      params: { keywords: keywords.join(','), days },
    });
    return data;
  },

  // 키워드 검색량 조회 (월간 실제 검색량)
  getVolume: async (keywords: string[]) => {
    const { data } = await api.get('/place/keyword-volume', {
      params: { keywords: keywords.join(',') },
    });
    return data;
  },

  // 연관 키워드 + 검색량 + 공략 가능성 조회
  getRelated: async (
    keyword: string,
    placeName = "",
    myVisitorReviews = 0,
    myBlogReviews = 0,
    limit = 10
  ) => {
    const { data } = await api.get('/place/related-keywords', {
      params: {
        keyword,
        place_name: placeName,
        my_visitor_reviews: myVisitorReviews,
        my_blog_reviews: myBlogReviews,
        limit
      },
    });
    return data;
  },

  // 요일별 패턴
  getWeeklyPattern: async (keyword: string) => {
    const { data } = await api.get('/place/keyword-trend/weekly-pattern', {
      params: { keyword },
    });
    return data;
  },

  // 시즌 트렌드
  getSeasonal: async (keyword: string, months = 12) => {
    const { data } = await api.get('/place/keyword-trend/seasonal', {
      params: { keyword, months },
    });
    return data;
  },
};

// 순위 요소 분석 API
export const rankingFactorsApi = {
  // 키워드별 순위 요소
  getFactors: async (keyword: string) => {
    const { data } = await api.get(`/place/ranking-factors/${keyword}`);
    return data;
  },

  // 히스토리
  getHistory: async (keyword: string, days = 30) => {
    const { data } = await api.get(`/place/ranking-factors/${keyword}/history`, {
      params: { days },
    });
    return data;
  },

  // 마케팅 추천
  getRecommendation: async (keyword: string) => {
    const { data } = await api.get(`/place/marketing-recommendation/${keyword}`);
    return data;
  },
};

// 리뷰 API
export const reviewApi = {
  // 방문자 리뷰
  getVisitorReviews: async (placeId: string, limit = 20) => {
    const { data } = await api.get(`/place/reviews/${placeId}/visitor`, {
      params: { limit },
    });
    return data;
  },

  // 블로그 리뷰
  getBlogReviews: async (placeId: string, limit = 20) => {
    const { data } = await api.get(`/place/reviews/${placeId}/blog`, {
      params: { limit },
    });
    return data;
  },

  // 전체 리뷰
  getAllReviews: async (placeId: string, visitorLimit = 20, blogLimit = 20) => {
    const { data } = await api.get(`/place/reviews/${placeId}/all`, {
      params: { visitor_limit: visitorLimit, blog_limit: blogLimit },
    });
    return data;
  },
};

// 히든 스코어 API
export const hiddenScoreApi = {
  // 히든 스코어 계산
  calculate: async (placeUrl: string, keyword: string) => {
    const { data } = await api.post('/place/hidden-score', {
      place_url: placeUrl,
      keyword,
    });
    return data;
  },

  // 배치 조회
  getBatch: async (keyword: string, limit = 30) => {
    const { data } = await api.get('/place/hidden-score/batch', {
      params: { keyword, limit },
    });
    return data;
  },

  // 비교
  compare: async (keyword: string, placeIds: string[]) => {
    const { data } = await api.get('/place/hidden-score/compare', {
      params: { keyword, place_ids: placeIds.join(',') },
    });
    return data;
  },
};

export const authApi = {
  // 회원가입
  register: async (email: string, password: string, name?: string) => {
    const { data } = await api.post('/auth/register', { email, password, name });
    return data;
  },

  // 로그인
  login: async (email: string, password: string) => {
    const { data } = await api.post('/auth/login', { email, password });
    if (data.access_token) {
      localStorage.setItem('token', data.access_token);
    }
    return data;
  },

  // 로그아웃
  logout: () => {
    localStorage.removeItem('token');
  },

  // 현재 사용자 정보
  getMe: async () => {
    const { data } = await api.get('/auth/me');
    return data;
  },
};

// ===========================================
// 분석 API (ADLOG 기반)
// ===========================================

export interface AnalyzeScores {
  quality_score: number;
  keyword_score: number;
  competition_score: number;
}

export interface AnalyzeMetrics {
  blog_count: number;
  visit_count: number;
  save_count: number;
}

export interface AnalyzeChanges {
  rank_change: number;
  score_change: number;
}

export interface AnalyzePlace {
  place_id: string;
  name: string;
  rank: number;
  scores: AnalyzeScores;
  metrics: AnalyzeMetrics;
  changes: AnalyzeChanges;
}

export interface AnalyzeRecommendation {
  type: string;
  amount: number;
  unit: string;
  effect: number;
  description?: string;  // N3 상승 효과 설명
  n3_effect?: number;    // 예상 N3 점수 증가
}

export interface AnalyzeCompetitor {
  rank: number;
  name: string;
  score: number;
}

export interface AnalyzeResponse {
  keyword: string;
  my_place: AnalyzePlace | null;
  comparison: {
    rank_1_gap: number;
    rank_1_score: number;
  } | null;
  recommendations: AnalyzeRecommendation[];
  competitors: AnalyzeCompetitor[];
  all_places: AnalyzePlace[];
  data_source?: 'api' | 'cache';  // api: ADLOG API, cache: 네이버 크롤링 + 자체 계산
}

export interface SimulateInputs {
  inflow: number;
  blog_review: number;
  visit_review: number;
}

// 목표 순위 시뮬레이션 타입
export interface TargetRankScoreChange {
  current: number;
  target: number;
  change: number;
}

export interface TargetRankRequest {
  keyword: string;
  place_name: string;
  current_rank: number;
  target_rank: number;
}

export interface TargetRankResponse {
  keyword: string;
  place_name: string;
  current_rank: number;
  target_rank: number;
  n2_change: TargetRankScoreChange;
  n3_change: TargetRankScoreChange;
  message: string;
  is_achievable: boolean;
  data_source: string;
}

export interface SimulateEffect {
  amount: number;
  effect: number;
}

export interface SimulateResponse {
  current_score: number;  // 현재 N2
  current_rank: number;
  effects: {
    inflow?: SimulateEffect;
    blog_review?: SimulateEffect;
    visit_review?: SimulateEffect;
  };
  total_effect: number;  // N2 변화량
  predicted_score: number;  // 예상 N2
  predicted_rank: number;
  // N3 관련 필드 (순위 결정 핵심 지표)
  current_n3?: number;  // 현재 경쟁력점수 (N3)
  predicted_n3?: number;  // 예상 경쟁력점수 (N3)
  n3_change?: number;  // N3 변화량
}

export const analyzeApi = {
  // 키워드 분석
  analyze: async (
    keyword: string,
    placeName?: string,
    inflow?: number
  ): Promise<AnalyzeResponse> => {
    const { data } = await api.post('/v1/analyze', {
      keyword,
      place_name: placeName,
      inflow,
    });
    return data;
  },

  // 시뮬레이션
  simulate: async (
    keyword: string,
    placeName: string,
    inputs: SimulateInputs
  ): Promise<SimulateResponse> => {
    const { data } = await api.post('/v1/simulate', {
      keyword,
      place_name: placeName,
      inputs,
    });
    return data;
  },

  // 목표 순위 시뮬레이션
  simulateTargetRank: async (
    keyword: string,
    placeName: string,
    currentRank: number,
    targetRank: number
  ): Promise<TargetRankResponse> => {
    const { data } = await api.post('/v1/simulate/target-rank', {
      keyword,
      place_name: placeName,
      current_rank: currentRank,
      target_rank: targetRank,
    });
    return data;
  },
};

// ===========================================
// 사용자 데이터 API
// ===========================================

export interface SubmitDataRequest {
  keyword: string;
  place_id: string;
  place_name?: string;
  inflow: number;
}

export interface SubmitDataResponse {
  success: boolean;
  data_id: number;
  keyword: string;
  place_id: string;
  place_name?: string;
  inflow: number;
  n2?: number;
  rank?: number;
  created_at: string;
}

export interface CorrelationResult {
  variable1: string;
  variable2: string;
  correlation: number;
  p_value: number;
  is_significant: boolean;
  sample_size: number;
}

export interface CorrelationResponse {
  inflow_n2: CorrelationResult;
  inflow_rank: CorrelationResult;
  total_samples: number;
  analysis_date: string;
  interpretation: string;
}

export interface UserInputDataItem {
  id: number;
  keyword: string;
  place_id: string;
  place_name?: string;
  inflow: number;
  n1?: number;
  n2?: number;
  n3?: number;
  rank?: number;
  visitor_review_count: number;
  blog_review_count: number;
  save_count: number;
  created_at: string;
}

export const userDataApi = {
  // 사용자 데이터 제출
  submit: async (request: SubmitDataRequest): Promise<SubmitDataResponse> => {
    const { data } = await api.post('/v1/submit-data', request);
    return data;
  },

  // 상관관계 분석
  getCorrelation: async (keyword?: string): Promise<CorrelationResponse> => {
    const { data } = await api.get('/v1/correlation', {
      params: keyword ? { keyword } : {},
    });
    return data;
  },

  // 저장된 사용자 데이터 조회
  getData: async (
    keyword?: string,
    placeId?: string,
    limit = 100
  ): Promise<{ total: number; data: UserInputDataItem[] }> => {
    const { data } = await api.get('/v1/user-data', {
      params: { keyword, place_id: placeId, limit },
    });
    return data;
  },
};

// ===========================================
// 활동 로그 API
// ===========================================

export interface ActivityLogRequest {
  keyword: string;
  place_id?: string;
  place_name?: string;
  activity_date?: string;  // YYYY-MM-DD
  blog_review_added: number;
  visit_review_added: number;
  save_added: number;
  inflow_added: number;
}

export interface ActivityLogResponse {
  success: boolean;
  log_id: number;
  keyword: string;
  place_name?: string;
  activity_date: string;
  blog_review_added: number;
  visit_review_added: number;
  save_added: number;
  inflow_added: number;
  rank_before?: number;
  n3_before?: number;
  created_at: string;
}

export interface ActivityHistoryItem {
  id: number;
  keyword: string;
  place_name?: string;
  activity_date: string;
  blog_review_added: number;
  visit_review_added: number;
  save_added: number;
  inflow_added: number;
  rank_before?: number;
  n3_before?: number;
  rank_after_1d?: number;
  n3_after_1d?: number;
  rank_after_7d?: number;
  n3_after_7d?: number;
  rank_change_1d?: number;
  rank_change_7d?: number;
  created_at: string;
}

export interface ActivityHistoryResponse {
  total: number;
  data: ActivityHistoryItem[];
}

export interface EffectByActivity {
  activity_type: string;
  total_added: number;
  sample_count: number;
  avg_rank_change_1d?: number;
  avg_rank_change_7d?: number;
  avg_n3_change_1d?: number;
  avg_n3_change_7d?: number;
}

export interface EffectAnalysisResponse {
  total_logs: number;
  logs_with_result: number;
  effects: EffectByActivity[];
  interpretation: string;
  analysis_date: string;
}

export const activityApi = {
  // 활동 기록
  log: async (request: ActivityLogRequest): Promise<ActivityLogResponse> => {
    const { data } = await api.post('/v1/activity/log', request);
    return data;
  },

  // 활동 히스토리 조회
  getHistory: async (
    keyword?: string,
    placeId?: string,
    days = 30,
    limit = 100
  ): Promise<ActivityHistoryResponse> => {
    const { data } = await api.get('/v1/activity/history', {
      params: { keyword, place_id: placeId, days, limit },
    });
    return data;
  },

  // 효과 분석
  getEffectAnalysis: async (
    keyword?: string,
    days = 90
  ): Promise<EffectAnalysisResponse> => {
    const { data } = await api.get('/v1/activity/effect-analysis', {
      params: { keyword, days },
    });
    return data;
  },

  // 결과 업데이트 (배치)
  updateResults: async (): Promise<{ success: boolean; updated_count: number }> => {
    const { data } = await api.post('/v1/activity/update-results');
    return data;
  },
};

export default api;
