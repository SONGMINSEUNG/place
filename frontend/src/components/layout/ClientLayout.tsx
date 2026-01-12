"use client";

import { usePathname } from "next/navigation";
import { AuthProvider } from "@/contexts/AuthContext";
import { Sidebar } from "./sidebar";

export function ClientLayout({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const isLoginPage = pathname === "/login";

  return (
    <AuthProvider>
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
