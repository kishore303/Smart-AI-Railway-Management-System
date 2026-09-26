"use client";

import React, { useEffect, useState, useCallback } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import ProtectedRoute from "@/components/ProtectedRoute";
import AppShell from "@/components/AppShell";
import Breadcrumbs from "@/components/Breadcrumbs";
import RailwayMap from "@/components/RailwayMap";
import { api, ApiError } from "@/lib/api-client";
import { useAuth } from "@/lib/auth-context";
import type { PendingApprovalItem, DecisionResult } from "@/types/approval";

export default function ApprovalDetailPage() {
  const params = useParams<{ id: string }>();
  const id = params.id;

  return (
    <ProtectedRoute>
      <AppShell>
        <ApprovalDetailContent optimizedId={id} />
      </AppShell>
    </ProtectedRoute>
  );
}

function ApprovalDetailContent({ optimizedId }: { optimizedId: string }) {
  const router = useRouter();
  const { user } = useAuth();
  const isOfficial = user?.role === "AUTHORIZED_OFFICIAL";

  const [detail, setDetail] = useState<PendingApprovalItem | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Decision Modal State
  const [decisionType, setDecisionType] = useState<"APPROVE" | "MODIFY" | "REJECT" | null>(null);
  const [reason, setReason] = useState("");
  const [newStart, setNewStart] = useState("");
  const [newEnd, setNewEnd] = useState("");
  const [newCandidateId, setNewCandidateId] = useState<string>("");
  const [submitting, setSubmitting] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);
  const [actionSuccess, setActionSuccess] = useState<string | null>(null);

  const loadData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await api.get<PendingApprovalItem>(`/api/approval/${optimizedId}`);
      setDetail(res);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to load approval details.");
    } finally {
      setLoading(false);
    }
  }, [optimizedId]);

  useEffect(() => {
    void loadData();
  }, [loadData]);

  async function handleDecisionSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!decisionType || submitting) return;

    if (decisionType === "REJECT" && !reason.trim()) {
      setActionError("A mandatory rejection reason is required.");
      return;
    }

    setSubmitting(true);
    setActionError(null);
    setActionSuccess(null);

    try {
      let endpoint = `/api/approval/${optimizedId}/approve`;
      const payload: Record<string, any> = { reason: reason.trim() };

      if (decisionType === "MODIFY") {
        endpoint = `/api/approval/${optimizedId}/modify`;
        if (newCandidateId) payload.new_candidate_id = Number(newCandidateId);
        if (newStart) payload.new_start_time = new Date(newStart).toISOString();
        if (newEnd) payload.new_end_time = new Date(newEnd).toISOString();
        payload.proposed_changes = reason.trim();
      } else if (decisionType === "REJECT") {
        endpoint = `/api/approval/${optimizedId}/reject`;
      }

      const res = await api.post<DecisionResult>(endpoint, payload);
      setActionSuccess(`Decision ${res.decision} executed successfully. Block status is now ${res.new_status}.`);
      setDecisionType(null);
      await loadData();
    } catch (err) {
      setActionError(
        err instanceof ApiError
          ? err.message
          : "An unexpected error occurred while recording your decision."
      );
    } finally {
      setSubmitting(false);
    }
  }

  if (loading) {
    return (
      <div className="gov-page">
        <p style={{ color: "#64748b" }}>Loading block recommendation details...</p>
      </div>
    );
  }

  if (error || !detail) {
    return (
      <div className="gov-page">
        <div className="gov-alert gov-alert-danger">{error || "Block recommendation not found."}</div>
        <Link href="/approval-center" className="gov-btn gov-btn-secondary" style={{ marginTop: "16px" }}>
          ← Back to Approval Center
        </Link>
      </div>
    );
  }

  return (
    <div className="gov-page">
      <Breadcrumbs
        trail={[
          { label: "Dashboard", href: "/dashboard" },
          { label: "Approval Center", href: "/approval-center" },
          { label: detail.block_code },
        ]}
      />

      {/* Header */}
      <div className="gov-page-header" style={{ marginBottom: "20px" }}>
        <div>
          <div style={{ display: "flex", alignItems: "center", gap: "12px", marginBottom: "4px" }}>
            <h2 className="gov-title" style={{ margin: 0 }}>{detail.block_code}</h2>
            <span className={`gov-badge ${detail.status === "APPROVED" || detail.status === "SCHEDULED" ? "gov-badge-success" : detail.status === "REJECTED" ? "gov-badge-danger" : "gov-badge-warning"}`}>
              {detail.status}
            </span>
            {detail.ownership.is_integrated && (
              <span className="gov-badge gov-badge-info">Multi-Department Integrated</span>
            )}
          </div>
          <p className="gov-sub" style={{ margin: 0 }}>
            Comprehensive 12-Section Decision Review for Railway Authorized Officials
          </p>
        </div>

        {isOfficial && (
          <div style={{ display: "flex", gap: "10px" }}>
            <button
              onClick={() => { setDecisionType("APPROVE"); setReason(""); }}
              className="gov-btn gov-btn-primary"
              style={{ background: "#16a34a", borderColor: "#15803d" }}
            >
              ✓ Approve Block
            </button>
            <button
              onClick={() => { setDecisionType("MODIFY"); setReason(""); }}
              className="gov-btn gov-btn-secondary"
              style={{ background: "#eab308", color: "#854d0e", borderColor: "#ca8a04" }}
            >
              ✎ Modify
            </button>
            <button
              onClick={() => { setDecisionType("REJECT"); setReason(""); }}
              className="gov-btn gov-btn-danger"
            >
              ✕ Reject
            </button>
          </div>
        )}
      </div>

      {actionSuccess && (
        <div className="gov-alert gov-alert-success" style={{ marginBottom: "20px" }}>
          {actionSuccess}
        </div>
      )}
      {actionError && (
        <div className="gov-alert gov-alert-danger" style={{ marginBottom: "20px" }}>
          {actionError}
        </div>
      )}

      {/* 12-Section Grid Layout */}
      <div style={{ display: "grid", gridTemplateColumns: "2fr 1fr", gap: "24px" }}>
        {/* Left Column: Sections 1 to 9 */}
        <div style={{ display: "flex", flexDirection: "column", gap: "20px" }}>
          
          {/* SECTION 1: Maintenance Request Summary */}
          <div className="gov-card">
            <h3 style={{ fontSize: "1.05rem", fontWeight: 700, borderBottom: "1px solid #e2e8f0", paddingBottom: "8px", marginBottom: "12px", color: "#1e3a8a" }}>
              1. Maintenance Request Summary
            </h3>
            <div className="gov-grid gov-grid-3">
              <div>
                <span className="gov-stat-label">Request Code</span>
                <strong>{detail.maintenance_request.request_code}</strong>
              </div>
              <div>
                <span className="gov-stat-label">Department</span>
                <strong>{detail.maintenance_request.department}</strong>
              </div>
              <div>
                <span className="gov-stat-label">Requester</span>
                <span>{detail.maintenance_request.requester_name}</span>
              </div>
              <div>
                <span className="gov-stat-label">Maintenance Type</span>
                <strong>{detail.maintenance_request.maintenance_type}</strong>
              </div>
              <div>
                <span className="gov-stat-label">Priority</span>
                <span style={{ color: detail.maintenance_request.priority === "HIGH" ? "#dc2626" : "#2563eb", fontWeight: 600 }}>
                  {detail.maintenance_request.priority}
                </span>
              </div>
              <div>
                <span className="gov-stat-label">Requested Duration</span>
                <span>{detail.maintenance_request.requested_duration_mins} mins</span>
              </div>
            </div>
            <div style={{ marginTop: "10px", fontSize: "0.9rem", color: "#475569" }}>
              <strong>Description:</strong> {detail.maintenance_request.description || "No additional description provided."}
            </div>
          </div>

          {/* SECTION 2 & 3: Department Ownership & Asset */}
          <div className="gov-grid gov-grid-2">
            <div className="gov-card">
              <h3 style={{ fontSize: "1.05rem", fontWeight: 700, borderBottom: "1px solid #e2e8f0", paddingBottom: "8px", marginBottom: "12px", color: "#1e3a8a" }}>
                2. Department Ownership
              </h3>
              <p style={{ margin: "4px 0" }}><strong>Lead Dept:</strong> {detail.ownership.primary_department}</p>
              <p style={{ margin: "4px 0" }}>
                <strong>Confirmed Participating:</strong> {detail.ownership.participating_departments.join(", ")}
              </p>
              <p style={{ margin: "4px 0", fontSize: "0.85rem", color: "#64748b" }}>
                {detail.ownership.is_integrated ? "✓ Accepted Phase 4 Cross-Department Opportunity" : "Single Department Maintenance"}
              </p>
            </div>

            <div className="gov-card">
              <h3 style={{ fontSize: "1.05rem", fontWeight: 700, borderBottom: "1px solid #e2e8f0", paddingBottom: "8px", marginBottom: "12px", color: "#1e3a8a" }}>
                3. Asset Details
              </h3>
              <p style={{ margin: "4px 0" }}><strong>Code:</strong> {detail.asset.asset_code} ({detail.asset.asset_type})</p>
              <p style={{ margin: "4px 0" }}><strong>Name:</strong> {detail.asset.name}</p>
              <p style={{ margin: "4px 0" }}>
                <strong>Health Score:</strong> {Math.round(detail.asset.health_score * 100)}% | <strong>Criticality:</strong> {detail.asset.criticality}
              </p>
            </div>
          </div>

          {/* SECTION 4: AI Predictions & Model Traceability */}
          <div className="gov-card">
            <h3 style={{ fontSize: "1.05rem", fontWeight: 700, borderBottom: "1px solid #e2e8f0", paddingBottom: "8px", marginBottom: "12px", color: "#1e3a8a" }}>
              4. AI / ML Predictions & Model Traceability
            </h3>
            <div className="gov-grid gov-grid-4" style={{ marginBottom: "12px" }}>
              <div style={{ background: "#f8fafc", padding: "10px", borderRadius: "6px" }}>
                <span className="gov-stat-label">Operational Risk</span>
                <strong style={{ color: "#dc2626", fontSize: "1.1rem" }}>{detail.ai_predictions.operational_risk}</strong>
                <span style={{ fontSize: "0.8rem", color: "#64748b", display: "block" }}>
                  Confidence: {Math.round(detail.ai_predictions.risk_probability * 100)}%
                </span>
              </div>
              <div style={{ background: "#f8fafc", padding: "10px", borderRadius: "6px" }}>
                <span className="gov-stat-label">Predicted Duration</span>
                <strong style={{ fontSize: "1.1rem" }}>{detail.ai_predictions.predicted_duration_mins} mins</strong>
              </div>
              <div style={{ background: "#f8fafc", padding: "10px", borderRadius: "6px" }}>
                <span className="gov-stat-label">Affected Trains</span>
                <strong style={{ fontSize: "1.1rem" }}>{detail.ai_predictions.affected_train_count} Trains</strong>
              </div>
              <div style={{ background: "#f8fafc", padding: "10px", borderRadius: "6px" }}>
                <span className="gov-stat-label">Total Train Delay</span>
                <strong style={{ fontSize: "1.1rem", color: "#d97706" }}>{detail.ai_predictions.total_predicted_delay_mins} mins</strong>
              </div>
            </div>
            <div style={{ fontSize: "0.8rem", color: "#64748b", background: "#f1f5f9", padding: "8px 12px", borderRadius: "4px" }}>
              <strong>Model Pipelines:</strong> {detail.ai_predictions.model_metadata.train_delay_model} ({detail.ai_predictions.model_metadata.version}) • Status: {detail.ai_predictions.model_metadata.prediction_status}
            </div>
          </div>

          {/* SECTION 5: Affected Trains */}
          <div className="gov-card">
            <h3 style={{ fontSize: "1.05rem", fontWeight: 700, borderBottom: "1px solid #e2e8f0", paddingBottom: "8px", marginBottom: "12px", color: "#1e3a8a" }}>
              5. Train Impact Analysis ({detail.affected_trains.length} Trains)
            </h3>
            {detail.affected_trains.length === 0 ? (
              <p style={{ color: "#16a34a", fontSize: "0.9rem" }}>✓ Zero train traffic conflicts detected in timetable for this window.</p>
            ) : (
              <table className="gov-table" style={{ width: "100%" }}>
                <thead>
                  <tr>
                    <th>Train #</th>
                    <th>Train Name</th>
                    <th>Section</th>
                    <th>Scheduled</th>
                    <th>Delay</th>
                    <th>Impact Status</th>
                  </tr>
                </thead>
                <tbody>
                  {detail.affected_trains.map((t, idx) => (
                    <tr key={idx}>
                      <td><strong>{t.train_number}</strong></td>
                      <td>{t.train_name}</td>
                      <td>{t.section_code}</td>
                      <td>{t.scheduled_time}</td>
                      <td style={{ color: "#d97706", fontWeight: 600 }}>+{t.predicted_delay_mins} min</td>
                      <td><span className="gov-badge gov-badge-warning">{t.impact_status}</span></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>

          {/* SECTION 6: Safety Engine Validation */}
          <div className="gov-card">
            <h3 style={{ fontSize: "1.05rem", fontWeight: 700, borderBottom: "1px solid #e2e8f0", paddingBottom: "8px", marginBottom: "12px", color: "#1e3a8a" }}>
              6. Deterministic Safety Engine Validation
            </h3>
            <div style={{ display: "flex", alignItems: "center", gap: "10px", marginBottom: "12px" }}>
              <span className={`gov-badge ${detail.safety_validation.overall_status === "SAFE" ? "gov-badge-success" : "gov-badge-danger"}`} style={{ fontSize: "1rem", padding: "6px 14px" }}>
                Overall Safety: {detail.safety_validation.overall_status}
              </span>
              <span style={{ fontSize: "0.85rem", color: "#64748b" }}>
                {detail.safety_validation.is_safe_for_optimization ? "✓ Hard Safety Gate Passed" : "✕ Excluded from Optimization"}
              </span>
            </div>
            <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: "8px" }}>
              {Object.entries(detail.safety_validation.checks).map(([checkName, rawResult]) => {
                const result = typeof rawResult === "string"
                  ? rawResult
                  : (rawResult as any)?.status || (rawResult as any)?.result || ((rawResult as any)?.passed ? "PASS" : "FAIL") || JSON.stringify(rawResult);
                const isPass = result === "PASS" || result === "PASSED" || result === "SAFE";
                const isWarn = result === "WARNING" || result === "WARN";
                return (
                  <div key={checkName} style={{ display: "flex", justifyContent: "space-between", padding: "6px 10px", background: "#f8fafc", borderRadius: "4px", fontSize: "0.85rem" }}>
                    <span style={{ textTransform: "capitalize", color: "#475569" }}>{checkName.replace(/_/g, " ")}</span>
                    <strong style={{ color: isPass ? "#16a34a" : isWarn ? "#d97706" : "#dc2626" }}>
                      {result}
                    </strong>
                  </div>
                );
              })}
            </div>
          </div>

          {/* SECTION 7: Candidate Comparison */}
          <div className="gov-card">
            <h3 style={{ fontSize: "1.05rem", fontWeight: 700, borderBottom: "1px solid #e2e8f0", paddingBottom: "8px", marginBottom: "12px", color: "#1e3a8a" }}>
              7. Candidate Alternatives & Rejected Windows
            </h3>
            <table className="gov-table" style={{ width: "100%", fontSize: "0.85rem" }}>
              <thead>
                <tr>
                  <th>Window</th>
                  <th>Duration</th>
                  <th>Trains</th>
                  <th>Delay</th>
                  <th>Safety</th>
                  <th>Status / Reason</th>
                </tr>
              </thead>
              <tbody>
                {detail.candidate_comparison.safe_alternatives.map((c) => (
                  <tr key={c.candidate_id} style={{ background: c.is_selected ? "#eff6ff" : "transparent" }}>
                    <td><strong>{c.window}</strong> {c.is_selected && "⭐ Recommended"}</td>
                    <td>{c.duration_mins}m</td>
                    <td>{c.affected_train_count}</td>
                    <td>{c.predicted_delay_mins}m</td>
                    <td><span className="gov-badge gov-badge-success">SAFE</span></td>
                    <td>{c.is_selected ? "Optimal Window" : "Alternative Safe Window"}</td>
                  </tr>
                ))}
                {detail.candidate_comparison.rejected_candidates.map((c) => (
                  <tr key={c.candidate_id} style={{ opacity: 0.75 }}>
                    <td>{c.window}</td>
                    <td>{c.duration_mins}m</td>
                    <td>{c.affected_train_count}</td>
                    <td>{c.predicted_delay_mins}m</td>
                    <td><span className="gov-badge gov-badge-danger">UNSAFE</span></td>
                    <td style={{ color: "#dc2626" }}>
                      {typeof c.rejection_reason === "string" ? c.rejection_reason : (c.rejection_reason as any)?.message || JSON.stringify(c.rejection_reason || "Unsafe candidate")}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* SECTION 8: OR-Tools Optimization */}
          <div className="gov-card">
            <h3 style={{ fontSize: "1.05rem", fontWeight: 700, borderBottom: "1px solid #e2e8f0", paddingBottom: "8px", marginBottom: "12px", color: "#1e3a8a" }}>
              8. Google OR-Tools CP-SAT Optimization Result
            </h3>
            <div className="gov-grid gov-grid-3" style={{ marginBottom: "12px" }}>
              <div>
                <span className="gov-stat-label">Solver Status</span>
                <strong style={{ color: "#16a34a" }}>{detail.optimization.solver_status}</strong>
              </div>
              <div>
                <span className="gov-stat-label">Optimization Score</span>
                <strong style={{ fontSize: "1.2rem", color: "#2563eb" }}>{detail.optimization.optimization_score}/100</strong>
              </div>
              <div>
                <span className="gov-stat-label">Config Version</span>
                <span>{detail.optimization.config_version}</span>
              </div>
            </div>
            <div style={{ background: "#f8fafc", padding: "12px", borderRadius: "6px", fontSize: "0.9rem", color: "#334155" }}>
              <strong>Optimization Rationale:</strong> {detail.optimization.explanation}
            </div>
          </div>

          {/* SECTION 9 & 10: Cross-Dept & Resources */}
          <div className="gov-grid gov-grid-2">
            <div className="gov-card">
              <h3 style={{ fontSize: "1.05rem", fontWeight: 700, borderBottom: "1px solid #e2e8f0", paddingBottom: "8px", marginBottom: "12px", color: "#1e3a8a" }}>
                9. Cross-Department Coordination
              </h3>
              {detail.cross_department.integrations.length === 0 ? (
                <p style={{ color: "#64748b", fontSize: "0.9rem" }}>No integrated requests for this block.</p>
              ) : (
                detail.cross_department.integrations.map((i) => (
                  <div key={i.integration_id} style={{ fontSize: "0.85rem", marginBottom: "6px" }}>
                    <span>{i.source_department} ↔ {i.target_department}</span>
                    <span className="gov-badge gov-badge-success" style={{ marginLeft: "8px" }}>{i.final_status}</span>
                  </div>
                ))
              )}
            </div>

            <div className="gov-card">
              <h3 style={{ fontSize: "1.05rem", fontWeight: 700, borderBottom: "1px solid #e2e8f0", paddingBottom: "8px", marginBottom: "12px", color: "#1e3a8a" }}>
                10. Resource Allocations
              </h3>
              {detail.resources.allocations.map((r, idx) => (
                <div key={idx} style={{ fontSize: "0.85rem", marginBottom: "6px" }}>
                  <strong>{r.resource_name}</strong> ({r.resource_type}) x{r.quantity}
                  <span className="gov-badge gov-badge-info" style={{ marginLeft: "6px" }}>{r.status}</span>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* Right Column: Sections 11 & 12 (Map & Decision Panel) */}
        <div style={{ display: "flex", flexDirection: "column", gap: "20px" }}>
          
          {/* SECTION 11: Railway Map Context */}
          <div className="gov-card" style={{ padding: "16px" }}>
            <h3 style={{ fontSize: "1.05rem", fontWeight: 700, borderBottom: "1px solid #e2e8f0", paddingBottom: "8px", marginBottom: "12px", color: "#1e3a8a" }}>
              11. Section & Track Visualization
            </h3>
            <p style={{ fontSize: "0.85rem", color: "#64748b", margin: "0 0 10px 0" }}>
              Section: <strong>{detail.map_context.section_code}</strong> | Track: <strong>{detail.map_context.track_code}</strong>
            </p>
            <div style={{ height: "260px", borderRadius: "6px", overflow: "hidden" }}>
              <RailwayMap height={260} layers={["sections", "tracks", "stations"]} />
            </div>
          </div>

          {/* SECTION 12: Decision Summary & Confirmation */}
          <div className="gov-card" style={{ borderTop: "4px solid #1e3a8a", background: "#f8fafc" }}>
            <h3 style={{ fontSize: "1.1rem", fontWeight: 700, marginBottom: "12px", color: "#1e3a8a" }}>
              12. Authoritative Official Decision
            </h3>
            
            <div style={{ fontSize: "0.9rem", color: "#475569", marginBottom: "16px" }}>
              <p style={{ margin: "4px 0" }}><strong>Recommended Window:</strong> {detail.optimization.recommended_window}</p>
              <p style={{ margin: "4px 0" }}><strong>Duration:</strong> {detail.optimization.duration_mins} mins</p>
              <p style={{ margin: "4px 0" }}><strong>Safety Status:</strong> {detail.safety_validation.overall_status}</p>
              <p style={{ margin: "4px 0" }}><strong>Current Status:</strong> {detail.status}</p>
            </div>

            {isOfficial ? (
              <div style={{ display: "flex", flexDirection: "column", gap: "10px" }}>
                <button
                  onClick={() => { setDecisionType("APPROVE"); setReason(""); }}
                  className="gov-btn gov-btn-primary"
                  style={{ width: "100%", background: "#16a34a", borderColor: "#15803d", padding: "12px" }}
                >
                  ✓ Authorize & Schedule Block
                </button>
                <button
                  onClick={() => { setDecisionType("MODIFY"); setReason(""); }}
                  className="gov-btn gov-btn-secondary"
                  style={{ width: "100%", padding: "10px" }}
                >
                  ✎ Modify Block Parameters
                </button>
                <button
                  onClick={() => { setDecisionType("REJECT"); setReason(""); }}
                  className="gov-btn gov-btn-danger"
                  style={{ width: "100%", padding: "10px" }}
                >
                  ✕ Reject Recommendation
                </button>
              </div>
            ) : (
              <div className="gov-alert gov-alert-warning" style={{ fontSize: "0.85rem" }}>
                Decision actions are restricted to Railway Authorized Officials (department=RAILWAY, role=AUTHORIZED_OFFICIAL).
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Decision Modal */}
      {decisionType && (
        <div style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,0.5)", display: "flex", alignItems: "center", justifyContent: "center", zIndex: 1000, padding: "20px" }}>
          <div className="gov-card" style={{ maxWidth: "520px", width: "100%", background: "#ffffff", padding: "24px", borderRadius: "8px" }}>
            <h3 style={{ fontSize: "1.2rem", fontWeight: 700, marginBottom: "12px", color: decisionType === "APPROVE" ? "#16a34a" : decisionType === "REJECT" ? "#dc2626" : "#d97706" }}>
              {decisionType === "APPROVE" && "Confirm Block Approval"}
              {decisionType === "MODIFY" && "Submit Block Modification"}
              {decisionType === "REJECT" && "Confirm Block Rejection"}
            </h3>

            <form onSubmit={handleDecisionSubmit}>
              {decisionType === "APPROVE" && (
                <div style={{ fontSize: "0.9rem", color: "#475569", marginBottom: "16px" }}>
                  <p>Are you sure you want to approve block recommendation <strong>{detail.block_code}</strong> for window <strong>{detail.optimization.recommended_window}</strong>?</p>
                  <p style={{ fontSize: "0.85rem", color: "#64748b" }}>This will officially transition the block to <strong>SCHEDULED</strong> state.</p>
                </div>
              )}

              {decisionType === "MODIFY" && (
                <div style={{ display: "flex", flexDirection: "column", gap: "12px", marginBottom: "16px" }}>
                  <div>
                    <label className="gov-label">Select Alternative Safe Candidate</label>
                    <select
                      value={newCandidateId}
                      onChange={(e) => setNewCandidateId(e.target.value)}
                      className="gov-select"
                    >
                      <option value="">-- Keep Current Window --</option>
                      {detail.candidate_comparison.safe_alternatives.map((c) => (
                        <option key={c.candidate_id} value={c.candidate_id}>
                          {c.window} ({c.duration_mins}m, {c.predicted_delay_mins}m delay)
                        </option>
                      ))}
                    </select>
                  </div>
                  <div>
                    <label className="gov-label">Or Custom Start Time</label>
                    <input
                      type="datetime-local"
                      value={newStart}
                      onChange={(e) => setNewStart(e.target.value)}
                      className="gov-input"
                    />
                  </div>
                  <div>
                    <label className="gov-label">Custom End Time</label>
                    <input
                      type="datetime-local"
                      value={newEnd}
                      onChange={(e) => setNewEnd(e.target.value)}
                      className="gov-input"
                    />
                  </div>
                </div>
              )}

              {decisionType === "REJECT" && (
                <div style={{ fontSize: "0.9rem", color: "#475569", marginBottom: "12px" }}>
                  <p>You are about to reject block proposal <strong>{detail.block_code}</strong>.</p>
                  <p style={{ color: "#dc2626", fontWeight: 600 }}>A mandatory non-empty reason is required for rejection audit logging.</p>
                </div>
              )}

              <div style={{ marginBottom: "16px" }}>
                <label className="gov-label">
                  {decisionType === "REJECT" ? "Rejection Reason (Mandatory)" : "Decision Remarks / Notes"}
                </label>
                <textarea
                  value={reason}
                  onChange={(e) => setReason(e.target.value)}
                  placeholder={decisionType === "REJECT" ? "e.g. Operational conflict with priority freight movement..." : "Optional remarks..."}
                  className="gov-input"
                  style={{ minHeight: "80px" }}
                  required={decisionType === "REJECT"}
                />
              </div>

              {actionError && <div className="gov-alert gov-alert-danger" style={{ marginBottom: "12px" }}>{actionError}</div>}

              <div style={{ display: "flex", justifyContent: "flex-end", gap: "10px" }}>
                <button
                  type="button"
                  onClick={() => setDecisionType(null)}
                  className="gov-btn gov-btn-secondary"
                  disabled={submitting}
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className={`gov-btn ${decisionType === "APPROVE" ? "gov-btn-primary" : decisionType === "REJECT" ? "gov-btn-danger" : "gov-btn-secondary"}`}
                  disabled={submitting}
                >
                  {submitting ? "Processing..." : `Confirm ${decisionType}`}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
