"use client";

import React, { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import ProtectedRoute from "@/components/ProtectedRoute";
import AppShell from "@/components/AppShell";
import Breadcrumbs from "@/components/Breadcrumbs";
import SafetyChecksTable from "@/components/SafetyChecksTable";
import { api, ApiError } from "@/lib/api-client";
import { useAuth } from "@/lib/auth-context";
import type { OfficialDecisionResponse, Recommendation } from "@/types/recommendations";
import { decisionBadgeKind } from "@/types/recommendations";
import { safetyBadgeKind } from "@/types/safety";

export default function RecommendationDetailPage() {
  const params = useParams<{ id: string }>();
  const id = params.id;
  return (
    <ProtectedRoute>
      <AppShell>
        <DetailContent optimizedId={id} />
      </AppShell>
    </ProtectedRoute>
  );
}

function decisionError(err: unknown): string {
  if (err instanceof ApiError) {
    if (err.status === 403) {
      const m = err.message.toLowerCase();
      if (m.includes("self")) return err.message;
      return "You are not authorized to approve this recommendation.";
    }
    if (err.status === 409) {
      return `Integration state changed. Revalidation/reoptimization is required before approval. (${err.message})`;
    }
    return err.message;
  }
  return "Unable to connect to the railway service. Please try again.";
}

function DetailContent({ optimizedId }: { optimizedId: string }) {
  const { user } = useAuth();
  const isOfficial = user?.role === "AUTHORIZED_OFFICIAL";

  const [rec, setRec] = useState<Recommendation | null>(null);
  const [explanation, setExplanation] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [action, setAction] = useState<"approve" | "reject" | "modify">("approve");
  const [reason, setReason] = useState("");
  const [newCand, setNewCand] = useState("");
  const [newStart, setNewStart] = useState("");
  const [newEnd, setNewEnd] = useState("");
  const [acting, setActing] = useState(false);
  const [actError, setActError] = useState<string | null>(null);
  const [decision, setDecision] = useState<OfficialDecisionResponse | null>(null);
  const [confirming, setConfirming] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const r = await api.get<Recommendation>(`/api/recommendations/${optimizedId}`);
      setRec(r);
      try {
        const ex = await api.get<{ explanation: string }>(`/api/recommendations/${optimizedId}/explanation`);
        setExplanation(ex.explanation);
      } catch {
        setExplanation(null);
      }
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Unable to connect to the railway service. Please try again.");
    } finally {
      setLoading(false);
    }
  }, [optimizedId]);

  useEffect(() => {
    void load();
  }, [load]);

  async function submitDecision() {
    if (acting) return;
    if (action === "reject" && reason.trim() === "") {
      setActError("A rejection reason is required.");
      return;
    }
    setActing(true);
    setActError(null);
    try {
      const payload: Record<string, unknown> = {};
      if (reason.trim() !== "") payload.reason = reason.trim().slice(0, 1000);
      if (action === "modify") {
        if (newCand.trim() !== "") payload.new_candidate_id = Number(newCand);
        if (newStart !== "") payload.new_start_time = new Date(newStart).toISOString();
        if (newEnd !== "") payload.new_end_time = new Date(newEnd).toISOString();
      }
      const res = await api.post<OfficialDecisionResponse>(
        `/api/recommendations/${optimizedId}/${action}`,
        payload
      );
      setDecision(res);
      setConfirming(false);
      await load();
    } catch (err) {
      setActError(decisionError(err));
    } finally {
      setActing(false);
    }
  }

  if (loading) {
    return (
      <div className="gov-page">
        <Breadcrumbs trail={[{ label: "Dashboard", href: "/dashboard" }, { label: "Recommendations", href: "/recommendations" }, { label: `#${optimizedId}` }]} />
        <div className="gov-card"><div className="gov-loading">Loading recommendation…</div></div>
      </div>
    );
  }

  if (error || !rec) {
    return (
      <div className="gov-page">
        <Breadcrumbs trail={[{ label: "Dashboard", href: "/dashboard" }, { label: "Recommendations", href: "/recommendations" }, { label: `#${optimizedId}` }]} />
        <div className="gov-card">
          <div className="gov-alert gov-alert-error" role="alert">{error ?? "Recommendation not found."}</div>
        </div>
      </div>
    );
  }

  const safety = rec.safety_summary;
  const sel = rec.selected_recommendation;

  return (
    <div className="gov-page">
      <Breadcrumbs
        trail={[
          { label: "Dashboard", href: "/dashboard" },
          { label: "Recommendations", href: "/recommendations" },
          { label: rec.block_code },
        ]}
      />

      <div className="gov-page-header">
        <div>
          <h2 className="gov-title">
            Recommendation {rec.block_code}{" "}
            <span className={`gov-badge gov-badge-${decisionBadgeKind(rec.status)}`}>{rec.status}</span>
          </h2>
          <p className="gov-sub">
            Optimization recommends; the Safety Engine validates; only an Authorized Official approves.
            SAFE does not mean approved.
          </p>
        </div>
      </div>

      <div className={`gov-alert gov-alert-${rec.is_eligible_for_approval ? "success" : "error"}`} role="status">
        <strong>
          {rec.is_eligible_for_approval
            ? "Eligible for official approval review"
            : "Not currently eligible for approval"}
        </strong>
        {rec.eligibility_reasons.length > 0 ? (
          <ul className="gov-list" style={{ marginTop: 8 }}>
            {rec.eligibility_reasons.map((r, i) => <li key={i}>{r}</li>)}
          </ul>
        ) : null}
      </div>

      {decision ? (
        <div className="gov-card gov-card-accent" style={{ marginTop: 12 }}>
          <div className="gov-section-header">
            <h3>Decision Recorded — {decision.decision}</h3>
          </div>
          <div className="gov-kv-grid">
            <span className="gov-kv-label">New Status</span>
            <span className="gov-kv-value">{decision.new_status}</span>
            <span className="gov-kv-label">Decided By</span>
            <span className="gov-kv-value">User #{decision.decided_by}</span>
            <span className="gov-kv-label">Decided At</span>
            <span className="gov-kv-value">{new Date(decision.decided_at).toLocaleString()}</span>
            <span className="gov-kv-label">Reason</span>
            <span className="gov-kv-value">{decision.reason ?? "—"}</span>
            <span className="gov-kv-label">Requires Revalidation</span>
            <span className="gov-kv-value">
              <span className={`gov-badge gov-badge-${decision.requires_revalidation ? "amber" : "green"}`}>
                {decision.requires_revalidation ? "Yes" : "No"}
              </span>
            </span>
            <span className="gov-kv-label">Requires Reoptimization</span>
            <span className="gov-kv-value">
              <span className={`gov-badge gov-badge-${decision.requires_reoptimization ? "amber" : "green"}`}>
                {decision.requires_reoptimization ? "Yes" : "No"}
              </span>
            </span>
          </div>
          {(decision.requires_revalidation || decision.requires_reoptimization) ? (
            <div className="gov-info-box" style={{ marginTop: 12 }}>
              Modification invalidated prior results — revalidation and reoptimization are required
              before this recommendation can be approved.
            </div>
          ) : null}
        </div>
      ) : null}

      <div className="gov-card">
        <div className="gov-section-header">
          <h3>Request Summary</h3>
        </div>
        <div className="gov-kv-grid">
          <span className="gov-kv-label">Maintenance Request</span>
          <span className="gov-kv-value">{rec.request_summary.request_code ?? rec.request_summary.maintenance_request_id ?? "—"}</span>
          <span className="gov-kv-label">Department</span>
          <span className="gov-kv-value">{rec.request_summary.department_code ?? "—"}</span>
          <span className="gov-kv-label">Asset</span>
          <span className="gov-kv-value">{rec.request_summary.asset_code ?? rec.request_summary.asset_id ?? "—"}</span>
          <span className="gov-kv-label">Section</span>
          <span className="gov-kv-value">{rec.request_summary.section_code ?? rec.request_summary.section_id ?? "—"}</span>
          <span className="gov-kv-label">Track</span>
          <span className="gov-kv-value">{rec.request_summary.track_code ?? rec.request_summary.track_id ?? "—"}</span>
          <span className="gov-kv-label">Type / Priority</span>
          <span className="gov-kv-value">{rec.request_summary.maintenance_type ?? "—"} / {rec.request_summary.priority ?? "—"}</span>
        </div>
      </div>

      <div className="gov-card">
        <div className="gov-section-header">
          <h3>
            Safety Summary{" "}
            {safety.overall_status ? (
              <span className={`gov-badge gov-badge-${safetyBadgeKind(safety.overall_status)}`}>{safety.overall_status}</span>
            ) : <span className="gov-badge gov-badge-amber">Not validated</span>}
          </h3>
        </div>
        <div className="gov-kv-grid">
          <span className="gov-kv-label">Candidate</span>
          <span className="gov-kv-value">
            {safety.candidate_id != null ? (
              <Link className="gov-link" href={`/safety/${safety.candidate_id}`}>{safety.candidate_id}</Link>
            ) : "—"}
          </span>
          <span className="gov-kv-label">Safe for Optimization</span>
          <span className="gov-kv-value">
            {safety.is_safe_for_optimization == null ? "—" : (
              <span className={`gov-badge gov-badge-${safety.is_safe_for_optimization ? "green" : "red"}`}>
                {safety.is_safe_for_optimization ? "Yes" : "No"}
              </span>
            )}
          </span>
          <span className="gov-kv-label">Planning Status</span>
          <span className="gov-kv-value">{safety.planning_safety_status ?? "—"}</span>
          <span className="gov-kv-label">Validated At</span>
          <span className="gov-kv-value">{safety.validated_at ? new Date(safety.validated_at).toLocaleString() : "—"}</span>
          <span className="gov-kv-label">Validated By</span>
          <span className="gov-kv-value">{safety.validated_by ? `User #${safety.validated_by}` : "—"}</span>
        </div>
        {safety.rejection_reasons && safety.rejection_reasons.length > 0 ? (
          <div className="gov-alert gov-alert-error" role="alert" style={{ marginTop: 12 }}>
            <ul className="gov-list" style={{ margin: 0 }}>
              {safety.rejection_reasons.map((r, i) => <li key={i}>{r}</li>)}
            </ul>
          </div>
        ) : null}
        {safety.warnings && safety.warnings.length > 0 ? (
          <div className="gov-info-box">Warnings: {safety.warnings.join("; ")}</div>
        ) : null}
        <div className="gov-section-header" style={{ marginTop: 16 }}>
          <h4>Safety Checks ({safety.checks?.length ?? 0})</h4>
        </div>
        <SafetyChecksTable checks={safety.checks} />
      </div>

      <div className="gov-card">
        <div className="gov-section-header">
          <h3>Optimization Result (OR-Tools, Backend)</h3>
        </div>
        <div className="gov-kv-grid">
          <span className="gov-kv-label">Optimization Score</span>
          <span className="gov-kv-value">{rec.optimization_summary.optimization_score ?? "—"}</span>
          <span className="gov-kv-label">Selected Candidate</span>
          <span className="gov-kv-value">{sel?.candidate_id ?? "—"}</span>
          <span className="gov-kv-label">Window</span>
          <span className="gov-kv-value">
            {sel?.candidate_start ? new Date(sel.candidate_start).toLocaleString() : "—"}
            {" → "}
            {sel?.candidate_end ? new Date(sel.candidate_end).toLocaleString() : "—"}
          </span>
          <span className="gov-kv-label">Predicted Duration</span>
          <span className="gov-kv-value">{sel?.predicted_duration_mins ?? "—"}</span>
          <span className="gov-kv-label">Predicted Delay</span>
          <span className="gov-kv-value">
            {sel?.predicted_delay_mins != null ? (
              <span className={`gov-badge gov-badge-${sel.predicted_delay_mins === 0 ? "green" : sel.predicted_delay_mins <= 10 ? "amber" : "red"}`}>
                {sel.predicted_delay_mins} mins
              </span>
            ) : "—"}
          </span>
          <span className="gov-kv-label">Asset Risk</span>
          <span className="gov-kv-value">{sel?.asset_risk_score ?? "—"}</span>
        </div>
        {explanation ? (
          <div style={{ marginTop: 12 }}>
            <div className="gov-section-header">
              <h4>Decision-Support Rationale (Backend)</h4>
            </div>
            <p>{explanation}</p>
          </div>
        ) : null}
        {rec.optimization_summary.explanation ? (
          <div className="gov-info-box" style={{ marginTop: 12 }}>Optimizer note: {rec.optimization_summary.explanation}</div>
        ) : null}
      </div>

      {rec.alternatives.length > 0 ? (
        <div className="gov-card">
          <div className="gov-section-header">
            <h3>Alternatives Considered ({rec.alternatives.length})</h3>
          </div>
          <div className="gov-table-wrap">
            <table className="gov-table">
              <thead><tr><th>Candidate</th><th>Window</th><th>Safety</th><th>Eligible</th><th>Why Not Selected</th></tr></thead>
              <tbody>
                {rec.alternatives.map((a) => (
                  <tr key={a.candidate_id}>
                    <td><Link className="gov-link" href={`/safety/${a.candidate_id}`}>{a.candidate_id}</Link></td>
                    <td>
                      {a.candidate_start ? new Date(a.candidate_start).toLocaleString() : "—"}
                      {" → "}
                      {a.candidate_end ? new Date(a.candidate_end).toLocaleString() : "—"}
                    </td>
                    <td>
                      {a.safety_overall ?? a.safety_status ? (
                        <span className={`gov-badge gov-badge-${safetyBadgeKind(a.safety_overall ?? a.safety_status ?? "")}`}>
                          {a.safety_overall ?? a.safety_status ?? "—"}
                        </span>
                      ) : "—"}
                    </td>
                    <td>
                      <span className={`gov-badge gov-badge-${a.optimization_eligible ? "green" : "red"}`}>
                        {a.optimization_eligible ? "Yes" : "No"}
                      </span>
                    </td>
                    <td>{a.reason_not_selected}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      ) : null}

      {rec.integration_summary.length > 0 ? (
        <div className="gov-card">
          <div className="gov-section-header">
            <h3>Cross-Department Integration ({rec.integration_summary.length})</h3>
          </div>
          <div className="gov-table-wrap">
            <table className="gov-table">
              <thead><tr><th>ID</th><th>Blocks</th><th>Departments</th><th>Compatibility</th><th>Final</th></tr></thead>
              <tbody>
                {rec.integration_summary.map((g) => (
                  <tr key={g.integration_id}>
                    <td>{g.integration_id}</td>
                    <td>{g.source_block} ↔ {g.target_block}</td>
                    <td>{g.requesting_dept} → {g.target_dept}</td>
                    <td>
                      {g.compatibility_status ? (
                        <span className={`gov-badge gov-badge-${g.compatibility_status === "COMPATIBLE" ? "green" : g.compatibility_status === "INCOMPATIBLE" ? "red" : "amber"}`}>
                          {g.compatibility_status}
                        </span>
                      ) : "—"}
                    </td>
                    <td>
                      {g.final_status ? (
                        <span className={`gov-badge gov-badge-${g.final_status === "ACCEPTED" ? "green" : g.final_status === "REJECTED" ? "red" : "amber"}`}>
                          {g.final_status}
                        </span>
                      ) : "—"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      ) : null}

      {rec.warnings.length > 0 ? (
        <div className="gov-card gov-card-warning">
          <div className="gov-section-header">
            <h3>Warnings ({rec.warnings.length})</h3>
          </div>
          <ul className="gov-list">
            {rec.warnings.map((w, i) => <li key={i}>{w}</li>)}
          </ul>
        </div>
      ) : null}

      <div className="gov-card gov-card-danger">
        <div className="gov-section-header">
          <h3>Official Decision — Authorized Official Only</h3>
        </div>
        <div className="gov-info-box">
          <strong>Final decision authority: Authorized Railway Official</strong><br />
          Review the safety status, planning status, and selected candidate above before deciding.
          The requester cannot approve their own request — the backend blocks self-approval.
        </div>
        {!isOfficial ? (
          <div className="gov-alert gov-alert-error" role="alert" style={{ marginTop: 12 }}>
            Approval actions are available to AUTHORIZED_OFFICIAL accounts only. You are signed in
            as {user?.role ?? "unknown"}. Backend role enforcement remains authoritative.
          </div>
        ) : (
          <>
            <div className="gov-tabs" style={{ marginTop: 12 }}>
              {(["approve", "reject", "modify"] as const).map((a) => (
                <button
                  key={a}
                  type="button"
                  className={`gov-tab${action === a ? " active" : ""}`}
                  onClick={() => {
                    setAction(a);
                    setConfirming(false);
                    setActError(null);
                  }}
                >
                  {a === "approve" ? "Approve" : a === "reject" ? "Reject" : "Modify"}
                </button>
              ))}
            </div>
            <label className="gov-label" htmlFor="dec-reason">
              Reason / Comments {action === "reject" ? "*" : "(optional)"}
            </label>
            <textarea
              id="dec-reason"
              className="gov-input"
              rows={3}
              value={reason}
              onChange={(e) => setReason(e.target.value)}
              placeholder={action === "reject" ? "Rejection reason (required)" : "Decision comments"}
            />
            {action === "modify" ? (
              <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit,minmax(200px,1fr))", gap: 12, marginTop: 12 }}>
                <div>
                  <label className="gov-label" htmlFor="dec-cand">New Candidate ID (optional)</label>
                  <input id="dec-cand" className="gov-input" inputMode="numeric" value={newCand} onChange={(e) => setNewCand(e.target.value)} placeholder="Same block only" />
                </div>
                <div>
                  <label className="gov-label" htmlFor="dec-start">New Start (optional)</label>
                  <input id="dec-start" className="gov-input" type="datetime-local" value={newStart} onChange={(e) => setNewStart(e.target.value)} />
                </div>
                <div>
                  <label className="gov-label" htmlFor="dec-end">New End (optional)</label>
                  <input id="dec-end" className="gov-input" type="datetime-local" value={newEnd} onChange={(e) => setNewEnd(e.target.value)} />
                </div>
              </div>
            ) : null}
            {action === "modify" ? (
              <div className="gov-info-box" style={{ marginTop: 12 }}>
                Modification invalidates prior safety and optimization results — revalidation and
                reoptimization will be required before approval.
              </div>
            ) : null}
            {actError ? <div className="gov-alert gov-alert-error" role="alert" style={{ marginTop: 12 }}>{actError}</div> : null}
            {!confirming ? (
              <div className="gov-btn-group">
                <button
                  className={`gov-btn${action === "reject" ? " gov-btn-danger" : action === "approve" ? " gov-btn-success" : ""}`}
                  onClick={() => {
                    setActError(null);
                    if (action === "reject" && reason.trim() === "") {
                      setActError("A rejection reason is required.");
                      return;
                    }
                    setConfirming(true);
                  }}
                >
                  Review {action === "approve" ? "Approval" : action === "reject" ? "Rejection" : "Modification"}
                </button>
              </div>
            ) : (
              <div className="gov-alert gov-alert-error" role="alert" style={{ marginTop: 12 }}>
                <p>
                  <strong>Confirm {action} of {rec.block_code}?</strong> Safety: {safety.overall_status ?? "unknown"}.
                  This decision is recorded with your user ID and cannot be undone from this page.
                </p>
                <div className="gov-btn-group" style={{ marginTop: 8 }}>
                  <button className={`gov-btn${action === "reject" ? " gov-btn-danger" : action === "approve" ? " gov-btn-success" : ""}`} onClick={() => void submitDecision()} disabled={acting}>
                    {acting ? "Submitting…" : `Confirm ${action}`}
                  </button>
                  <button className="gov-btn gov-btn-secondary" onClick={() => setConfirming(false)} disabled={acting}>
                    Cancel
                  </button>
                </div>
              </div>
            )}
          </>
        )}
      </div>

      {rec.decision_history.length > 0 ? (
        <div className="gov-card">
          <div className="gov-section-header">
            <h3>Decision History ({rec.decision_history.length})</h3>
          </div>
          <div className="gov-table-wrap">
            <table className="gov-table">
              <thead><tr><th>Action</th><th>User</th><th>Description</th><th>At</th></tr></thead>
              <tbody>
                {rec.decision_history.map((h, i) => (
                  <tr key={i}>
                    <td><span className={`gov-badge gov-badge-${h.action === "APPROVE" ? "green" : h.action === "REJECT" ? "red" : "blue"}`}>{h.action}</span></td>
                    <td>{h.user_id != null ? `User #${h.user_id}` : "—"}</td>
                    <td>{h.description ?? "—"}</td>
                    <td>{h.created_at ? new Date(h.created_at).toLocaleString() : "—"}</td>
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
