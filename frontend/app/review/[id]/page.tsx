"use client";

import React, { useCallback, useEffect, useState } from "react";
import { useParams } from "next/navigation";
import ProtectedRoute from "@/components/ProtectedRoute";
import AppShell from "@/components/AppShell";
import Breadcrumbs from "@/components/Breadcrumbs";
import { api, ApiError } from "@/lib/api-client";
import { useAuth } from "@/lib/auth-context";
import type { MaintenanceRequest } from "@/types/maintenance";
import { statusBadgeKind } from "@/types/maintenance";
import type { ReviewActionValue, ReviewHistoryItem } from "@/types/review";

export default function ReviewDetailPage() {
  return (
    <ProtectedRoute>
      <AppShell>
        <DetailContent />
      </AppShell>
    </ProtectedRoute>
  );
}

function fmt(dt: string | null): string {
  if (!dt) return "—";
  try {
    return new Date(dt).toLocaleString();
  } catch {
    return dt;
  }
}

function statusBadgeClass(status: string): string {
  const kind = statusBadgeKind(status);
  return `gov-badge gov-badge-${kind}`;
}

function actionBadgeClass(action: string): string {
  switch (action) {
    case "VERIFY":
    case "VERIFIED":
      return "gov-badge gov-badge-green";
    case "REJECT":
    case "REJECTED":
      return "gov-badge gov-badge-red";
    case "REVISION_REQUIRED":
      return "gov-badge gov-badge-amber";
    default:
      return "gov-badge gov-badge-blue";
  }
}

function DetailContent() {
  const params = useParams<{ id: string }>();
  const id = params.id;
  const { user } = useAuth();
  const [data, setData] = useState<MaintenanceRequest | null>(null);
  const [history, setHistory] = useState<ReviewHistoryItem[] | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [action, setAction] = useState<ReviewActionValue>("VERIFY");
  const [reason, setReason] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [starting, setStarting] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);
  const [actionSuccess, setActionSuccess] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const req = await api.get<MaintenanceRequest>(`/api/maintenance/requests/${id}`);
      setData(req);
      try {
        const h = await api.get<ReviewHistoryItem[]>(`/api/maintenance/requests/${id}/history`);
        setHistory(h);
      } catch {
        setHistory(null);
      }
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Unable to connect to the railway service. Please try again.");
    } finally {
      setLoading(false);
    }
  }, [id]);

  useEffect(() => {
    void load();
  }, [load]);

  const isOwnRequest = !!user && !!data && user.id === data.requested_by;
  const isReviewer = user?.role === "JUNIOR_ENGINEER" || user?.role === "SENIOR_SECTION_ENGINEER";
  const canAct = isReviewer && !isOwnRequest && data?.status === "UNDER_REVIEW";
  // The reviewer takes ownership via the transition endpoint; the backend still enforces role,
  // same-department and no-self-review rules.
  const canStartReview = isReviewer && !isOwnRequest && data?.status === "SUBMITTED";

  async function onStartReview() {
    if (starting) return;
    setActionError(null);
    setActionSuccess(null);
    setStarting(true);
    try {
      const res = await api.post<MaintenanceRequest>(`/api/maintenance/requests/${id}/transition`, {
        new_status: "UNDER_REVIEW",
      });
      setData(res);
      setActionSuccess("Review started — status is now UNDER_REVIEW. You may now VERIFY, REJECT or request revision.");
      try {
        const h = await api.get<ReviewHistoryItem[]>(`/api/maintenance/requests/${id}/history`);
        setHistory(h);
      } catch {
        // history is best-effort
      }
    } catch (err) {
      setActionError(err instanceof ApiError ? err.message : "Unable to connect to the railway service. Please try again.");
    } finally {
      setStarting(false);
    }
  }

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (submitting) return;
    setActionError(null);
    setActionSuccess(null);
    setSubmitting(true);
    try {
      const payload: Record<string, unknown> = { action };
      if (reason.trim() !== "") payload.reason = reason.trim();
      const res = await api.post<MaintenanceRequest>(`/api/maintenance/requests/${id}/review`, payload);
      setData(res);
      setReason("");
      setActionSuccess(`Request ${res.status === "VERIFIED" ? "verified" : res.status === "REJECTED" ? "rejected" : "sent for revision"} successfully.`);
      try {
        const h = await api.get<ReviewHistoryItem[]>(`/api/maintenance/requests/${id}/history`);
        setHistory(h);
      } catch {
        // history is best-effort
      }
    } catch (err) {
      setActionError(err instanceof ApiError ? err.message : "Unable to connect to the railway service. Please try again.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="gov-page">
      <Breadcrumbs
        trail={[
          { label: "Dashboard", href: "/dashboard" },
          { label: "Reviews", href: "/review" },
          { label: `Request ${id}` },
        ]}
      />

      <div className="gov-page-header">
        <div>
          <h2 className="gov-title">Review Request</h2>
          {data ? (
            <p className="gov-sub">
              <span className={statusBadgeClass(data.status)} style={{ marginRight: 8 }}>{data.status}</span>
              {data.request_code} — {data.maintenance_type}
            </p>
          ) : null}
        </div>
      </div>

      {loading ? (
        <div className="gov-card">
          <div className="gov-loading">Loading request details…</div>
        </div>
      ) : null}

      {error && !loading ? (
        <div className="gov-alert gov-alert-error" role="alert">{error}</div>
      ) : null}

      {!loading && !error && !data ? (
        <div className="gov-card">
          <div className="gov-empty">
            <p className="gov-muted">Request not found.</p>
          </div>
        </div>
      ) : null}

      {!loading && !error && data ? (
        <>
          <div className="gov-card">
            <div className="gov-section-header">
              <h3 className="gov-section-title">Request Details</h3>
            </div>
            <div className="gov-kv-grid">
              <div className="gov-kv-label">Request Code</div>
              <div className="gov-kv-value">{data.request_code}</div>

              <div className="gov-kv-label">Status</div>
              <div className="gov-kv-value">
                <span className={statusBadgeClass(data.status)}>{data.status}</span>
              </div>

              <div className="gov-kv-label">Maintenance Type</div>
              <div className="gov-kv-value">{data.maintenance_type}</div>

              <div className="gov-kv-label">Priority</div>
              <div className="gov-kv-value">{data.priority}</div>

              <div className="gov-kv-label">Department</div>
              <div className="gov-kv-value">{data.department_code}</div>

              <div className="gov-kv-label">Asset ID</div>
              <div className="gov-kv-value">{data.asset_id}</div>

              <div className="gov-kv-label">Section ID</div>
              <div className="gov-kv-value">{data.section_id}</div>

              <div className="gov-kv-label">Track ID</div>
              <div className="gov-kv-value">{data.track_id ?? "—"}</div>

              <div className="gov-kv-label">Requested Start</div>
              <div className="gov-kv-value">{fmt(data.requested_start)}</div>

              <div className="gov-kv-label">Requested End</div>
              <div className="gov-kv-value">{fmt(data.requested_end)}</div>

              <div className="gov-kv-label">Description</div>
              <div className="gov-kv-value">{data.description ?? "—"}</div>
            </div>
          </div>

          <div className={`gov-card ${!canAct ? "gov-card-warning" : "gov-card-accent"}`}>
            <div className="gov-section-header">
              <h3 className="gov-section-title">Review Action</h3>
            </div>

            {isOwnRequest ? (
              <div className="gov-alert gov-alert-error" role="alert">
                You cannot review your own request. Self-review is prohibited; the backend will reject such attempts.
              </div>
            ) : null}

            {!isReviewer ? (
              <div className="gov-alert gov-alert-error" role="alert">
                Only users with Junior Engineer (JE) or Senior Section Engineer (SSE) role can perform review actions.
              </div>
            ) : null}

            {canStartReview ? (
              <div className="gov-info-box">
                This request is <strong>SUBMITTED</strong> and awaiting reviewer take-up.
                <div className="gov-form-actions">
                  <button className="gov-btn" type="button" onClick={() => void onStartReview()} disabled={starting || submitting}>
                    {starting ? "Starting review…" : "Start Review"}
                  </button>
                </div>
              </div>
            ) : null}

            {isReviewer && !isOwnRequest && data.status !== "UNDER_REVIEW" && data.status !== "SUBMITTED" ? (
              <div className="gov-info-box">
                Review actions require the request to be UNDER_REVIEW. Current status: <strong>{data.status}</strong>.
              </div>
            ) : null}

            <form onSubmit={onSubmit}>
              <label className="gov-label" htmlFor="review-action">Action</label>
              <select
                id="review-action"
                className="gov-select"
                value={action}
                onChange={(e) => setAction(e.target.value as ReviewActionValue)}
                disabled={!canAct || submitting}
              >
                <option value="VERIFY">VERIFY</option>
                <option value="REJECT">REJECT</option>
                <option value="REVISION_REQUIRED">REVISION_REQUIRED</option>
              </select>

              <label className="gov-label" htmlFor="review-reason">
                Reason / Comment {action === "VERIFY" ? "(optional)" : "(recommended)"}
              </label>
              <textarea
                id="review-reason"
                className="gov-input"
                rows={3}
                maxLength={1000}
                value={reason}
                onChange={(e) => setReason(e.target.value)}
                disabled={!canAct || submitting}
                placeholder={
                  action === "REJECT"
                    ? "Rejection reason…"
                    : action === "REVISION_REQUIRED"
                      ? "Revision notes…"
                      : "Optional comment…"
                }
              />

              {actionError ? (
                <div className="gov-alert gov-alert-error" role="alert">{actionError}</div>
              ) : null}

              {actionSuccess ? (
                <div className="gov-alert gov-alert-success" role="status">{actionSuccess}</div>
              ) : null}

              <div className="gov-form-actions">
                <button className="gov-btn" type="submit" disabled={!canAct || submitting}>
                  {submitting ? "Submitting…" : `Submit ${action}`}
                </button>
              </div>
            </form>
          </div>

          <div className="gov-card">
            <div className="gov-section-header">
              <h3 className="gov-section-title">Review History &amp; Audit Timeline</h3>
            </div>

            {!history || !Array.isArray(history) ? (
              <div className="gov-info-box">History is unavailable for this request.</div>
            ) : null}

            {Array.isArray(history) && history.length === 0 ? (
              <div className="gov-empty">
                <p className="gov-muted">No history entries recorded.</p>
              </div>
            ) : null}

            {Array.isArray(history) && history.length > 0 ? (
              <div className="gov-table-wrap">
                <table className="gov-table">
                  <thead>
                    <tr>
                      <th>Time</th>
                      <th>Action</th>
                      <th>Reviewer</th>
                      <th>Change</th>
                      <th>Detail</th>
                    </tr>
                  </thead>
                  <tbody>
                    {history.map((h) => (
                      <tr key={h.id}>
                        <td>{fmt(h.created_at)}</td>
                        <td>
                          <span className={actionBadgeClass(h.action)}>{h.action}</span>
                        </td>
                        <td>{h.user_name ? `${h.user_name} (${h.user_role ?? ""})` : h.user_id ?? "—"}</td>
                        <td>{h.old_status || h.new_status ? `${h.old_status ?? "—"} → ${h.new_status ?? "—"}` : "—"}</td>
                        <td>{h.description ?? "—"}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : null}
          </div>
        </>
      ) : null}
    </div>
  );
}
