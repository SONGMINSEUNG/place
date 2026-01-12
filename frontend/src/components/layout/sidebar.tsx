"use client";

import { useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  LayoutDashboard,
  Search,
  TrendingUp,
  // FileText,  // TODO: reports 페이지 구현 후 사용
  // Settings,  // TODO: settings 페이지 구현 후 사용
  LogOut,
  BarChart2,
  User,
  Menu,
  X,
} from "lucide-react";
import { useAuth } from "@/contexts/AuthContext";

const menuItems = [
  { href: "/", label: "대시보드", icon: LayoutDashboard },
  { href: "/inquiry", label: "순위 조회", icon: Search },
  { href: "/tracking", label: "순위 추적", icon: TrendingUp },
  // TODO: 아래 라우트들은 페이지 구현 후 활성화
  // { href: "/reports", label: "리포트", icon: FileText },
  // { href: "/settings", label: "설정", icon: Settings },
];

export function Sidebar() {
  const pathname = usePathname();

  // 로그인 페이지에서는 사이드바 숨김
  if (pathname === "/login") {
    return null;
  }

  return <SidebarContent />;
}

function SidebarContent() {
  const pathname = usePathname();
  const { user, logout } = useAuth();
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

  const getMembershipLabel = (type: string) => {
    const labels: Record<string, string> = {
      free: "무료",
      basic: "Basic",
      pro: "Pro",
      enterprise: "Enterprise"
    };
    return labels[type] || type;
  };

  const handleNavClick = () => {
    setMobileMenuOpen(false);
  };

  return (
    <>
      {/* 모바일 햄버거 버튼 */}
      <button
        onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
        className="mobile-menu-btn"
        style={{
          display: 'none',
          position: 'fixed',
          top: '16px',
          left: '16px',
          zIndex: 60,
          padding: '10px',
          borderRadius: '12px',
          border: '1px solid #e2e8f0',
          background: 'white',
          cursor: 'pointer',
          boxShadow: '0 2px 8px rgba(0,0,0,0.1)'
        }}
      >
        {mobileMenuOpen ? (
          <X style={{ width: '24px', height: '24px', color: '#64748b' }} />
        ) : (
          <Menu style={{ width: '24px', height: '24px', color: '#64748b' }} />
        )}
      </button>

      {/* 모바일 오버레이 */}
      {mobileMenuOpen && (
        <div
          onClick={() => setMobileMenuOpen(false)}
          style={{
            position: 'fixed',
            inset: 0,
            background: 'rgba(0,0,0,0.3)',
            zIndex: 45,
            display: 'none'
          }}
          className="mobile-overlay"
        />
      )}

      {/* 사이드바 */}
      <aside
        className={`sidebar-container ${mobileMenuOpen ? 'open' : ''}`}
        style={{
          position: 'fixed',
          left: 0,
          top: 0,
          bottom: 0,
          width: '256px',
          background: 'white',
          borderRight: '1px solid #e2e8f0',
          padding: '24px',
          display: 'flex',
          flexDirection: 'column',
          zIndex: 50,
          transition: 'transform 0.3s ease'
        }}
      >
        {/* Logo */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px', padding: '0 12px', marginBottom: '32px' }}>
          <div style={{
            width: '36px',
            height: '36px',
            borderRadius: '12px',
            background: 'linear-gradient(135deg, #6366f1, #8b5cf6)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center'
          }}>
            <BarChart2 style={{ width: '20px', height: '20px', color: 'white' }} />
          </div>
          <span style={{ fontSize: '18px', fontWeight: 'bold', color: '#1e293b' }}>PlaceRank</span>
        </div>

        {/* User Info */}
        {user && (
          <div style={{
            padding: '12px',
            marginBottom: '16px',
            borderRadius: '12px',
            background: '#f8fafc'
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
              <div style={{
                width: '40px',
                height: '40px',
                borderRadius: '50%',
                background: 'linear-gradient(135deg, #f472b6, #a855f7)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center'
              }}>
                <User style={{ width: '20px', height: '20px', color: 'white' }} />
              </div>
              <div style={{ flex: 1, minWidth: 0 }}>
                <p style={{ fontSize: '14px', fontWeight: '600', color: '#1e293b', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                  {user.name || user.email.split('@')[0]}
                </p>
                <p style={{ fontSize: '12px', color: '#64748b' }}>{getMembershipLabel(user.membership_type)} 플랜</p>
              </div>
            </div>
            <div style={{ marginTop: '8px', paddingTop: '8px', borderTop: '1px solid #e2e8f0' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '12px' }}>
                <span style={{ color: '#64748b' }}>오늘 조회</span>
                <span style={{ fontWeight: '500', color: '#475569' }}>{user.daily_search_count} / {user.daily_limit}</span>
              </div>
              <div style={{ marginTop: '4px', height: '6px', background: '#e2e8f0', borderRadius: '3px', overflow: 'hidden' }}>
                <div
                  style={{
                    height: '100%',
                    background: 'linear-gradient(90deg, #6366f1, #8b5cf6)',
                    borderRadius: '3px',
                    width: `${(user.daily_search_count / user.daily_limit) * 100}%`,
                    transition: 'width 0.3s ease'
                  }}
                />
              </div>
            </div>
          </div>
        )}

        {/* Navigation */}
        <nav style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: '4px' }}>
          {menuItems.map((item) => {
            const Icon = item.icon;
            const isActive = pathname === item.href;
            return (
              <Link key={item.href} href={item.href} onClick={handleNavClick}>
                <div
                  className="menu-item"
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: '12px',
                    padding: '12px 16px',
                    borderRadius: '12px',
                    cursor: 'pointer',
                    transition: 'all 0.2s ease',
                    background: isActive ? 'linear-gradient(135deg, #6366f1, #8b5cf6)' : 'transparent',
                    color: isActive ? 'white' : '#64748b',
                    fontWeight: isActive ? '600' : '500',
                    fontSize: '14px',
                    boxShadow: isActive ? '0 4px 12px rgba(99, 102, 241, 0.3)' : 'none'
                  }}
                >
                  <Icon style={{ width: '20px', height: '20px', color: isActive ? 'white' : '#94a3b8' }} />
                  <span>{item.label}</span>
                </div>
              </Link>
            );
          })}
        </nav>

        {/* Upgrade Card - 무료 회원만 표시 */}
        {user?.membership_type === 'free' && (
          <div style={{
            marginTop: '16px',
            padding: '16px',
            borderRadius: '16px',
            background: 'linear-gradient(135deg, #fef3c7, #fde68a)',
            position: 'relative',
            overflow: 'hidden'
          }}>
            <div style={{
              position: 'absolute',
              right: '-16px',
              bottom: '-16px',
              width: '80px',
              height: '80px',
              opacity: 0.3
            }}>
              <svg viewBox="0 0 100 100" style={{ width: '100%', height: '100%' }}>
                <path d="M50 10 L90 90 L10 90 Z" fill="#fbbf24" opacity="0.5" />
              </svg>
            </div>
            <p style={{ fontSize: '14px', fontWeight: '600', color: '#92400e', marginBottom: '4px' }}>Pro 플랜으로</p>
            <p style={{ fontSize: '12px', color: '#a16207', marginBottom: '12px' }}>하루 200회 조회!</p>
            <button style={{
              fontSize: '12px',
              fontWeight: '600',
              color: '#6366f1',
              background: 'none',
              border: 'none',
              cursor: 'pointer',
              padding: 0
            }}>
              업그레이드 →
            </button>
          </div>
        )}

        {/* Logout */}
        <div style={{ marginTop: '16px', paddingTop: '16px', borderTop: '1px solid #f1f5f9' }}>
          <button
            onClick={() => { logout(); handleNavClick(); }}
            className="menu-item"
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '12px',
              padding: '12px 16px',
              borderRadius: '12px',
              width: '100%',
              background: 'transparent',
              border: 'none',
              cursor: 'pointer',
              color: '#64748b',
              fontSize: '14px',
              fontWeight: '500',
              transition: 'all 0.2s ease'
            }}
          >
            <LogOut style={{ width: '20px', height: '20px' }} />
            <span>로그아웃</span>
          </button>
        </div>
      </aside>

      {/* 반응형 스타일 */}
      <style>{`
        .menu-item:hover {
          background: rgba(99, 102, 241, 0.08) !important;
          color: #4f46e5 !important;
        }

        .menu-item:hover svg {
          color: #4f46e5 !important;
        }

        @media (max-width: 1024px) {
          .mobile-menu-btn {
            display: flex !important;
          }

          .mobile-overlay {
            display: block !important;
          }

          .sidebar-container {
            transform: translateX(-100%);
          }

          .sidebar-container.open {
            transform: translateX(0);
          }
        }
      `}</style>
    </>
  );
}
