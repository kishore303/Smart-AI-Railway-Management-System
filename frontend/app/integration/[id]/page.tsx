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
  const [acting, setActing] = useState(false);
  const [actError, setActError] = useState<string | null>(null);
  const [confirming, setConfirming] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const r = await api.get<IntegrationRequest>(`/api/integration/requests/${integrationId}`);
      setData(r);
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
    setActing(true);
    setActError(null);
    try {
      const payload: Record<string, unknown> = { response };
      if (reason.trim() !== "") payload.reason = reason.trim().slice(0, 1000);
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
            Integration Request #{data.id}{" "}
            <span className={`gov-badge gov-badge-${integrationBadgeKind(data.final_status)}`}>{data.final_status}</span>
          </h2>
        </div>
      </div>

      <div className="gov-card">
        <div className="gov-section-header">
          <h3>Request Details</h3>
        </div>
        <div className="gov-kv-grid">
          <span className="gov-kv-label">Source Block</span>
          <span className="gov-kv-value"><Link className="gov-link" href={`/blocks/${data.source_block_id}`}>{data.source_block_id}</Link></span>
          <span className="gov-kv-label">Target Block</span>
          <span className="gov-kv-value"><Link className="gov-link" href={`/blocks/${data.target_block_id}`}>{data.target_block_id}</Link></span>
          <span className="gov-kv-label">Requesting Department</span>
          <span className="gov-kv-value">{data.requesting_department_code} (ID {data.requesting_department_id})</span>
          <span className="gov-kv-label">Target Department</span>
          <span className="gov-kv-value">{data.target_department_code} (ID {data.target_department_id})</span>
          <span className="gov-kv-label">Overlap</span>
          <span className="gov-kv-value">{data.overlap_duration_mins != null ? `${data.overlap_duration_mins} mins` : "—"}</span>
          <span className="gov-kv-label">Compatibility</span>
          <span className="gov-kv-value">
            {data.compatibility_status ? (
              <span className={`gov-badge gov-badge-${data.compatibility_status === "COMPATIBLE" ? "green" : data.compatibility_status === "INCOMPATIBLE" ? "red" : "amber"}`}>
                {data.compatibility_status}
              </span>
            ) : "—"}
          </span>
          <span className="gov-kv-label">Response</span>
          <span className="gov-kv-value">
            {data.response ? (
              <span className={`gov-badge gov-badge-${data.response === "ACCEPT" ? "green" : data.response === "REJECT" ? "red" : "amber"}`}>
                {data.response}
              </span>
            ) : "—"}
          </span>
          <span className="gov-kv-label">Reason</span>
          <span className="gov-kv-value">{data.reason ?? "—"}</span>
          <span className="gov-kv-label">Requested By</span>
          <span className="gov-kv-value">User #{data.requested_by}</span>
          <span className="gov-kv-label">Response By</span>
          <span className="gov-kv-value">{data.response_by != null ? `User #${data.response_by}` : "—"}</span>
          <span className="gov-kv-label">Created</span>
          <span className="gov-kv-value">{data.created_at ? new Date(data.created_at).toLocaleString() : "—"}</span>
        </div>
        <div className="gov-info-box" style={{ marginTop: 12 }}>
          {compatibilityNote(data.compatibility_status)}
        </div>
      </div>

      {pending ? (
        <div className="gov-card gov-card-accent">
          <div className="gov-section-header">
            <h3>Respond — Target Department Only</h3>
          </div>
          <div className="gov-info-box">
            Only the target department (or Authorized Official) may respond. The requester cannot
            respond to their own request — the backend enforces this.
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
                {r}
              </button>
            ))}
          </div>
          <label className="gov-label" htmlFor="int-resp-reason">Reason / Comments (optional)</label>
          <textarea
            id="int-resp-reason"
            className="gov-input"
            rows={3}
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
                Review {response}
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
            <h4>Cancel Request (Requester or Official)</h4>
          </div>
          <button className="gov-btn gov-btn-danger" onClick={() => void onCancel()} disabled={acting}>
            Cancel This Request
          </button>
        </div>
      ) : (
        <div className="gov-card gov-card-warning">
          <div className="gov-info-box">
            This request is {data.final_status} and can no longer be actioned.
            {data.final_status === "ACCEPTED" ? " Acceptance is a planning-level agreement — Safety Engine validation, optimization, and official approval are still required." : null}
          </div>
        </div>
      )}
    </div>
  );
}
