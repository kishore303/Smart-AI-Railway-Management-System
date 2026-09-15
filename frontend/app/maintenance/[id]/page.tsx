"use client";

import React, { useCallback, useEffect, useState } from "react";
import { useParams } from "next/navigation";
import ProtectedRoute from "@/components/ProtectedRoute";
import AppShell from "@/components/AppShell";
import Breadcrumbs from "@/components/Breadcrumbs";
import { api, ApiError } from "@/lib/api-client";
import type { MaintenanceRequest, ReviewHistoryItem } from "@/types/maintenance";
import { statusBadgeKind } from "@/types/maintenance";

export default function MaintenanceDetailPage() {
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

function DetailContent() {
  const params = useParams<{ id: string }>();
  const id = params.id;
  const [data, setData] = useState<MaintenanceRequest | null>(null);
  const [history, setHistory] = useState<ReviewHistoryItem[] | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [actionLoading, setActionLoading] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);
  const [newStatus, setNewStatus] = useState("SUBMITTED");
  const [reason, setReason] = useState("");
  const [editDesc, setEditDesc] = useState("");
  const [editPriority, setEditPriority] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const req = await api.get<MaintenanceRequest>(`/api/maintenance/requests/${id}`);
      setData(req);
      setEditDesc(req.description ?? "");
      setEditPriority(req.priority);
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

  async function onTransition(e: React.FormEvent) {
    e.preventDefault();
    if (actionLoading) return;
    setActionError(null);
    setActionLoading(true);
    try {
      const res = await api.post<MaintenanceRequest>(`/api/maintenance/requests/${id}/transition`, {
        new_status: newStatus,
        reason: reason.trim() === "" ? undefined : reason.trim(),
      });
      setData(res);
      setReason("");
      const h = await api.get<ReviewHistoryItem[]>(`/api/maintenance/requests/${id}/history`).catch(() => null);
      if (h) setHistory(h);
    } catch (err) {
      setActionError(err instanceof ApiError ? err.message : "Unable to connect to the railway service. Please try again.");
    } finally {
      setActionLoading(false);
    }
  }

  async function onUpdate(e: React.FormEvent) {
    e.preventDefault();
    if (actionLoading) return;
    setActionError(null);
    setActionLoading(true);
    try {
      const res = await api.patch<MaintenanceRequest>(`/api/maintenance/requests/${id}`, {
        description: editDesc,
        priority: editPriority || undefined,
      });
      setData(res);
    } catch (err) {
      setActionError(err instanceof ApiError ? err.message : "Unable to connect to the railway service. Please try again.");
    } finally {
      setActionLoading(false);
    }
  }

  const statusKind = data ? statusBadgeKind(data.status) : "amber";

  return (
    <div className="gov-page">
      <Breadcrumbs
        trail={[
          { label: "Dashboard", href: "/dashboard" },
          { label: "Maintenance Requests", href: "/maintenance" },
          { label: `Request ${id}` },
        ]}
      />

      <div className="gov-page-header">
        <div>
          <h2 className="gov-title">Maintenance Request Details</h2>
          {data ? (
            <p className="gov-sub">
              <span className={`gov-badge gov-badge-${statusKind}`}>{data.status}</span>
              {" · "}
              {data.request_code}
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
          {/* Request Overview */}
          <div className={`gov-card gov-card-accent`}>
            <div className="gov-section-header">
              <h3 className="gov-section-title">Request Overview</h3>
            </div>
            <div className="gov-kv-grid">
              <div className="gov-kv-label">Request Code</div>
              <div className="gov-kv-value">{data.request_code}</div>

              <div className="gov-kv-label">Status</div>
              <div className="gov-kv-value">
                <span className={`gov-badge gov-badge-${statusKind}`}>{data.status}</span>
              </div>

              <div className="gov-kv-label">Maintenance Type</div>
              <div className="gov-kv-value">{data.maintenance_type}</div>

              <div className="gov-kv-label">Priority</div>
              <div className="gov-kv-value">{data.priority}</div>

              <div className="gov-kv-label">Description</div>
              <div className="gov-kv-value">{data.description ?? "—"}</div>
            </div>
          </div>

          {/* Schedule */}
          <div className="gov-card gov-card-success">
            <div className="gov-section-header">
              <h3 className="gov-section-title">Schedule</h3>
            </div>
            <div className="gov-kv-grid">
              <div className="gov-kv-label">Requested Start</div>
              <div className="gov-kv-value">{fmt(data.requested_start)}</div>

              <div className="gov-kv-label">Requested End</div>
              <div className="gov-kv-value">{fmt(data.requested_end)}</div>

              <div className="gov-kv-label">Duration (mins)</div>
              <div className="gov-kv-value">{data.requested_duration_mins ?? "—"}</div>
            </div>
          </div>

          {/* Location & Department */}
          <div className="gov-card gov-card-warning">
            <div className="gov-section-header">
              <h3 className="gov-section-title">Location &amp; Department</h3>
            </div>
            <div className="gov-kv-grid">
              <div className="gov-kv-label">Asset ID</div>
              <div className="gov-kv-value">{data.asset_id}</div>

              <div className="gov-kv-label">Section ID</div>
              <div className="gov-kv-value">{data.section_id}</div>

              <div className="gov-kv-label">Track ID</div>
              <div className="gov-kv-value">{data.track_id ?? "—"}</div>

              <div className="gov-kv-label">Department</div>
              <div className="gov-kv-value">{data.department_code}</div>

              <div className="gov-kv-label">Requested By (User ID)</div>
              <div className="gov-kv-value">{data.requested_by}</div>

              <div className="gov-kv-label">Reviewed By</div>
              <div className="gov-kv-value">{data.reviewed_by ?? "—"}</div>

              <div className="gov-kv-label">Rejection Reason</div>
              <div className="gov-kv-value">{data.rejection_reason ?? "—"}</div>

              <div className="gov-kv-label">Revision Notes</div>
              <div className="gov-kv-value">{data.revision_notes ?? "—"}</div>

              <div className="gov-kv-label">Created</div>
              <div className="gov-kv-value">{fmt(data.created_at)}</div>

              <div className="gov-kv-label">Updated</div>
              <div className="gov-kv-value">{fmt(data.updated_at)}</div>
            </div>
          </div>

          {/* Status Transition */}
          <div className="gov-card">
            <div className="gov-section-header">
              <h3 className="gov-section-title">Status Transition</h3>
            </div>
            <div className="gov-info-box">
              Allowed transitions are enforced by the backend. Unauthorized or skipped transitions return an error.
            </div>
            <form onSubmit={onTransition} style={{ display: "flex", gap: 12, flexWrap: "wrap", alignItems: "end" }}>
              <div>
                <label className="gov-label" htmlFor="new-status">New Status</label>
                <select id="new-status" className="gov-select" value={newStatus} onChange={(e) => setNewStatus(e.target.value)}>
                  {["SUBMITTED", "UNDER_REVIEW", "VERIFIED", "REJECTED", "REVISION_REQUIRED", "BLOCK_PLANNING", "AI_RECOMMENDATION", "OFFICIAL_REVIEW", "APPROVED", "MODIFIED"].map((s) => (
                    <option key={s} value={s}>{s}</option>
                  ))}
                </select>
              </div>
              <div style={{ flex: 1, minWidth: 220 }}>
                <label className="gov-label" htmlFor="reason">Reason (if required)</label>
                <input id="reason" className="gov-input" value={reason} onChange={(e) => setReason(e.target.value)} maxLength={1000} />
              </div>
              <button className="gov-btn gov-btn-sm" type="submit" disabled={actionLoading}>
                {actionLoading ? "Submitting…" : "Change Status"}
              </button>
            </form>
          </div>

          {/* Update (Owner) */}
          <div className="gov-card">
            <div className="gov-section-header">
              <h3 className="gov-section-title">Update (Owner, DRAFT / REVISION_REQUIRED only)</h3>
            </div>
            <form onSubmit={onUpdate}>
              <label className="gov-label" htmlFor="edit-desc">Description</label>
              <textarea id="edit-desc" className="gov-input" rows={3} maxLength={2000} value={editDesc} onChange={(e) => setEditDesc(e.target.value)} />
              <label className="gov-label" htmlFor="edit-priority">Priority</label>
              <select id="edit-priority" className="gov-select" value={editPriority} onChange={(e) => setEditPriority(e.target.value)}>
                <option value="LOW">LOW</option>
                <option value="MEDIUM">MEDIUM</option>
                <option value="HIGH">HIGH</option>
                <option value="CRITICAL">CRITICAL</option>
              </select>
              <div className="gov-form-actions">
                <button className="gov-btn" type="submit" disabled={actionLoading}>
                  {actionLoading ? "Saving…" : "Save Changes"}
                </button>
              </div>
            </form>
            {actionError ? (
              <div className="gov-alert gov-alert-error" role="alert">{actionError}</div>
            ) : null}
          </div>

          {/* History */}
          <div className="gov-card">
            <div className="gov-section-header">
              <h3 className="gov-section-title">History</h3>
            </div>
            {!history ? <p className="gov-muted">History is unavailable for this request.</p> : null}
            {history && history.length === 0 ? <p className="gov-muted">No history entries recorded.</p> : null}
            {history && history.length > 0 ? (
              <div className="gov-table-wrap">
                <table className="gov-table">
                  <thead>
                    <tr>
                      <th>Time</th>
                      <th>Action</th>
                      <th>Actor</th>
                      <th>Change</th>
                      <th>Detail</th>
                    </tr>
                  </thead>
                  <tbody>
                    {history.map((h) => (
                      <tr key={h.id}>
                        <td>{fmt(h.created_at)}</td>
                        <td>{h.action}</td>
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
