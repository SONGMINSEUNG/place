"use client";

import { createContext, useContext, useState, useEffect, ReactNode } from "react";
import { authApi } from "@/lib/api";
import { useRouter, usePathname } from "next/navigation";

interface User {
  id: number;
  email: string;
  name: string | null;
  membership_type: string;
  daily_search_count: number;
  daily_limit: number;
}

interface AuthContextType {
  user: User | null;
  loading: boolean;
  login: (email: string, password: string) => Promise<void>;
  logout: () => void;
  refreshUser: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  const router = useRouter();
  const pathname = usePathname();

  const publicPaths = ["/login"];

  useEffect(() => {
    checkAuth();
  }, []);

  useEffect(() => {
    if (!loading && !user && !publicPaths.includes(pathname)) {
      router.push("/login");
    }
  }, [loading, user, pathname]);

  const checkAuth = async () => {
    const token = localStorage.getItem("token");
    if (!token) {
      // access token이 없어도 refresh token이 있으면 갱신 시도
      const refreshToken = localStorage.getItem("refresh_token");
      if (refreshToken) {
        try {
          await authApi.refresh();
          // refresh 성공 후 사용자 정보 조회
          const userData = await authApi.getMe();
          setUser(userData);
        } catch {
          // refresh도 실패하면 모든 토큰 제거
          localStorage.removeItem("token");
          localStorage.removeItem("refresh_token");
        }
      }
      setLoading(false);
      return;
    }

    try {
      const userData = await authApi.getMe();
      setUser(userData);
    } catch {
      // getMe 실패 시 토큰 정리 (refresh는 axios 인터셉터가 자동 처리)
      setUser(null);
      localStorage.removeItem("token");
      localStorage.removeItem("refresh_token");
    } finally {
      setLoading(false);
    }
  };

  const login = async (email: string, password: string) => {
    await authApi.login(email, password);
    // login이 성공하면 authApi.login 내부에서 token과 refresh_token이 저장됨
    const userData = await authApi.getMe();
    setUser(userData);
    router.push("/");
  };

  const logout = () => {
    authApi.logout();
    setUser(null);
    router.push("/login");
  };

  const refreshUser = async () => {
    try {
      const userData = await authApi.getMe();
      setUser(userData);
    } catch (error) {
      console.error("Failed to refresh user:", error);
    }
  };

  return (
    <AuthContext.Provider value={{ user, loading, login, logout, refreshUser }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return context;
}
