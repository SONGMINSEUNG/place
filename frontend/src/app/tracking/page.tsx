"use client";

import React, { useState, useEffect, useCallback } from "react";
import { Loader2, RefreshCw, Plus, Trash2, TrendingUp, TrendingDown, Minus, X, Search, Bell, ChevronDown, ChevronUp, Users, FileText } from "lucide-react";
import { toast } from "sonner";
import { keywordsApi, SavedKeyword, DailyData } from "@/lib/api";
import { useAuth } from "@/contexts/AuthContext";

const cardStyle: React.CSSProperties = { background: 'white', borderRadius: '16px', padding: '24px', border: '1px solid #e2e8f0' };
const inputStyle: React.CSSProperties = { width: '100%', padding: '12px 16px', borderRadius: '12px', border: '1px solid #e2e8f0', fontSize: '14px', background: 'white' };
const btnPrimary: React.CSSProperties = { background: 'linear-gradient(135deg, #6366f1, #8b5cf6)', color: 'white', padding: '10px 20px', borderRadius: '12px', fontWeight: '600', fontSize: '14px', border: 'none', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '8px' };
const btnSecondary: React.CSSProperties = { background: 'white', color: '#64748b', padding: '10px 20px', borderRadius: '12px', fontWeight: '500', fontSize: '14px', border: '1px solid #e2e8f0', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '8px' };

export default function TrackingPage() {
  const { user } = useAuth();
  const [keywords, setKeywords] = useState<SavedKeyword[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [addDialogOpen, setAddDialogOpen] = useState(false);
  const [newPlaceUrl, setNewPlaceUrl] = useState("");
  const [newPlaceName, setNewPlaceName] = useState("");
  const [newKeyword, setNewKeyword] = useState("");
  const [addLoading, setAddLoading] = useState(false);
  const [expandedKeyword, setExpandedKeyword] = useState<number | null>(null);
  const [searchQuery, setSearchQuery] = useState("");
  const [autoRefreshed, setAutoRefreshed] = useState(false);

  const loadKeywords = useCallback(async () => {
    try {
      const data = await keywordsApi.getAll();
      setKeywords(data);
    } catch (error: any) {
      if (error.response?.status === 401) toast.error("로그인이 필요합니다");
      else toast.error("키워드 목록을 불러오는데 실패했습니다");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadKeywords();
  }, [loadKeywords]);

  useEffect(() => {
    if (user && !autoRefreshed && keywords.length > 0 && !loading) {
      const shouldRefresh = keywords.some(kw => {
        if (!kw.weekly_data || kw.weekly_data.length === 0) return true;
        const lastUpdate = new Date(kw.weekly_data[kw.weekly_data.length - 1]?.date);
        const hoursSinceUpdate = (Date.now() - lastUpdate.getTime()) / (1000 * 60 * 60);
        return hoursSinceUpdate > 1;
      });

      if (shouldRefresh) {
        handleRefreshAll(true);
        setAutoRefreshed(true);
      }
    }
  }, [user, keywords, loading, autoRefreshed]);

  const handleAddKeyword = async () => {
    if (!newPlaceUrl.trim() || !newKeyword.trim()) {
      toast.error("플레이스 URL과 키워드를 입력해주세요");
      return;
    }
    setAddLoading(true);
    try {
      const saved = await keywordsApi.save(newPlaceUrl, newKeyword, newPlaceName);
      setKeywords([saved, ...keywords]);
      setAddDialogOpen(false);
      setNewPlaceUrl(""); setNewPlaceName(""); setNewKeyword("");
      toast.success("키워드가 추가되었습니다");
    } catch (error: any) {
      toast.error(error.response?.data?.detail || "키워드 추가에 실패했습니다");
    } finally {
      setAddLoading(false);
    }
  };

  const handleRefresh = async (keywordId: number) => {
    try {
      const result = await keywordsApi.refresh(keywordId);
      await loadKeywords();
      toast.success(result.rank_change ? `순위가 ${Math.abs(result.rank_change)}${result.rank_change > 0 ? "위 상승" : "위 하락"}했습니다` : "순위가 업데이트되었습니다");
    } catch { toast.error("순위 업데이트에 실패했습니다"); }
  };

  const handleRefreshAll = async (silent = false) => {
    setRefreshing(true);
    try {
      const result = await keywordsApi.refreshAll();
      await loadKeywords();
      if (!silent) {
        toast.success(`${result.updated}개 키워드의 순위가 업데이트되었습니다`);
      }
    } catch {
      if (!silent) toast.error("전체 업데이트에 실패했습니다");
    }
    finally { setRefreshing(false); }
  };

  const handleDelete = async (keywordId: number) => {
    if (!confirm("정말 삭제하시겠습니까?")) return;
    try {
      await keywordsApi.delete(keywordId);
      setKeywords(keywords.filter((kw) => kw.id !== keywordId));
      toast.success("키워드가 삭제되었습니다");
    } catch { toast.error("삭제에 실패했습니다"); }
  };

  const getRankBadge = (rank: number | null | undefined) => {
    if (!rank) return { background: '#f1f5f9', color: '#64748b' };
    if (rank <= 3) return { background: 'linear-gradient(135deg, #fbbf24, #f59e0b)', color: 'white' };
    if (rank <= 10) return { background: '#dcfce7', color: '#16a34a' };
    if (rank <= 20) return { background: '#dbeafe', color: '#2563eb' };
    return { background: '#f1f5f9', color: '#64748b' };
  };

  const getRankChange = (weeklyData: DailyData[]) => {
    if (!weeklyData || weeklyData.length < 2) return null;
    const today = weeklyData[weeklyData.length - 1];
    const yesterday = weeklyData[weeklyData.length - 2];
    if (!today?.rank || !yesterday?.rank) return null;
    return yesterday.rank - today.rank;
  };

  const formatDate = (dateStr: string) => {
    const parts = dateStr.split('/');
    if (parts.length === 2) {
      return `${parts[0]}/${parts[1]}`;
    }
    const date = new Date(dateStr);
    return `${date.getMonth() + 1}/${date.getDate()}`;
  };

  const stats = {
    total: keywords.length,
    top3: keywords.filter(k => k.last_rank && k.last_rank <= 3).length,
    top10: keywords.filter(k => k.last_rank && k.last_rank <= 10).length,
    avgRank: keywords.length > 0 ? (keywords.reduce((sum, k) => sum + (k.last_rank || 100), 0) / keywords.length).toFixed(1) : '-'
  };

  const filteredKeywords = keywords.filter(kw =>
    !searchQuery ||
    kw.keyword.toLowerCase().includes(searchQuery.toLowerCase()) ||
    (kw.place_name && kw.place_name.toLowerCase().includes(searchQuery.toLowerCase()))
  );

  return (
    <div>
      {/* Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '32px' }}>
        <div>
          <h1 style={{ fontSize: '24px', fontWeight: 'bold', color: '#1e293b' }}>순위 추적</h1>
          <p style={{ fontSize: '14px', color: '#64748b', marginTop: '4px' }}>키워드별 순위 변동을 추적하세요</p>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          <div style={{ position: 'relative' }}>
            <Search style={{ position: 'absolute', left: '16px', top: '50%', transform: 'translateY(-50%)', width: '16px', height: '16px', color: '#94a3b8' }} />
            <input
              type="text"
              placeholder="키워드/업체명 검색..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              style={{ ...inputStyle, paddingLeft: '44px', width: '240px' }}
            />
          </div>
          <button style={{ padding: '10px', borderRadius: '12px', border: '1px solid #e2e8f0', background: 'white' }}>
            <Bell style={{ width: '20px', height: '20px', color: '#64748b' }} />
          </button>
        </div>
      </div>

      {/* KPI Cards */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '24px', marginBottom: '32px' }}>
        <div style={cardStyle}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
            <span style={{ fontSize: '14px', color: '#64748b' }}>추적 키워드</span>
            <span style={{ padding: '4px 8px', borderRadius: '12px', fontSize: '12px', fontWeight: '500', background: '#dbeafe', color: '#2563eb' }}>활성</span>
          </div>
          <div style={{ display: 'flex', alignItems: 'baseline', gap: '8px' }}>
            <span style={{ fontSize: '30px', fontWeight: 'bold', color: '#1e293b' }}>{stats.total}</span>
            <span style={{ fontSize: '14px', color: '#94a3b8' }}>개</span>
          </div>
        </div>

        <div style={cardStyle}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
            <span style={{ fontSize: '14px', color: '#64748b' }}>TOP 3</span>
            <span style={{ padding: '4px 8px', borderRadius: '12px', fontSize: '12px', fontWeight: '500', background: '#fef3c7', color: '#d97706' }}>최고</span>
          </div>
          <div style={{ display: 'flex', alignItems: 'baseline', gap: '8px' }}>
            <span style={{ fontSize: '30px', fontWeight: 'bold', color: '#1e293b' }}>{stats.top3}</span>
            <span style={{ fontSize: '14px', color: '#94a3b8' }}>개</span>
          </div>
        </div>

        <div style={cardStyle}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
            <span style={{ fontSize: '14px', color: '#64748b' }}>TOP 10</span>
            <span style={{ padding: '4px 8px', borderRadius: '12px', fontSize: '12px', fontWeight: '500', background: '#dcfce7', color: '#16a34a' }}>양호</span>
          </div>
          <div style={{ display: 'flex', alignItems: 'baseline', gap: '8px' }}>
            <span style={{ fontSize: '30px', fontWeight: 'bold', color: '#1e293b' }}>{stats.top10}</span>
            <span style={{ fontSize: '14px', color: '#94a3b8' }}>개</span>
          </div>
        </div>

        <div style={cardStyle}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
            <span style={{ fontSize: '14px', color: '#64748b' }}>평균 순위</span>
            <span style={{ padding: '4px 8px', borderRadius: '12px', fontSize: '12px', fontWeight: '500', background: '#f3e8ff', color: '#9333ea' }}>평균</span>
          </div>
          <div style={{ display: 'flex', alignItems: 'baseline', gap: '8px' }}>
            <span style={{ fontSize: '30px', fontWeight: 'bold', color: '#1e293b' }}>{stats.avgRank}</span>
            <span style={{ fontSize: '14px', color: '#94a3b8' }}>위</span>
          </div>
        </div>
      </div>

      {/* Keywords Table */}
      <div style={cardStyle}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '24px' }}>
          <h2 style={{ fontSize: '18px', fontWeight: '600', color: '#1e293b' }}>키워드 목록</h2>
          <div style={{ display: 'flex', gap: '12px' }}>
            <button onClick={() => handleRefreshAll(false)} disabled={refreshing} style={btnSecondary}>
              {refreshing ? <Loader2 style={{ width: '16px', height: '16px', animation: 'spin 1s linear infinite' }} /> : <RefreshCw style={{ width: '16px', height: '16px' }} />}
              전체 새로고침
            </button>
            <button onClick={() => setAddDialogOpen(true)} style={btnPrimary}>
              <Plus style={{ width: '16px', height: '16px' }} />
              키워드 추가
            </button>
          </div>
        </div>

        {loading ? (
          <div style={{ display: 'flex', justifyContent: 'center', padding: '64px 0' }}>
            <Loader2 style={{ width: '32px', height: '32px', color: '#6366f1', animation: 'spin 1s linear infinite' }} />
          </div>
        ) : filteredKeywords.length > 0 ? (
          <div style={{ overflowX: 'auto' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', minWidth: '900px' }}>
              <thead>
                <tr style={{ borderBottom: '2px solid #e2e8f0', background: '#f8fafc' }}>
                  <th style={{ padding: '14px 16px', textAlign: 'left', fontSize: '13px', fontWeight: '600', color: '#475569' }}>업체 / 키워드</th>
                  <th style={{ padding: '14px 12px', textAlign: 'center', fontSize: '13px', fontWeight: '600', color: '#475569', width: '100px' }}>현재 순위</th>
                  <th style={{ padding: '14px 12px', textAlign: 'center', fontSize: '13px', fontWeight: '600', color: '#475569', width: '90px' }}>변동</th>
                  <th style={{ padding: '14px 12px', textAlign: 'center', fontSize: '13px', fontWeight: '600', color: '#475569', width: '100px' }}>
                    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '4px' }}>
                      <Users style={{ width: '14px', height: '14px' }} />
                      방문자
                    </div>
                  </th>
                  <th style={{ padding: '14px 12px', textAlign: 'center', fontSize: '13px', fontWeight: '600', color: '#475569', width: '100px' }}>
                    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '4px' }}>
                      <FileText style={{ width: '14px', height: '14px' }} />
                      블로그
                    </div>
                  </th>
                  <th style={{ padding: '14px 12px', textAlign: 'center', fontSize: '13px', fontWeight: '600', color: '#475569', width: '80px' }}>최고</th>
                  <th style={{ padding: '14px 12px', textAlign: 'center', fontSize: '13px', fontWeight: '600', color: '#475569', width: '100px' }}>관리</th>
                </tr>
              </thead>
              <tbody>
                {filteredKeywords.map((kw) => {
                  const rankChange = getRankChange(kw.weekly_data);
                  const isExpanded = expandedKeyword === kw.id;

                  return (
                    <React.Fragment key={kw.id}>
                      <tr
                        style={{
                          borderBottom: isExpanded ? 'none' : '1px solid #e2e8f0',
                          background: isExpanded ? '#f8fafc' : 'white',
                          cursor: 'pointer',
                          transition: 'background 0.15s'
                        }}
                        onClick={() => setExpandedKeyword(isExpanded ? null : kw.id)}
                        onMouseOver={(e) => { if (!isExpanded) e.currentTarget.style.background = '#fafafa'; }}
                        onMouseOut={(e) => { if (!isExpanded) e.currentTarget.style.background = 'white'; }}
                      >
                        <td style={{ padding: '16px' }}>
                          <div style={{ fontWeight: '600', color: '#1e293b', marginBottom: '2px' }}>{kw.place_name || kw.place_id}</div>
                          <div style={{ fontSize: '13px', color: '#6366f1', fontWeight: '500' }}>{kw.keyword}</div>
                        </td>
                        <td style={{ padding: '12px', textAlign: 'center' }}>
                          <span style={{ ...getRankBadge(kw.last_rank), padding: '6px 14px', borderRadius: '12px', fontSize: '14px', fontWeight: '600' }}>
                            {kw.last_rank ? `${kw.last_rank}위` : '-'}
                          </span>
                        </td>
                        <td style={{ padding: '12px', textAlign: 'center' }}>
                          {rankChange !== null ? (
                            <span style={{
                              display: 'inline-flex', alignItems: 'center', gap: '3px',
                              padding: '4px 10px', borderRadius: '8px', fontSize: '13px', fontWeight: '600',
                              background: rankChange > 0 ? '#dcfce7' : rankChange < 0 ? '#fee2e2' : '#f1f5f9',
                              color: rankChange > 0 ? '#16a34a' : rankChange < 0 ? '#dc2626' : '#64748b'
                            }}>
                              {rankChange > 0 ? <TrendingUp style={{ width: '14px', height: '14px' }} /> :
                               rankChange < 0 ? <TrendingDown style={{ width: '14px', height: '14px' }} /> :
                               <Minus style={{ width: '14px', height: '14px' }} />}
                              {rankChange > 0 ? `+${rankChange}` : rankChange < 0 ? rankChange : '-'}
                            </span>
                          ) : (
                            <span style={{ fontSize: '13px', color: '#94a3b8' }}>-</span>
                          )}
                        </td>
                        <td style={{ padding: '12px', textAlign: 'center' }}>
                          <span style={{ fontSize: '14px', fontWeight: '600', color: '#1e293b' }}>
                            {(kw.visitor_review_count || 0).toLocaleString()}
                          </span>
                        </td>
                        <td style={{ padding: '12px', textAlign: 'center' }}>
                          <span style={{ fontSize: '14px', fontWeight: '600', color: '#1e293b' }}>
                            {(kw.blog_review_count || 0).toLocaleString()}
                          </span>
                        </td>
                        <td style={{ padding: '12px', textAlign: 'center' }}>
                          <span style={{ fontSize: '13px', color: '#64748b' }}>
                            {kw.best_rank ? `${kw.best_rank}위` : '-'}
                          </span>
                        </td>
                        <td style={{ padding: '12px', textAlign: 'center' }}>
                          <div style={{ display: 'flex', gap: '4px', justifyContent: 'center', alignItems: 'center' }}>
                            <button
                              onClick={(e) => { e.stopPropagation(); handleRefresh(kw.id); }}
                              style={{ padding: '8px', borderRadius: '8px', background: 'transparent', border: 'none', cursor: 'pointer', color: '#6366f1' }}
                              title="새로고침"
                            >
                              <RefreshCw style={{ width: '16px', height: '16px' }} />
                            </button>
                            <button
                              onClick={(e) => { e.stopPropagation(); handleDelete(kw.id); }}
                              style={{ padding: '8px', borderRadius: '8px', background: 'transparent', border: 'none', cursor: 'pointer', color: '#dc2626' }}
                              title="삭제"
                            >
                              <Trash2 style={{ width: '16px', height: '16px' }} />
                            </button>
                            {isExpanded ?
                              <ChevronUp style={{ width: '18px', height: '18px', color: '#6366f1' }} /> :
                              <ChevronDown style={{ width: '18px', height: '18px', color: '#94a3b8' }} />
                            }
                          </div>
                        </td>
                      </tr>

                      {/* 확장된 상세 정보 - 7일 순위 기록 */}
                      {isExpanded && (
                        <tr>
                          <td colSpan={7} style={{ padding: 0 }}>
                            <div style={{ padding: '20px 24px', background: '#f8fafc', borderBottom: '1px solid #e2e8f0' }}>
                              <h4 style={{ fontSize: '14px', fontWeight: '600', color: '#1e293b', marginBottom: '16px' }}>
                                📊 일별 기록 (최근 7일)
                              </h4>

                              {kw.weekly_data && kw.weekly_data.length > 0 ? (
                                <div style={{ background: 'white', borderRadius: '12px', border: '1px solid #e2e8f0', overflow: 'hidden' }}>
                                  <table style={{ width: '100%', borderCollapse: 'collapse' }}>
                                    <thead>
                                      <tr style={{ background: '#f1f5f9' }}>
                                        <th style={{ padding: '12px 16px', textAlign: 'center', fontSize: '12px', fontWeight: '600', color: '#64748b', borderBottom: '1px solid #e2e8f0' }}>날짜</th>
                                        <th style={{ padding: '12px 16px', textAlign: 'center', fontSize: '12px', fontWeight: '600', color: '#64748b', borderBottom: '1px solid #e2e8f0' }}>순위</th>
                                        <th style={{ padding: '12px 16px', textAlign: 'center', fontSize: '12px', fontWeight: '600', color: '#64748b', borderBottom: '1px solid #e2e8f0' }}>변동</th>
                                        <th style={{ padding: '12px 16px', textAlign: 'center', fontSize: '12px', fontWeight: '600', color: '#64748b', borderBottom: '1px solid #e2e8f0' }}>방문자 리뷰</th>
                                        <th style={{ padding: '12px 16px', textAlign: 'center', fontSize: '12px', fontWeight: '600', color: '#64748b', borderBottom: '1px solid #e2e8f0' }}>블로그 리뷰</th>
                                      </tr>
                                    </thead>
                                    <tbody>
                                      {kw.weekly_data.slice(-7).reverse().map((day, idx, arr) => {
                                        const prevDay = arr[idx + 1];
                                        const rankChange = prevDay && day.rank && prevDay.rank ? prevDay.rank - day.rank : null;
                                        const visitorChange = prevDay && day.visitor_review_count && prevDay.visitor_review_count ? day.visitor_review_count - prevDay.visitor_review_count : null;
                                        const blogChange = prevDay && day.blog_review_count && prevDay.blog_review_count ? day.blog_review_count - prevDay.blog_review_count : null;

                                        return (
                                          <tr key={idx} style={{ borderBottom: idx === arr.length - 1 ? 'none' : '1px solid #f1f5f9' }}>
                                            <td style={{ padding: '14px 16px', textAlign: 'center', fontSize: '13px', color: '#1e293b', fontWeight: '500' }}>
                                              {formatDate(day.date)}
                                            </td>
                                            <td style={{ padding: '14px 16px', textAlign: 'center' }}>
                                              <span style={{
                                                ...getRankBadge(day.rank),
                                                padding: '4px 12px',
                                                borderRadius: '8px',
                                                fontSize: '13px',
                                                fontWeight: '600'
                                              }}>
                                                {day.rank ? `${day.rank}위` : '-'}
                                              </span>
                                            </td>
                                            <td style={{ padding: '14px 16px', textAlign: 'center' }}>
                                              {rankChange !== null ? (
                                                <span style={{
                                                  fontSize: '13px',
                                                  fontWeight: '600',
                                                  color: rankChange > 0 ? '#16a34a' : rankChange < 0 ? '#dc2626' : '#94a3b8'
                                                }}>
                                                  {rankChange > 0 ? `▲${rankChange}` : rankChange < 0 ? `▼${Math.abs(rankChange)}` : '-'}
                                                </span>
                                              ) : <span style={{ color: '#94a3b8' }}>-</span>}
                                            </td>
                                            <td style={{ padding: '14px 16px', textAlign: 'center' }}>
                                              <span style={{ fontSize: '13px', fontWeight: '600', color: '#1e293b' }}>
                                                {(day.visitor_review_count || 0).toLocaleString()}
                                              </span>
                                              {visitorChange !== null && visitorChange !== 0 && (
                                                <span style={{
                                                  marginLeft: '8px',
                                                  fontSize: '11px',
                                                  fontWeight: '600',
                                                  padding: '2px 6px',
                                                  borderRadius: '4px',
                                                  background: visitorChange > 0 ? '#dcfce7' : '#fee2e2',
                                                  color: visitorChange > 0 ? '#16a34a' : '#dc2626'
                                                }}>
                                                  {visitorChange > 0 ? `+${visitorChange}` : visitorChange}
                                                </span>
                                              )}
                                            </td>
                                            <td style={{ padding: '14px 16px', textAlign: 'center' }}>
                                              <span style={{ fontSize: '13px', fontWeight: '600', color: '#1e293b' }}>
                                                {(day.blog_review_count || 0).toLocaleString()}
                                              </span>
                                              {blogChange !== null && blogChange !== 0 && (
                                                <span style={{
                                                  marginLeft: '8px',
                                                  fontSize: '11px',
                                                  fontWeight: '600',
                                                  padding: '2px 6px',
                                                  borderRadius: '4px',
                                                  background: blogChange > 0 ? '#dcfce7' : '#fee2e2',
                                                  color: blogChange > 0 ? '#16a34a' : '#dc2626'
                                                }}>
                                                  {blogChange > 0 ? `+${blogChange}` : blogChange}
                                                </span>
                                              )}
                                            </td>
                                          </tr>
                                        );
                                      })}
                                    </tbody>
                                  </table>
                                </div>
                              ) : (
                                <div style={{ padding: '24px', textAlign: 'center', color: '#94a3b8', fontSize: '14px', background: 'white', borderRadius: '12px', border: '1px solid #e2e8f0' }}>
                                  기록이 없습니다. 새로고침을 눌러 첫 데이터를 기록하세요.
                                </div>
                              )}

                              {/* 등록일 정보 */}
                              <div style={{ marginTop: '12px', fontSize: '12px', color: '#94a3b8' }}>
                                등록일: {new Date(kw.created_at).toLocaleDateString('ko-KR')}
                              </div>
                            </div>
                          </td>
                        </tr>
                      )}
                    </React.Fragment>
                  );
                })}
              </tbody>
            </table>
          </div>
        ) : keywords.length > 0 ? (
          <div style={{ textAlign: 'center', padding: '40px 0', color: '#64748b' }}>
            검색 결과가 없습니다
          </div>
        ) : (
          <div style={{ textAlign: 'center', padding: '64px 0' }}>
            <div style={{ width: '64px', height: '64px', borderRadius: '16px', background: 'linear-gradient(135deg, #eef2ff, #f3e8ff)', display: 'inline-flex', alignItems: 'center', justifyContent: 'center', marginBottom: '16px' }}>
              <TrendingUp style={{ width: '32px', height: '32px', color: '#6366f1' }} />
            </div>
            <p style={{ fontWeight: '500', color: '#475569' }}>저장된 키워드가 없습니다</p>
            <p style={{ fontSize: '14px', color: '#94a3b8', marginTop: '4px' }}>키워드를 추가하여 순위 변동을 추적하세요</p>
            <button onClick={() => setAddDialogOpen(true)} style={{ ...btnPrimary, marginTop: '16px', display: 'inline-flex' }}>
              <Plus style={{ width: '16px', height: '16px' }} />
              첫 키워드 추가하기
            </button>
          </div>
        )}
      </div>

      {/* Add Dialog */}
      {addDialogOpen && (
        <div style={{ position: 'fixed', inset: 0, zIndex: 50, display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '16px' }}>
          <div onClick={() => setAddDialogOpen(false)} style={{ position: 'absolute', inset: 0, background: 'rgba(0,0,0,0.3)', backdropFilter: 'blur(4px)' }} />
          <div style={{ position: 'relative', background: 'white', borderRadius: '24px', padding: '32px', width: '100%', maxWidth: '400px', boxShadow: '0 25px 50px -12px rgba(0,0,0,0.25)' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '24px' }}>
              <div>
                <h3 style={{ fontSize: '20px', fontWeight: 'bold', color: '#1e293b' }}>키워드 추가</h3>
                <p style={{ fontSize: '14px', color: '#64748b', marginTop: '4px' }}>추적할 플레이스와 키워드를 입력하세요</p>
              </div>
              <button onClick={() => setAddDialogOpen(false)} style={{ padding: '8px', borderRadius: '12px', background: 'transparent', border: 'none', cursor: 'pointer', color: '#94a3b8' }}>
                <X style={{ width: '20px', height: '20px' }} />
              </button>
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
              <div>
                <label style={{ fontSize: '14px', fontWeight: '500', color: '#374151', display: 'block', marginBottom: '8px' }}>플레이스 URL</label>
                <input type="text" placeholder="https://m.place.naver.com/restaurant/1234567890" value={newPlaceUrl} onChange={(e) => setNewPlaceUrl(e.target.value)} style={inputStyle} />
              </div>
              <div>
                <label style={{ fontSize: '14px', fontWeight: '500', color: '#374151', display: 'block', marginBottom: '8px' }}>업체명 <span style={{ color: '#94a3b8', fontWeight: '400' }}>(선택)</span></label>
                <input type="text" placeholder="업체명" value={newPlaceName} onChange={(e) => setNewPlaceName(e.target.value)} style={inputStyle} />
              </div>
              <div>
                <label style={{ fontSize: '14px', fontWeight: '500', color: '#374151', display: 'block', marginBottom: '8px' }}>키워드</label>
                <input type="text" placeholder="강남 맛집" value={newKeyword} onChange={(e) => setNewKeyword(e.target.value)} style={inputStyle} />
              </div>
              <button onClick={handleAddKeyword} disabled={addLoading} style={{ ...btnPrimary, width: '100%', justifyContent: 'center', marginTop: '8px' }}>
                {addLoading ? <Loader2 style={{ width: '16px', height: '16px', animation: 'spin 1s linear infinite' }} /> : <Plus style={{ width: '16px', height: '16px' }} />}
                추가하기
              </button>
            </div>
          </div>
        </div>
      )}

      <style>{`@keyframes spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }`}</style>
    </div>
  );
}
