'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { useAuth } from '@/lib/auth';
import { login as apiLogin } from '@/lib/api';
import { DEMO_USERS } from '@/lib/types';

export default function LoginPage() {
  const router = useRouter();
  const { login } = useAuth();
  const [loading, setLoading] = useState<string | null>(null);
  const [error, setError] = useState('');

  const handleRoleLogin = async (username: string, password: string) => {
    setLoading(username);
    setError('');
    try {
      const res = await apiLogin(username, password);
      login(res.token, res.user);
      router.push('/chat');
    } catch (err: any) {
      setError(err.message || 'Login failed');
    } finally {
      setLoading(null);
    }
  };

  return (
    <div className="login-page">
      <div className="login-container animate-fade-in">
        <div className="login-header">
          <h1>🤖 FinBot</h1>
          <p>Intelligent RAG Chatbot with Role-Based Access Control</p>
          <p style={{ color: 'var(--text-muted)', fontSize: 13, marginTop: 8 }}>
            Select a role below to explore department-specific access
          </p>
        </div>

        {error && (
          <div className="guardrail-banner guardrail-blocked" style={{ marginBottom: 20, justifyContent: 'center' }}>
            ❌ {error}
          </div>
        )}

        <div className="role-grid">
          {DEMO_USERS.map((demo, i) => (
            <div
              key={demo.username}
              className="role-card"
              onClick={() => handleRoleLogin(demo.username, demo.password)}
              style={{
                opacity: loading && loading !== demo.username ? 0.5 : 1,
                animationDelay: `${i * 0.05}s`,
              }}
            >
              {loading === demo.username ? (
                <div className="typing-indicator" style={{ justifyContent: 'center', margin: '8px 0' }}>
                  <div className="typing-dot" />
                  <div className="typing-dot" />
                  <div className="typing-dot" />
                </div>
              ) : (
                <div className="icon">{demo.icon}</div>
              )}
              <div className="label">{demo.label}</div>
              <div className="desc">{demo.description}</div>
            </div>
          ))}
        </div>

        <div style={{ textAlign: 'center', color: 'var(--text-muted)', fontSize: 12 }}>
          All demo accounts use password: <code style={{ background: 'var(--bg-glass)', padding: '2px 6px', borderRadius: 4 }}>demo123</code>
        </div>
      </div>
    </div>
  );
}
