'use client';

import React, { createContext, useContext, useEffect, useState, useCallback } from 'react';
import type { User } from './types';

interface AuthContextType {
  user: User | null;
  token: string | null;
  isAuthenticated: boolean;
  isExecutive: boolean;
  accessibleCollections: string[];
  login: (token: string, user: User) => void;
  logout: () => void;
}

const AuthContext = createContext<AuthContextType>({
  user: null,
  token: null,
  isAuthenticated: false,
  isExecutive: false,
  accessibleCollections: [],
  login: () => {},
  logout: () => {},
});

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [token, setToken] = useState<string | null>(null);
  const [accessibleCollections, setAccessibleCollections] = useState<string[]>([]);

  // Restore session from localStorage on mount
  useEffect(() => {
    const savedToken = localStorage.getItem('finbot_token');
    const savedUser = localStorage.getItem('finbot_user');
    const savedCollections = localStorage.getItem('finbot_collections');
    if (savedToken && savedUser) {
      try {
        setToken(savedToken);
        setUser(JSON.parse(savedUser));
        setAccessibleCollections(savedCollections ? JSON.parse(savedCollections) : []);
      } catch {
        localStorage.removeItem('finbot_token');
        localStorage.removeItem('finbot_user');
      }
    }
  }, []);

  const handleLogin = useCallback((newToken: string, newUser: User) => {
    setToken(newToken);
    setUser(newUser);
    localStorage.setItem('finbot_token', newToken);
    localStorage.setItem('finbot_user', JSON.stringify(newUser));

    // Fetch accessible collections
    const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
    fetch(`${API_BASE}/api/auth/me`, {
      headers: { Authorization: `Bearer ${newToken}` },
    })
      .then(res => res.json())
      .then(data => {
        const cols = data.accessible_collections || [];
        setAccessibleCollections(cols);
        localStorage.setItem('finbot_collections', JSON.stringify(cols));
      })
      .catch(() => {});
  }, []);

  const handleLogout = useCallback(() => {
    setToken(null);
    setUser(null);
    setAccessibleCollections([]);
    localStorage.removeItem('finbot_token');
    localStorage.removeItem('finbot_user');
    localStorage.removeItem('finbot_collections');
  }, []);

  return (
    <AuthContext.Provider
      value={{
        user,
        token,
        isAuthenticated: !!user && !!token,
        isExecutive: user?.role === 'executive',
        accessibleCollections,
        login: handleLogin,
        logout: handleLogout,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  return useContext(AuthContext);
}
