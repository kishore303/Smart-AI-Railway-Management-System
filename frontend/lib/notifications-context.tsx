"use client";

import React, { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from "react";
import { api, BASE_URL, getToken } from "@/lib/api-client";
import { useAuth } from "@/lib/auth-context";
import { isWsNotificationEvent, type WsNotificationEvent, type WsStatus } from "@/types/notifications";

interface NotificationsState {
  status: WsStatus;
  unread: number | null;
  refreshUnread: () => Promise<void>;
  lastEvent: WsNotificationEvent | null;
  feedVersion: number;
}

const NotificationsContext = createContext<NotificationsState | null>(null);

const BACKOFFS = [1000, 2000, 5000, 10000, 30000];

function toWsUrl(): string | null {
  const token = getToken();
  if (!token) return null;
  const wsBase = BASE_URL.replace(/^http:/, "ws:").replace(/^https:/, "wss:");
  return `${wsBase}/api/notifications/ws?token=${encodeURIComponent(token)}`;
}

export function NotificationsProvider({ children }: { children: React.ReactNode }) {
  const { user, loading } = useAuth();
  const [status, setStatus] = useState<WsStatus>("DISCONNECTED");
  const [unread, setUnread] = useState<number | null>(null);
  const [lastEvent, setLastEvent] = useState<WsNotificationEvent | null>(null);
  const [feedVersion, setFeedVersion] = useState(0);
  const seenIds = useRef<Set<number>>(new Set());
  const socketRef = useRef<WebSocket | null>(null);
  const attemptRef = useRef(0);
  const retryTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const pingTimer = useRef<ReturnType<typeof setInterval> | null>(null);
  const unmounted = useRef(false);

  const refreshUnread = useCallback(async () => {
    if (!getToken()) {
      setUnread(null);
      return;
    }
    try {
      const r = await api.get<{ unread: number }>("/api/notifications/unread/count");
      setUnread(r.unread);
    } catch {
      // Keep last known value; page-level errors surface separately.
    }
  }, []);

  const cleanupSocket = useCallback(() => {
    if (retryTimer.current) {
      clearTimeout(retryTimer.current);
      retryTimer.current = null;
    }
    if (pingTimer.current) {
      clearInterval(pingTimer.current);
      pingTimer.current = null;
    }
    if (socketRef.current) {
      try {
        socketRef.current.close();
      } catch {
        // ignore
      }
      socketRef.current = null;
    }
  }, []);

  const connect = useCallback(() => {
    if (unmounted.current || !getToken()) return;
    cleanupSocket();
    const url = toWsUrl();
    if (!url) return;
    setStatus(attemptRef.current === 0 ? "CONNECTING" : "RECONNECTING");
    let ws: WebSocket;
    try {
      ws = new WebSocket(url);
    } catch {
      scheduleRetry();
      return;
    }
    socketRef.current = ws;

    ws.onopen = () => {
      if (unmounted.current) return;
      attemptRef.current = 0;
      setStatus("CONNECTED");
      pingTimer.current = setInterval(() => {
        try {
          if (ws.readyState === WebSocket.OPEN) ws.send("ping");
        } catch {
          // ignore
        }
      }, 25000);
      void refreshUnread();
    };

    ws.onmessage = (ev) => {
      let data: unknown = null;
      try {
        data = JSON.parse(String(ev.data));
      } catch {
        return;
      }
      if (isWsNotificationEvent(data)) {
        if (seenIds.current.has(data.notification_id)) return;
        seenIds.current.add(data.notification_id);
        if (seenIds.current.size > 500) {
          const first = seenIds.current.values().next().value;
          if (first !== undefined) seenIds.current.delete(first);
        }
        setLastEvent(data);
        setFeedVersion((v) => v + 1);
        void refreshUnread();
      }
      // "connected" and "pong" carry no state; ignored.
    };

    ws.onerror = () => {
      try {
        ws.close();
      } catch {
        // ignore
      }
    };

    ws.onclose = () => {
      if (pingTimer.current) {
        clearInterval(pingTimer.current);
        pingTimer.current = null;
      }
      socketRef.current = null;
      if (!unmounted.current && getToken()) scheduleRetry();
      else if (!unmounted.current) setStatus("DISCONNECTED");
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [cleanupSocket, refreshUnread]);

  function scheduleRetry() {
    if (unmounted.current || !getToken()) {
      if (!unmounted.current) setStatus("DISCONNECTED");
      return;
    }
    const delay = BACKOFFS[Math.min(attemptRef.current, BACKOFFS.length - 1)];
    attemptRef.current += 1;
    setStatus("RECONNECTING");
    retryTimer.current = setTimeout(() => {
      retryTimer.current = null;
      connect();
    }, delay);
  }

  useEffect(() => {
    unmounted.current = false;
    if (!loading && user && getToken()) {
      attemptRef.current = 0;
      connect();
      void refreshUnread();
    } else if (!loading && !user) {
      cleanupSocket();
      attemptRef.current = 0;
      setStatus("DISCONNECTED");
      setUnread(null);
    }
    return () => {
      // Cleanup handled on unmount below; this return runs on user change too.
      cleanupSocket();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [user, loading]);

  useEffect(() => {
    return () => {
      unmounted.current = true;
      cleanupSocket();
    };
  }, [cleanupSocket]);

  const value = useMemo(
    () => ({ status, unread, refreshUnread, lastEvent, feedVersion }),
    [status, unread, refreshUnread, lastEvent, feedVersion]
  );
  return <NotificationsContext.Provider value={value}>{children}</NotificationsContext.Provider>;
}

export function useNotifications(): NotificationsState {
  const ctx = useContext(NotificationsContext);
  if (!ctx) throw new Error("useNotifications must be used within NotificationsProvider");
  return ctx;
}
