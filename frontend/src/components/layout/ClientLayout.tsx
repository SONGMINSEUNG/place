"use client";

import { usePathname } from "next/navigation";
import { AuthProvider, useAuth } from "@/contexts/AuthContext";
import { Sidebar } from "./sidebar";

function ServerConnectingOverlay() {
  const { serverConnecting } = useAuth();

  if (!serverConnecting) return null;

  return (
    <div
      style={{
        position: 'fixed',
        top: 0,
        left: 0,
        right: 0,
        bottom: 0,
        background: 'rgba(255, 255, 255, 0.95)',
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        zIndex: 9999,
      }}
    >
      {/* 스피너 */}
      <div
        style={{
          width: 48,
          height: 48,
          border: '4px solid #e2e8f0',
          borderTop: '4px solid #8b5cf6',
          borderRadius: '50%',
          animation: 'spin 1s linear infinite',
          marginBottom: 24,
        }}
      />
      <p
        style={{
          fontSize: 18,
          fontWeight: 600,
          color: '#1e293b',
          margin: 0,
          marginBottom: 8,
        }}
      >
        서버에 연결 중입니다...
      </p>
      <p
        style={{
          fontSize: 14,
          color: '#94a3b8',
          margin: 0,
        }}
      >
        잠시만 기다려주세요
      </p>
      <style>{`
        @keyframes spin {
          0% { transform: rotate(0deg); }
          100% { transform: rotate(360deg); }
        }
      `}</style>
    </div>
  );
}

export function ClientLayout({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const isLoginPage = pathname === "/login";

  return (
    <AuthProvider>
      <ServerConnectingOverlay />
      <Sidebar />
      <main
        className={isLoginPage ? "" : "main-content"}
        style={{
          marginLeft: isLoginPage ? '0' : undefined,
          padding: isLoginPage ? '0' : '32px',
          minHeight: '100vh',
          background: 'linear-gradient(135deg, #fdf2f8 0%, #f3e8ff 50%, #dbeafe 100%)'
        }}
      >
        {children}
      </main>
      {/* 반응형 스타일 */}
      <style>{`
        .main-content {
          margin-left: 256px;
          transition: margin-left 0.3s ease;
        }

        @media (max-width: 1024px) {
          .main-content {
            margin-left: 0;
            padding: 24px 16px !important;
          }
        }
      `}</style>
    </AuthProvider>
  );
}
