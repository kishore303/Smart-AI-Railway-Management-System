"use client";

import React, { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import ProtectedRoute from "@/components/ProtectedRoute";
import AppShell from "@/components/AppShell";
import Breadcrumbs from "@/components/Breadcrumbs";
import { api, ApiError } from "@/lib/api-client";
import { useAuth } from "@/lib/auth-context";
import type { ReviewQueueResponse } from "@/types/review";
import { statusBadgeKind } from "@/types/maintenance";

const STATUS_FILTERS = ["", "SUBMITTED", "UNDER_REVIEW"];

function statusBadgeClass(status: string): string {
  const kind = statusBadgeKind(status);
  return `gov-badge gov-badge-${kind}`;
}

export default function ReviewQueuePage() {
  return (
    <ProtectedRoute>
      <AppShell>
        <QueueContent />
      </AppShell>
    </ProtectedRoute>
  );
}

function QueueContent() {
  const { user } = useAuth();
  const [data, setData] = useState<ReviewQueueResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [status, setStatus] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const params = new URLSearchParams({ skip: "0", limit: "20" });
      if (status) params.set("status", status);
      const res = await api.get<ReviewQueueResponse>(`/api/maintenance/review/queue?${params.toString()}`);
      setData(res);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Unable to connect to the railway service. Please try again.");
    } finally {
      setLoading(false);
    }
  }, [status]);

  useEffect(() => {
    void load();
  }, [load]);

  const isReviewer = user?.role === "JUNIOR_ENGINEER" || user?.role === "SENIOR_SECTION_ENGINEER";

  return (
    <div className="gov-page">
      <Breadcrumbs trail={[{ label: "Dashboard", href: "/dashboard" }, { label: "Reviews" }]} />

      <div className="gov-page-header">
        <div>
          <h2 className="gov-title">Review Queue</h2>
          <p className="gov-sub">
            Maintenance requests awaiting technical verification in your department (Junior Engineer &amp; Senior Section Engineer).
          </p>
        </div>
      </div>

      {!isReviewer && !loading ? (
        <div className="gov-alert gov-alert-error" role="alert">
          Only users with the Junior Engineer (JE) or Senior Section Engineer (SSE) role can access the review queue.
        </div>
      ) : null}

      <div className="gov-card" style={{ marginBottom: 12 }}>
        <form
          onSubmit={(e) => {
            e.preventDefault();
            void load();
          }}
        >
          <div className="gov-filter-bar">
            <div>
              <label className="gov-label" htmlFor="rq-status">Status</label>
              <select id="rq-status" className="gov-select" value={status} onChange={(e) => setStatus(e.target.value)}>
                {STATUS_FILTERS.map((s) => (
                  <option key={s} value={s}>{s === "" ? "SUBMITTED + UNDER_REVIEW" : s}</option>
                ))}
              </select>
            </div>
            <button className="gov-btn gov-btn-secondary gov-btn-sm" type="submit">
              Apply Filter
            </button>
          </div>
        </form>
      </div>

      {loading ? (
        <div className="gov-card">
          <div className="gov-loading">Loading review queue…</div>
        </div>
      ) : null}

      {error && !loading ? (
        <div className="gov-alert gov-alert-error" role="alert">{error}</div>
      ) : null}

      {!loading && !error && data && (data.items ?? []).length === 0 ? (
        <div className="gov-card">
          <div className="gov-empty">
            <p className="gov-muted">No maintenance requests are currently awaiting review.</p>
          </div>
        </div>
      ) : null}

      {!loading && !error && data && (data.items ?? []).length > 0 ? (
        <div className="gov-card">
          <div className="gov-card-header">
            <h3 className="gov-section-title" style={{ margin: 0 }}>Requests</h3>
            <span className="gov-muted">Total: {data.total ?? (data.items ?? []).length}</span>
          </div>
          <div className="gov-table-wrap">
            <table className="gov-table">
              <thead>
                <tr>
                  <th>Request Code</th>
                  <th>Type</th>
                  <th>Priority</th>
                  <th>Status</th>
                  <th>Requested Start</th>
                  <th>Review</th>
                </tr>
              </thead>
              <tbody>
                {(data.items ?? []).map((r) => (
                  <tr key={r.id}>
                    <td style={{ fontWeight: 600 }}>{r.request_code}</td>
                    <td>{r.maintenance_type}</td>
                    <td>{r.priority}</td>
                    <td>
                      <span className={statusBadgeClass(r.status)}>{r.status}</span>
                    </td>
                    <td>{r.requested_start ? new Date(r.requested_start).toLocaleString() : "—"}</td>
                    <td>
                      <Link className="gov-link" href={`/review/${r.id}`}>
                        Review
                      </Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      ) : null}
    </div>
  );
}
