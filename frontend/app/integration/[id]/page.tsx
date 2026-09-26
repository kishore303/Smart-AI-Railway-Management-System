"use client";

import React, { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import ProtectedRoute from "@/components/ProtectedRoute";
import AppShell from "@/components/AppShell";
import Breadcrumbs from "@/components/Breadcrumbs";
import { api, ApiError } from "@/lib/api-client";
import type { IntegrationRequest, IntegrationResponse } from "@/types/integration";
import { compatibilityNote, integrationBadgeKind } from "@/types/integration";

export default function IntegrationDetailPage() {
  const params = useParams<{ id: string }>();
  const id = params.id;
  return (
    <ProtectedRoute>
      <AppShell>
        <DetailContent integrationId={id} />
      </AppShell>
    </ProtectedRoute>
  );
}

function DetailContent({ integrationId }: { integrationId: string }) {
  const [data, setData] = useState<IntegrationRequest | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [response, setResponse] = useState<IntegrationResponse>("ACCEPT");
  const [reason, setReason] = useState("");
  const [modifiedStart, setModifiedStart] = useState("");
  const [modifiedEnd, setModifiedEnd] = useState("");
  const [acting, setActing] = useState(false);
  const [actError, setActError] = useState<string | null>(null);
  const [confirming, setConfirming] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const r = await api.get<IntegrationRequest>(`/api/integration/requests/${integrationId}`);
      setData(r);
      if (r.modified_start) setModifiedStart(r.modified_start.slice(0, 16));
      if (r.modified_end) setModifiedEnd(r.modified_end.slice(0, 16));
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Unable to connect to the railway service. Please try again.");
    } finally {
      setLoading(false);
    }
  }, [integrationId]);

  useEffect(() => {
    void load();
  }, [load]);

  async function submitRespond() {
    if (acting) return;
    if (response === "REJECT" && !reason.trim()) {
      setActError("Rejection reason is mandatory. Please state why coordination is not possible.");
      return;
    }
    if (response === "MODIFY" && (!modifiedStart || !modifiedEnd)) {
      setActError("Proposed modified start and end times are required for a MODIFY response.");
      return;
    }
    setActing(true);
    setActError(null);
    try {
      const payload: Record<string, unknown> = { response };
      if (reason.trim() !== "") payload.reason = reason.trim().slice(0, 1000);
      if (response === "MODIFY") {
        payload.modified_start = new Date(modifiedStart).toISOString();
        payload.modified_end = new Date(modifiedEnd).toISOString();
      }
      const r = await api.post<IntegrationRequest>(`/api/integration/requests/${integrationId}/respond`, payload);
      setData(r);
      setConfirming(false);
    } catch (err) {
      setActError(err instanceof ApiError ? err.message : "Unable to connect to the railway service. Please try again.");
    } finally {
      setActing(false);
    }
  }

  async function onCancel() {
    if (acting) return;
    setActing(true);
    setActError(null);
    try {
      const r = await api.post<IntegrationRequest>(`/api/integration/requests/${integrationId}/cancel`, {});
      setData(r);
      setConfirming(false);
    } catch (err) {
      setActError(err instanceof ApiError ? err.message : "Unable to connect to the railway service. Please try again.");
    } finally {
      setActing(false);
    }
  }

  if (loading) {
    return (
      <div className="gov-page">
        <Breadcrumbs trail={[{ label: "Dashboard", href: "/dashboard" }, { label: "Department Integration", href: "/integration" }, { label: `#${integrationId}` }]} />
        <div className="gov-card"><div className="gov-loading">Loading integration request…</div></div>
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="gov-page">
        <Breadcrumbs trail={[{ label: "Dashboard", href: "/dashboard" }, { label: "Department Integration", href: "/integration" }, { label: `#${integrationId}` }]} />
        <div className="gov-card">
          <div className="gov-alert gov-alert-error" role="alert">{error ?? "Integration request not found."}</div>
        </div>
      </div>
    );
  }

  const pending = data.final_status === "PENDING";

  return (
    <div className="gov-page">
      <Breadcrumbs
        trail={[
          { label: "Dashboard", href: "/dashboard" },
          { label: "Department Integration", href: "/integration" },
          { label: `Request #${data.id}` },
        ]}
      />

      <div className="gov-page-header">
        <div>
          <h2 className="gov-title">
            Coordination Request #{data.id}{" "}
            <span className={`gov-badge gov-badge-${integrationBadgeKind(data.final_status)}`}>{data.final_status}</span>
          </h2>
          <p className="gov-subtitle">Cross-departmental block integration and window synchronization review.</p>
        </div>
      </div>

      <div className="gov-card">
        <div className="gov-section-header">
          <h3>Coordination & Asset Parameters</h3>
          {data.coordination_score != null && (
            <span className="gov-badge gov-badge-info" style={{ fontSize: "0.85rem" }}>
              Match Score: {data.coordination_score}%
            </span>
          )}
        </div>
        <div className="gov-kv-grid">
          <span className="gov-kv-label">Source Request</span>
          <span className="gov-kv-value">
            <Link className="gov-link" href={`/blocks/${data.source_block_id}`}>
              {data.source_block_code ?? `Block #${data.source_block_id}`}
            </Link>{" "}
            ({data.requesting_department_code})
          </span>

          <span className="gov-kv-label">Target Request</span>
          <span className="gov-kv-value">
            <Link className="gov-link" href={`/blocks/${data.target_block_id}`}>
              {data.target_block_code ?? `Block #${data.target_block_id}`}
            </Link>{" "}
            ({data.target_department_code})
          </span>

          <span className="gov-kv-label">Section / Track</span>
          <span className="gov-kv-value">
            {data.section_id != null ? `Section #${data.section_id}` : "Universal / Unknown"} &bull;{" "}
            {data.track_id != null ? `Track #${data.track_id}` : "Unassigned"}
          </span>

          <span className="gov-kv-label">Spatial Co-location</span>
          <span className="gov-kv-value">
            {data.spatial_status ? (
              <span className={`gov-badge gov-badge-${data.spatial_status === "SAME_TRACK" ? "green" : data.spatial_status === "ADJACENT_TRACK" ? "amber" : "info"}`}>
                {data.spatial_status.replace(/_/g, " ")}
              </span>
            ) : "—"}
          </span>

          <span className="gov-kv-label">Overlap Duration</span>
          <span className="gov-kv-value font-semibold">
            {data.overlap_duration_mins != null ? `${data.overlap_duration_mins} mins` : "—"}
          </span>

          <span className="gov-kv-label">Preliminary Status</span>
          <span className="gov-kv-value">
            {data.compatibility_status ? (
              <span className={`gov-badge gov-badge-${data.compatibility_status === "COMPATIBLE" ? "green" : data.compatibility_status === "INCOMPATIBLE" ? "red" : "amber"}`}>
                {data.compatibility_status}
              </span>
            ) : "—"}
          </span>

          {data.detection_reason && (
            <>
              <span className="gov-kv-label">Detection Basis</span>
              <span className="gov-kv-value text-muted" style={{ gridColumn: "span 3" }}>{data.detection_reason}</span>
            </>
          )}

          {data.modified_start && (
            <>
              <span className="gov-kv-label">Proposed Modified Window</span>
              <span className="gov-kv-value" style={{ gridColumn: "span 3" }}>
                {new Date(data.modified_start).toLocaleString()} &rarr; {data.modified_end ? new Date(data.modified_end).toLocaleString() : "—"}
              </span>
            </>
          )}

          <span className="gov-kv-label">Response Decision</span>
          <span className="gov-kv-value">
            {data.response ? (
              <span className={`gov-badge gov-badge-${data.response === "ACCEPT" ? "green" : data.response === "REJECT" ? "red" : "amber"}`}>
                {data.response}
              </span>
            ) : "—"}
          </span>

          <span className="gov-kv-label">Comments / Notes</span>
          <span className="gov-kv-value">{data.reason ?? "—"}</span>

          <span className="gov-kv-label">Requested By</span>
          <span className="gov-kv-value">User #{data.requested_by}</span>

          <span className="gov-kv-label">Responded By</span>
          <span className="gov-kv-value">{data.response_by != null ? `User #${data.response_by}` : "—"}</span>

          <span className="gov-kv-label">Created At</span>
          <span className="gov-kv-value">{data.created_at ? new Date(data.created_at).toLocaleString() : "—"}</span>
        </div>
        <div className="gov-info-box" style={{ marginTop: 12 }}>
          {compatibilityNote(data.compatibility_status)}
        </div>
      </div>

      {pending ? (
        <div className="gov-card gov-card-accent">
          <div className="gov-section-header">
            <h3>Department Review & Coordination Action</h3>
          </div>
          <div className="gov-info-box">
            Only authorized personnel from <strong>{data.target_department_code}</strong> (or Authorized Officials) may respond. The requesting department cannot approve its own proposal.
          </div>
          <div className="gov-tabs" style={{ marginTop: 12 }}>
            {(["ACCEPT", "REJECT", "MODIFY"] as IntegrationResponse[]).map((r) => (
              <button
                key={r}
                type="button"
                className={`gov-tab${response === r ? " active" : ""}`}
                onClick={() => {
                  setResponse(r);
                  setConfirming(false);
                  setActError(null);
                }}
              >
                {r === "ACCEPT" ? "Accept Coordination" : r === "REJECT" ? "Reject Coordination" : "Propose Modified Window"}
              </button>
            ))}
          </div>

          {response === "MODIFY" && (
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "1rem", marginTop: 12 }}>
              <div>
                <label className="gov-label" htmlFor="mod-start">Proposed Start Time *</label>
                <input
                  id="mod-start"
                  type="datetime-local"
                  className="gov-input"
                  value={modifiedStart}
                  onChange={(e) => setModifiedStart(e.target.value)}
                  required
                />
              </div>
              <div>
                <label className="gov-label" htmlFor="mod-end">Proposed End Time *</label>
                <input
                  id="mod-end"
                  type="datetime-local"
                  className="gov-input"
                  value={modifiedEnd}
                  onChange={(e) => setModifiedEnd(e.target.value)}
                  required
                />
              </div>
            </div>
          )}

          <label className="gov-label" htmlFor="int-resp-reason" style={{ marginTop: 12 }}>
            {response === "REJECT" ? "Reason for Rejection (Mandatory) *" : response === "MODIFY" ? "Modification Rationale *" : "Reason / Operational Notes (Optional)"}
          </label>
          <textarea
            id="int-resp-reason"
            className="gov-input"
            rows={3}
            placeholder={
              response === "REJECT"
                ? "State operational or equipment incompatibility reason..."
                : response === "MODIFY"
                ? "Explain why the modified time window is needed..."
                : "Add notes regarding joint possession, gang deployment, or power shutoff..."
            }
            value={reason}
            onChange={(e) => setReason(e.target.value)}
            maxLength={1000}
          />
          {actError ? <div className="gov-alert gov-alert-error" role="alert" style={{ marginTop: 12 }}>{actError}</div> : null}
          {!confirming ? (
            <div className="gov-btn-group">
              <button
                className={`gov-btn${response === "REJECT" ? " gov-btn-danger" : response === "ACCEPT" ? " gov-btn-success" : ""}`}
                onClick={() => {
                  setActError(null);
                  setConfirming(true);
                }}
              >
                Review & Confirm {response}
              </button>
            </div>
          ) : (
            <div className="gov-alert gov-alert-error" role="alert" style={{ marginTop: 12 }}>
              <p><strong>Confirm {response} of integration request #{data.id}?</strong></p>
              <div className="gov-btn-group" style={{ marginTop: 8 }}>
                <button className={`gov-btn${response === "REJECT" ? " gov-btn-danger" : response === "ACCEPT" ? " gov-btn-success" : ""}`} onClick={() => void submitRespond()} disabled={acting}>
                  {acting ? "Submitting…" : `Confirm ${response}`}
                </button>
                <button className="gov-btn gov-btn-secondary" onClick={() => setConfirming(false)} disabled={acting}>
                  Cancel
                </button>
              </div>
            </div>
          )}
          <hr className="gov-divider" />
          <div className="gov-section-header">
            <h4>Withdraw Request (Requester or Official)</h4>
          </div>
          <button className="gov-btn gov-btn-danger" onClick={() => void onCancel()} disabled={acting}>
            Cancel / Withdraw This Request
          </button>
        </div>
      ) : (
        <div className="gov-card gov-card-warning">
          <div className="gov-info-box">
            This request is <strong>{data.final_status}</strong> and can no longer be actioned.
            {data.final_status === "ACCEPTED" ? " Note: Acceptance represents a planning-level coordination agreement. Formal safety isolation, OR-Tools corridor optimization, and Operating Department authorization will follow in downstream stages." : null}
          </div>
        </div>
      )}
    </div>
  );
}

