"use client";

import React, { useCallback, useEffect, useState } from "react";
import ProtectedRoute from "@/components/ProtectedRoute";
import AppShell from "@/components/AppShell";
import Breadcrumbs from "@/components/Breadcrumbs";
import { api, ApiError } from "@/lib/api-client";
import { useNotifications } from "@/lib/notifications-context";
import type { NotificationItem, NotificationListResponse, WsStatus } from "@/types/notifications";
import { priorityBadgeKind } from "@/types/notifications";

type Filter = "ALL" | "UNREAD";

export default function NotificationsPage() {
  return (
    <ProtectedRoute>
      <AppShell>
        <NotifContent />
      </AppShell>
    </ProtectedRoute>
  );
}

function statusPill(status: WsStatus): string {
  if (status === "CONNECTED") return "gov-badge-green";
  if (status === "DISCONNECTED") return "gov-badge-red";
  return "gov-badge-amber";
}

function NotifContent() {
  const { status, unread, refreshUnread, lastEvent, feedVersion } = useNotifications();
  const [filter, setFilter] = useState<Filter>("ALL");
  const [items, setItems] = useState<NotificationItem[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [acting, setActing] = useState(false);
  const [toastVisible, setToastVisible] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const params = new URLSearchParams({ skip: "0", limit: "20" });
      if (filter === "UNREAD") params.set("unread_only", "true");
      const res = await api.get<NotificationListResponse>(`/api/notifications?${params.toString()}`);
      setItems(res.items);
      setTotal(res.total);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Unable to connect to the railway service. Please try again.");
    } finally {
      setLoading(false);
    }
  }, [filter]);

  useEffect(() => {
    void load();
  }, [load]);

  const firstRender = React.useRef(true);
  useEffect(() => {
    if (firstRender.current) {
      firstRender.current = false;
      return;
    }
    void load();
    setToastVisible(true);
    const t = setTimeout(() => setToastVisible(false), 6000);
    return () => clearTimeout(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [feedVersion]);

  async function onMarkRead(id: number) {
    if (acting) return;
    setActing(true);
    try {
      await api.post(`/api/notifications/${id}/read`, {});
      setItems((prev) => prev.map((n) => (n.id === id ? { ...n, is_read: true } : n)));
      await refreshUnread();
      if (filter === "UNREAD") await load();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Unable to connect to the railway service. Please try again.");
    } finally {
      setActing(false);
    }
  }

  async function onMarkAllRead() {
    if (acting) return;
    setActing(true);
    try {
      await api.post("/api/notifications/read-all", {});
      setItems((prev) => prev.map((n) => ({ ...n, is_read: true })));
      await refreshUnread();
      await load();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Unable to connect to the railway service. Please try again.");
    } finally {
      setActing(false);
    }
  }

  const toastCritical =
    lastEvent != null &&
    (lastEvent.priority === "HIGH" || lastEvent.priority === "CRITICAL" || lastEvent.priority === "EMERGENCY");

  return (
    <div className="gov-page">
      <Breadcrumbs trail={[{ label: "Dashboard", href: "/dashboard" }, { label: "Notifications" }]} />

      <div className="gov-page-header">
        <div>
          <h2 className="gov-title">
            Notifications{" "}
            {unread != null && unread > 0 ? <span className="gov-badge gov-badge-red">{unread} unread</span> : null}{" "}
            <span className={`gov-badge ${statusPill(status)}`}>{status}</span>
          </h2>
          <p className="gov-sub">
            Informational workflow updates only. Notifications never approve blocks, validate safety, or
            start execution. The list below is the authoritative record; the live connection only delivers new arrivals.
          </p>
        </div>
      </div>

      {toastVisible && lastEvent ? (
        <div
          className={`gov-alert gov-alert-${toastCritical ? "error" : "info"}`}
          role="status"
        >
          <strong>New: {lastEvent.title}</strong>
          <span className="gov-muted"> ({lastEvent.event})</span>
          <button
            type="button"
            className="gov-link"
            style={{ background: "none", border: "none", cursor: "pointer", marginLeft: 12 }}
            onClick={() => setToastVisible(false)}
            aria-label="Dismiss notification"
          >
            Dismiss
          </button>
        </div>
      ) : null}

      <div className="gov-card">
        <div style={{ display: "flex", gap: 8, flexWrap: "wrap", alignItems: "center" }}>
          <div className="gov-tabs" style={{ border: "none", marginBottom: 0 }}>
            {(["ALL", "UNREAD"] as Filter[]).map((f) => (
              <button
                key={f}
                type="button"
                className={`gov-tab${filter === f ? " active" : ""}`}
                onClick={() => setFilter(f)}
              >
                {f === "ALL" ? "All" : "Unread"}
              </button>
            ))}
          </div>
          <button
            type="button"
            className="gov-btn gov-btn-sm gov-btn-secondary"
            onClick={() => void onMarkAllRead()}
            disabled={acting}
          >
            Mark all as read
          </button>
          <span className="gov-muted" style={{ marginLeft: "auto" }}>Total: {total}</span>
        </div>
      </div>

      <div className="gov-card">
        {loading ? <div className="gov-loading">Loading notifications…</div> : null}
        {error && !loading ? <div className="gov-alert gov-alert-error" role="alert">{error}</div> : null}
        {!loading && !error && items.length === 0 ? (
          <div className="gov-empty">
            <div className="gov-empty-icon">🔔</div>
            <p>No notifications available.</p>
          </div>
        ) : null}
        {!loading && !error && items.length > 0 ? (
          <ul style={{ listStyle: "none", padding: 0, margin: 0 }}>
            {items.map((n) => (
              <li
                key={n.id}
                style={{
                  padding: "12px 16px",
                  borderBottom: "1px solid var(--border-light)",
                  background: n.is_read ? "transparent" : "#f6f9ff",
                  borderRadius: "var(--radius)",
                  marginBottom: 4,
                }}
              >
                <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
                  {!n.is_read ? <span className="gov-badge gov-badge-blue">Unread</span> : null}
                  <span className={`gov-badge gov-badge-${priorityBadgeKind(n.priority)}`}>{n.priority}</span>
                  <strong>{n.title}</strong>
                  <span className="gov-muted">#{n.id} · {n.type}</span>
                  <span className="gov-muted" style={{ marginLeft: "auto" }}>
                    {n.created_at ? new Date(n.created_at).toLocaleString() : "—"}
                  </span>
                </div>
                <p style={{ margin: "6px 0 0" }}>{n.message}</p>
                {!n.is_read ? (
                  <button
                    type="button"
                    className="gov-btn gov-btn-sm gov-btn-ghost"
                    style={{ marginTop: 6 }}
                    onClick={() => void onMarkRead(n.id)}
                    disabled={acting}
                  >
                    Mark as read
                  </button>
                ) : null}
              </li>
            ))}
          </ul>
        ) : null}
      </div>
    </div>
  );
}
