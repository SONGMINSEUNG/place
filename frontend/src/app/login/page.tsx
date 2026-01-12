"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { Eye, EyeOff, Mail, Lock, User, Loader2 } from "lucide-react";
import { authApi } from "@/lib/api";
import { toast } from "sonner";
import { useAuth } from "@/contexts/AuthContext";

export default function LoginPage() {
  const router = useRouter();
  const { user, login: authLogin, loading: authLoading } = useAuth();
  const [isLogin, setIsLogin] = useState(true);
  const [loading, setLoading] = useState(false);
  const [showPassword, setShowPassword] = useState(false);

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [name, setName] = useState("");

  // 이미 로그인된 사용자는 대시보드로 리다이렉트
  useEffect(() => {
    if (!authLoading && user) {
      router.push("/");
    }
  }, [user, authLoading, router]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    if (!email || !password) {
      toast.error("이메일과 비밀번호를 입력해주세요");
      return;
    }

    if (!isLogin && !name) {
      toast.error("이름을 입력해주세요");
      return;
    }

    setLoading(true);
    try {
      if (isLogin) {
        await authLogin(email, password);
        toast.success("로그인 성공!");
      } else {
        await authApi.register(email, password, name);
        toast.success("회원가입 성공! 로그인해주세요");
        setIsLogin(true);
        setPassword("");
      }
    } catch (error: any) {
      toast.error(error.response?.data?.detail || "오류가 발생했습니다");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{
      minHeight: '100vh',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      background: 'linear-gradient(135deg, #fdf2f8 0%, #f3e8ff 50%, #dbeafe 100%)',
      marginLeft: '-256px',
      padding: '32px'
    }}>
      <div style={{
        width: '100%',
        maxWidth: '420px',
        background: 'white',
        borderRadius: '24px',
        padding: '40px',
        boxShadow: '0 4px 24px rgba(0, 0, 0, 0.08)'
      }}>
        {/* Logo */}
        <div style={{ textAlign: 'center', marginBottom: '32px' }}>
          <div style={{
            width: '64px',
            height: '64px',
            borderRadius: '16px',
            background: 'linear-gradient(135deg, #6366f1, #8b5cf6)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            margin: '0 auto 16px'
          }}>
            <span style={{ fontSize: '28px', color: 'white', fontWeight: 'bold' }}>P</span>
          </div>
          <h1 style={{ fontSize: '24px', fontWeight: 'bold', color: '#1e293b' }}>PlaceRank</h1>
          <p style={{ fontSize: '14px', color: '#64748b', marginTop: '8px' }}>
            {isLogin ? '계정에 로그인하세요' : '새 계정을 만드세요'}
          </p>
        </div>

        {/* Tabs */}
        <div style={{
          display: 'flex',
          background: '#f1f5f9',
          borderRadius: '12px',
          padding: '4px',
          marginBottom: '24px'
        }}>
          <button
            onClick={() => setIsLogin(true)}
            style={{
              flex: 1,
              padding: '10px',
              borderRadius: '8px',
              border: 'none',
              fontSize: '14px',
              fontWeight: '600',
              cursor: 'pointer',
              background: isLogin ? 'white' : 'transparent',
              color: isLogin ? '#1e293b' : '#64748b',
              boxShadow: isLogin ? '0 1px 3px rgba(0,0,0,0.1)' : 'none'
            }}
          >
            로그인
          </button>
          <button
            onClick={() => setIsLogin(false)}
            style={{
              flex: 1,
              padding: '10px',
              borderRadius: '8px',
              border: 'none',
              fontSize: '14px',
              fontWeight: '600',
              cursor: 'pointer',
              background: !isLogin ? 'white' : 'transparent',
              color: !isLogin ? '#1e293b' : '#64748b',
              boxShadow: !isLogin ? '0 1px 3px rgba(0,0,0,0.1)' : 'none'
            }}
          >
            회원가입
          </button>
        </div>

        {/* Form */}
        <form onSubmit={handleSubmit}>
          {!isLogin && (
            <div style={{ marginBottom: '16px' }}>
              <label style={{ fontSize: '14px', fontWeight: '500', color: '#374151', display: 'block', marginBottom: '8px' }}>
                이름
              </label>
              <div style={{ position: 'relative' }}>
                <User style={{
                  position: 'absolute',
                  left: '14px',
                  top: '50%',
                  transform: 'translateY(-50%)',
                  width: '18px',
                  height: '18px',
                  color: '#94a3b8'
                }} />
                <input
                  type="text"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  placeholder="홍길동"
                  style={{
                    width: '100%',
                    padding: '14px 14px 14px 44px',
                    borderRadius: '12px',
                    border: '1.5px solid #e2e8f0',
                    fontSize: '14px',
                    outline: 'none'
                  }}
                />
              </div>
            </div>
          )}

          <div style={{ marginBottom: '16px' }}>
            <label style={{ fontSize: '14px', fontWeight: '500', color: '#374151', display: 'block', marginBottom: '8px' }}>
              이메일
            </label>
            <div style={{ position: 'relative' }}>
              <Mail style={{
                position: 'absolute',
                left: '14px',
                top: '50%',
                transform: 'translateY(-50%)',
                width: '18px',
                height: '18px',
                color: '#94a3b8'
              }} />
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="example@email.com"
                style={{
                  width: '100%',
                  padding: '14px 14px 14px 44px',
                  borderRadius: '12px',
                  border: '1.5px solid #e2e8f0',
                  fontSize: '14px',
                  outline: 'none'
                }}
              />
            </div>
          </div>

          <div style={{ marginBottom: '24px' }}>
            <label style={{ fontSize: '14px', fontWeight: '500', color: '#374151', display: 'block', marginBottom: '8px' }}>
              비밀번호
            </label>
            <div style={{ position: 'relative' }}>
              <Lock style={{
                position: 'absolute',
                left: '14px',
                top: '50%',
                transform: 'translateY(-50%)',
                width: '18px',
                height: '18px',
                color: '#94a3b8'
              }} />
              <input
                type={showPassword ? "text" : "password"}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="••••••••"
                style={{
                  width: '100%',
                  padding: '14px 44px 14px 44px',
                  borderRadius: '12px',
                  border: '1.5px solid #e2e8f0',
                  fontSize: '14px',
                  outline: 'none'
                }}
              />
              <button
                type="button"
                onClick={() => setShowPassword(!showPassword)}
                style={{
                  position: 'absolute',
                  right: '14px',
                  top: '50%',
                  transform: 'translateY(-50%)',
                  background: 'none',
                  border: 'none',
                  cursor: 'pointer',
                  padding: '0'
                }}
              >
                {showPassword
                  ? <EyeOff style={{ width: '18px', height: '18px', color: '#94a3b8' }} />
                  : <Eye style={{ width: '18px', height: '18px', color: '#94a3b8' }} />
                }
              </button>
            </div>
          </div>

          <button
            type="submit"
            disabled={loading}
            style={{
              width: '100%',
              padding: '14px',
              borderRadius: '12px',
              border: 'none',
              background: 'linear-gradient(135deg, #6366f1, #8b5cf6)',
              color: 'white',
              fontSize: '16px',
              fontWeight: '600',
              cursor: loading ? 'not-allowed' : 'pointer',
              opacity: loading ? 0.7 : 1,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              gap: '8px'
            }}
          >
            {loading && <Loader2 style={{ width: '18px', height: '18px', animation: 'spin 1s linear infinite' }} />}
            {isLogin ? '로그인' : '회원가입'}
          </button>
        </form>

        {/* Membership Info */}
        <div style={{
          marginTop: '24px',
          padding: '16px',
          background: '#f8fafc',
          borderRadius: '12px',
          textAlign: 'center'
        }}>
          <p style={{ fontSize: '13px', color: '#64748b' }}>
            무료 회원: 하루 <strong>10회</strong> 조회 가능
          </p>
          <p style={{ fontSize: '12px', color: '#94a3b8', marginTop: '4px' }}>
            Pro 업그레이드 시 200회까지!
          </p>
        </div>
      </div>
    </div>
  );
}
