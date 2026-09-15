"use client";

import React, { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { api, setToken as persistToken, getToken, TOKEN_KEY } from "@/lib/api-client";
import type { LoginResponse, MeResponse } from "@/types/auth";

interface AuthState {
  user: MeResponse | null;
  loading: boolean;
  login: (username: string, password: string) => Promise<void>;
  logout: () => void;
  refresh: () => Promise<void>;
}

const AuthContext = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<MeResponse | null>(null);
  const [loading, setLoading] = useState(true);

  const refresh = useCallback(async () => {
    const token = getToken();
    if (!token) {
      setUser(null);
      setLoading(false);
      return;
    }
    try {
      let me: MeResponse;
      try {
        me = await api.get<MeResponse>("/api/users/me");
      } catch {
        me = await api.get<MeResponse>("/api/auth/me");
      }
      setUser(me);
    } catch {
      persistToken(null);
      setUser(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  // Listen for token removal (e.g. from 401 interceptor or another tab)
  useEffect(() => {
    function onStorage(e: StorageEvent) {
      if (e.key === TOKEN_KEY && !e.newValue) {
        setUser(null);
      }
    }
    function onTokenCleared() {
      setUser(null);
    }
    window.addEventListener("storage", onStorage);
    window.addEventListener("sih26027_token_cleared", onTokenCleared);
    return () => {
      window.removeEventListener("storage", onStorage);
      window.removeEventListener("sih26027_token_cleared", onTokenCleared);
    };
  }, []);

  const login = useCallback(
    async (username: string, password: string) => {
      const res = await api.post<LoginResponse>("/api/auth/login", { username, password });
      persistToken(res.access_token);
      setUser({
        id: res.user.id,
        name: res.user.name,
        email: res.user.email,
        role: res.user.role,
        department: res.user.department,
        department_id: res.user.department_id,
        is_active: res.user.is_active,
      });
    },
    []
  );

  const logout = useCallback(() => {
    persistToken(null);
    setUser(null);
  }, []);

  const value = useMemo(() => ({ user, loading, login, logout, refresh }), [user, loading, login, logout, refresh]);
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
