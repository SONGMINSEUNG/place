"use client";

import { createContext, useContext, useState, useEffect, ReactNode } from "react";
import { authApi } from "@/lib/api";
import { useRouter, usePathname } from "next/navigation";
import { AxiosError } from "axios";

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
  serverConnecting: boolean;
  login: (email: string, password: string) => Promise<void>;
  logout: () => void;
  refreshUser: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

// 네트워크 에러인지 판별 (타임아웃, 서버 다운, 연결 거부 등)
function isNetworkError(error: unknown): boolean {
  if (error instanceof AxiosError) {
    // 응답 자체가 없으면 네트워크 에러 (타임아웃, 연결 실패 등)
    return !error.response;
  }
  return false;
}

// 재시도 유틸 (Render cold start 대응)
async function retryWithDelay<T>(fn: () => Promise<T>, retries = 2, delay = 3000): Promise<T> {
  for (let i = 0; i <= retries; i++) {
    try {
      return await fn();
    } catch (error) {
      if (i < retries && isNetworkError(error)) {
        await new Promise((r) => setTimeout(r, delay));
        continue;
      }
      throw error;
    }
  }
  throw new Error("Max retries exceeded");
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  const [serverConnecting, setServerConnecting] = useState(false);
  const router = useRouter();
  const pathname = usePathname();

  const publicPaths = ["/login"];

  useEffect(() => {
    checkAuth();
  }, []);

  // 탭 복귀 시 세션 체크 + 서버 연결 확인
  useEffect(() => {
    const handleVisibilityChange = () => {
      if (document.visibilityState === "visible") {
        checkAuth();
      }
    };
    document.addEventListener("visibilitychange", handleVisibilityChange);
    return () => {
      document.removeEventListener("visibilitychange", handleVisibilityChange);
    };
  }, []);

  useEffect(() => {
    if (!loading && !user && !publicPaths.includes(pathname)) {
      router.push("/login");
    }
  }, [loading, user, pathname]);

  const checkAuth = async () => {
    const token = localStorage.getItem("token");
    if (!token) {
      const refreshToken = localStorage.getItem("refresh_token");
      if (refreshToken) {
        try {
          setServerConnecting(true);
          await retryWithDelay(() => authApi.refresh());
          const userData = await retryWithDelay(() => authApi.getMe());
          setUser(userData);
          setServerConnecting(false);
        } catch (error) {
          // 네트워크 에러면 토큰 유지 (서버가 아직 깨어나는 중)
          if (isNetworkError(error)) {
            setServerConnecting(true);
            scheduleRetry();
          } else {
            setServerConnecting(false);
            localStorage.removeItem("token");
            localStorage.removeItem("refresh_token");
          }
        }
      }
      setLoading(false);
      return;
    }

    try {
      setServerConnecting(true);
      const userData = await retryWithDelay(() => authApi.getMe());
      setUser(userData);
      setServerConnecting(false);
    } catch (error) {
      // 네트워크 에러면 토큰 유지 (서버가 깨어나는 중일 수 있음)
      if (isNetworkError(error)) {
        // 토큰은 유지하고, 서버 연결 중 표시
        setUser(null);
        setServerConnecting(true);
        scheduleRetry();
      } else {
        // 401 등 실제 인증 에러면 토큰 제거
        setUser(null);
        setServerConnecting(false);
        localStorage.removeItem("token");
        localStorage.removeItem("refresh_token");
      }
    } finally {
      setLoading(false);
    }
  };

  // 서버 깨어날 때까지 주기적 재시도 (5초 간격)
  const scheduleRetry = () => {
    const interval = setInterval(async () => {
      try {
        const userData = await authApi.getMe();
        setUser(userData);
        setServerConnecting(false);
        clearInterval(interval);
      } catch (error) {
        if (!isNetworkError(error)) {
          // 서버는 응답하지만 인증 실패 -> 연결은 됨
          setServerConnecting(false);
          clearInterval(interval);
        }
        // 네트워크 에러면 계속 재시도
      }
    }, 5000);
  };

  const login = async (email: string, password: string) => {
    await retryWithDelay(() => authApi.login(email, password));
    const userData = await retryWithDelay(() => authApi.getMe());
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
      const userData = await retryWithDelay(() => authApi.getMe());
      setUser(userData);
    } catch (error) {
      console.error("Failed to refresh user:", error);
    }
  };

  return (
    <AuthContext.Provider value={{ user, loading, serverConnecting, login, logout, refreshUser }}>
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
