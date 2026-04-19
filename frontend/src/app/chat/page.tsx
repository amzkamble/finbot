'use client';

import { useCallback, useEffect, useRef, useState } from 'react';
import { useRouter } from 'next/navigation';
import ReactMarkdown from 'react-markdown';
import { useAuth } from '@/lib/auth';
import { sendMessage, getChatHistory } from '@/lib/api';
import type { ChatMessage, ChatResponse, SourceInfo, RouteInfo, GuardrailInfo } from '@/lib/types';
import { COLLECTION_COLORS } from '@/lib/types';

function generateId() {
  return Math.random().toString(36).slice(2, 10);
}

function getOrCreateSessionId(): string {
  if (typeof window === 'undefined') return generateId();
  const saved = localStorage.getItem('finbot_session_id');
  if (saved) return saved;
  const newId = generateId();
  localStorage.setItem('finbot_session_id', newId);
  return newId;
}

export default function ChatPage() {
  const router = useRouter();
  const { user, isAuthenticated, isExecutive, accessibleCollections, logout } = useAuth();
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [sessionId, setSessionId] = useState(() => getOrCreateSessionId());
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const historyLoaded = useRef(false);

  useEffect(() => {
    if (!isAuthenticated) router.replace('/login');
  }, [isAuthenticated, router]);

  // Load chat history from backend SQLite on mount
  useEffect(() => {
    if (!isAuthenticated || historyLoaded.current) return;
    historyLoaded.current = true;

    getChatHistory(sessionId)
      .then((history) => {
        if (history.length > 0) {
          const restored: ChatMessage[] = history.map((msg) => ({
            id: generateId(),
            role: msg.role as 'user' | 'assistant',
            content: msg.content,
            timestamp: new Date(),
          }));
          setMessages(restored);
        }
      })
      .catch(() => {}); // Silently fail if backend is not reachable
  }, [isAuthenticated, sessionId]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const handleNewChat = useCallback(() => {
    setMessages([]);
    const newId = generateId();
    setSessionId(newId);
    localStorage.setItem('finbot_session_id', newId);
    historyLoaded.current = false;
  }, []);

  const handleSend = useCallback(async () => {
    if (!input.trim() || loading) return;
    const text = input.trim();
    setInput('');

    const userMsg: ChatMessage = {
      id: generateId(),
      role: 'user',
      content: text,
      timestamp: new Date(),
    };
    setMessages(prev => [...prev, userMsg]);
    setLoading(true);

    try {
      const res: ChatResponse = await sendMessage(text, sessionId);
      const botMsg: ChatMessage = {
        id: generateId(),
        role: 'assistant',
        content: res.blocked ? (res.blocked_reason || 'Request blocked by guardrails.') : res.answer,
        timestamp: new Date(),
        sources: res.sources,
        route: res.route,
        guardrails: res.guardrails,
        blocked: res.blocked,
        blocked_reason: res.blocked_reason,
        metadata: res.metadata,
      };
      setMessages(prev => [...prev, botMsg]);
    } catch (err: any) {
      setMessages(prev => [
        ...prev,
        {
          id: generateId(),
          role: 'assistant',
          content: `⚠️ Error: ${err.message}`,
          timestamp: new Date(),
        },
      ]);
    } finally {
      setLoading(false);
    }
  }, [input, loading, sessionId]);

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  if (!user) return null;

  return (
    <div className="chat-page">
      {/* Header */}
      <header className="chat-header">
        <div className="chat-header-left">
          <h1>🤖 FinBot</h1>
          <span className="badge badge-role">🔹 {user.role.replace('_', ' ')}</span>
          <div className="collections-bar">
            {accessibleCollections.map(col => (
              <span key={col} className={`badge badge-${col}`}>{col}</span>
            ))}
          </div>
        </div>
        <div className="chat-header-right">
          <button className="btn btn-ghost" onClick={handleNewChat} style={{ fontSize: 13 }}>
            + New Chat
          </button>
          {isExecutive && (
            <button className="btn btn-ghost" onClick={() => router.push('/admin')} style={{ fontSize: 13 }}>
              Admin
            </button>
          )}
          <button className="btn btn-ghost" onClick={() => { logout(); router.push('/login'); }} style={{ fontSize: 13 }}>
            Logout
          </button>
        </div>
      </header>

      {/* Messages */}
      <div className="chat-messages">
        {messages.length === 0 && (
          <div style={{ textAlign: 'center', marginTop: '20vh', color: 'var(--text-muted)' }} className="animate-fade-in">
            <div style={{ fontSize: 48, marginBottom: 16 }}>🤖</div>
            <h2 style={{ fontSize: 20, fontWeight: 600, color: 'var(--text-secondary)', marginBottom: 8 }}>
              Welcome, {user.username.split('_')[0]}!
            </h2>
            <p style={{ fontSize: 14, maxWidth: 500, margin: '0 auto', lineHeight: 1.6 }}>
              Ask me anything about the company. Your role ({user.role.replace('_', ' ')}) gives you access to: {accessibleCollections.join(', ')}.
            </p>
          </div>
        )}

        {messages.map(msg => (
          <div key={msg.id} className={`message message-${msg.role}`}>
            {/* Route indicator for bot messages */}
            {msg.role === 'assistant' && msg.route && !msg.blocked && (
              <div className="route-indicator">
                <span className={`badge badge-${msg.route.collections_searched?.[0] || 'general'}`} style={{ fontSize: 10 }}>
                  {msg.route.name.replace('_route', '').replace('_', ' ')}
                </span>
                <span>{(msg.route.confidence * 100).toFixed(0)}% confidence</span>
                {msg.route.was_rbac_filtered && (
                  <span style={{ color: 'var(--accent-warning)' }}>
                    ⚠ Adjusted from: {msg.route.original_route?.replace('_route', '')}
                  </span>
                )}
              </div>
            )}

            {/* Guardrail banners */}
            {msg.blocked && (
              <div className="guardrail-banner guardrail-blocked">
                🚫 Blocked: {msg.blocked_reason?.replace(/_/g, ' ')}
              </div>
            )}
            {msg.guardrails?.output?.grounding_warning && (
              <div className="guardrail-banner guardrail-warning">
                ⚠ Response may contain ungrounded claims (score: {msg.guardrails.output.grounding_score.toFixed(2)})
              </div>
            )}
            {msg.guardrails?.input?.pii_scrubbed && (
              <div className="guardrail-banner guardrail-info">
                🛡️ PII was detected and redacted from your query
              </div>
            )}
            {msg.guardrails?.output?.citations_auto_added && (
              <div className="guardrail-banner guardrail-info">
                📝 Citations were automatically added to this response
              </div>
            )}

            {/* Message bubble */}
            <div className="message-bubble">
              {msg.role === 'assistant' ? (
                <ReactMarkdown>{msg.content}</ReactMarkdown>
              ) : (
                msg.content
              )}
            </div>

            {/* Sources */}
            {msg.sources && msg.sources.length > 0 && (
              <div className="sources-panel">
                {msg.sources.map((src: SourceInfo, i: number) => (
                  <div key={i} className="source-card">
                    <span style={{ color: COLLECTION_COLORS[src.collection] || '#6b7280' }}>📄</span>
                    <span className="source-doc">{src.document}</span>
                    {src.page > 0 && <span>Page {src.page}</span>}
                    {src.section !== 'Untitled Section' && <span>· {src.section}</span>}
                    <span className={`badge badge-${src.collection}`} style={{ marginLeft: 'auto' }}>
                      {src.collection}
                    </span>
                  </div>
                ))}
              </div>
            )}

            {/* Metadata */}
            {msg.metadata?.latency_ms && msg.role === 'assistant' && (
              <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 6 }}>
                {msg.metadata.latency_ms}ms · {msg.metadata.chunks_retrieved || 0} chunks
              </div>
            )}
          </div>
        ))}

        {loading && (
          <div className="message message-assistant animate-fade-in">
            <div className="message-bubble">
              <div className="typing-indicator">
                <div className="typing-dot" />
                <div className="typing-dot" />
                <div className="typing-dot" />
              </div>
            </div>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* Input */}
      <div className="chat-input-area">
        <div className="chat-input-wrapper">
          <input
            className="input"
            placeholder="Ask about company data..."
            value={input}
            onChange={e => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            disabled={loading}
            maxLength={4000}
          />
          <button className="btn btn-primary" onClick={handleSend} disabled={loading || !input.trim()}>
            {loading ? '...' : 'Send'}
          </button>
        </div>
      </div>
    </div>
  );
}
