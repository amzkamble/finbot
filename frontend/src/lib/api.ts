/* Centralized API client for all backend communication */

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

function getToken(): string | null {
  if (typeof window === 'undefined') return null;
  return localStorage.getItem('finbot_token');
}

async function apiFetch<T>(path: string, options: RequestInit = {}): Promise<T> {
  const token = getToken();
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...(options.headers as Record<string, string> || {}),
  };
  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }

  const res = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers,
  });

  if (res.status === 401) {
    if (typeof window !== 'undefined') {
      localStorage.removeItem('finbot_token');
      window.location.href = '/login';
    }
    throw new Error('Unauthorized');
  }

  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || `API error: ${res.status}`);
  }

  return res.json();
}

/* ── Auth ─────────────────────────────────────────────────────── */

import type { LoginResponse, ChatResponse, User, DocumentInfo, StatsResponse } from './types';

export async function login(username: string, password: string): Promise<LoginResponse> {
  return apiFetch<LoginResponse>('/api/auth/login', {
    method: 'POST',
    body: JSON.stringify({ username, password }),
  });
}

export async function getMe(): Promise<User & { accessible_collections: string[] }> {
  return apiFetch('/api/auth/me');
}

/* ── Chat ─────────────────────────────────────────────────────── */

export async function sendMessage(message: string, sessionId: string): Promise<ChatResponse> {
  return apiFetch<ChatResponse>('/api/chat', {
    method: 'POST',
    body: JSON.stringify({ message, session_id: sessionId }),
  });
}

export async function getChatHistory(sessionId: string): Promise<{ role: string; content: string }[]> {
  return apiFetch<{ role: string; content: string }[]>(`/api/chat/history?session_id=${encodeURIComponent(sessionId)}`);
}

/* ── Admin ────────────────────────────────────────────────────── */

export async function getUsers(): Promise<User[]> {
  return apiFetch<User[]>('/api/admin/users');
}

export async function updateRole(userId: string, role: string): Promise<User> {
  return apiFetch<User>(`/api/admin/users/${userId}/role`, {
    method: 'PUT',
    body: JSON.stringify({ role }),
  });
}

export async function getDocuments(): Promise<DocumentInfo[]> {
  return apiFetch<DocumentInfo[]>('/api/admin/documents');
}

export async function getStats(): Promise<StatsResponse> {
  return apiFetch<StatsResponse>('/api/admin/stats');
}

export async function triggerIngest(collection: string): Promise<{ status: string; message: string }> {
  return apiFetch('/api/admin/ingest', {
    method: 'POST',
    body: JSON.stringify({ collection }),
  });
}
