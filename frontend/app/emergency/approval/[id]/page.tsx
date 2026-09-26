"use client";

import React, { useEffect, useState, use } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import ProtectedRoute from "@/components/ProtectedRoute";
import AppShell from "@/components/AppShell";
import Breadcrumbs from "@/components/Breadcrumbs";
import { useAuth } from "@/lib/auth-context";
import { api, ApiError } from "@/lib/api-client";
import { IncidentRecord } from "@/types/emergency";

interface RecommendationData {
  has_recommendation: boolean;
  optimized_block?: {
    id: number;
    block_code: string;
    start_time: string;
    end_time: string;
    total_duration_mins: number;
    total_delay_mins: number;
    affected_train_count: number;
    optimization_score: number | null;
    recommendation_reason: string;
    status: string;
  };
  comparison_matrix: Array<{
    candidate_id: number;
    window: string;
    start: string;
    end: string;
    predicted_duration_mins: number;
    predicted_delay_mins: number;
    affected_train_count: number;
    safety_status: string;
    optimization_score: number | null;
    is_selected: boolean;
    rejection_reason?: string;
  }>;
}

export default function OfficialEmergencyApprovalPage({ params }: { params: Promise<{ id: string }> }) {
  const resolvedParams = use(params);
  const incidentId = resolvedParams.id;
  const router = useRouter();
  const { user } = useAuth();

  const [incident, setIncident] = useState<IncidentRecord | null>(null);
  const [recommendation, setRecommendation] = useState<RecommendationData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [actionSuccess, setActionSuccess] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  // Forms
  const [activeTab, setActiveTab] = useState<"APPROVE" | "MODIFY" | "REJECT">("APPROVE");
  const [remarks, setRemarks] = useState("Approved for immediate emergency restoration by Railway Authorized Official.");
  const [teamName, setTeamName] = useState("Accident Relief & Restoration Gang #1");
  const [assignedResources, setAssignedResources] = useState("ART-01 (140T Crane), TWR-03 (Tower Car), SSE P-Way Team");
  
  // Modify fields
  const [modStart, setModStart] = useState("");
  const [modEnd, setModEnd] = useState("");

  // Reject fields
  const [rejectReason, setRejectReason] = useState("");

  const isOfficial =
    user?.role === "AUTHORIZED_OFFICIAL" ||
    (user?.role && user.role.includes("OFFICIAL")) ||
    user?.role === "SUPER_ADMIN";

  useEffect(() => {
    async function load() {
      try {
        const [inc, rec] = await Promise.all([
          api.get<IncidentRecord>(`/api/emergency/incidents/${incidentId}`),
          api.get<RecommendationData>(`/api/emergency/incidents/${incidentId}/recommendation`),
        ]);
        setIncident(inc);
        setRecommendation(rec);
        if (rec.optimized_block) {
          setModStart(new Date(rec.optimized_block.start_time).toISOString().slice(0, 16));
          setModEnd(new Date(rec.optimized_block.end_time).toISOString().slice(0, 16));
        }
      } catch (err) {
        setError(err instanceof ApiError ? err.message : "Failed to load recommendation details");
      } finally {
        setLoading(false);
      }
    }
    load();
  }, [incidentId]);

  const handleApprove = async () => {
    setSubmitting(true);
    setError(null);
    try {
      const res = await api.post<{ message: string }>(`/api/emergency/incidents/${incidentId}/approve`, {
        decision: "APPROVE",
        team_name: teamName,
        assigned_resources: assignedResources,
        remarks: remarks,
      });
      setActionSuccess(res.message);
      setTimeout(() => router.push(`/emergency/incidents/${incidentId}`), 1800);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to approve emergency block");
    } finally {
      setSubmitting(false);
    }
  };

  const handleModify = async () => {
    setSubmitting(true);
    setError(null);
    try {
      const res = await api.post<{ message: string }>(`/api/emergency/incidents/${incidentId}/modify`, {
        decision: "MODIFY",
        start_time: new Date(modStart).toISOString(),
        end_time: new Date(modEnd).toISOString(),
        team_name: teamName,
        assigned_resources: assignedResources,
        remarks: remarks,
      });
      setActionSuccess(res.message);
      setTimeout(() => router.push(`/emergency/incidents/${incidentId}`), 1800);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to modify emergency block");
    } finally {
      setSubmitting(false);
    }
  };

  const handleReject = async () => {
    if (!rejectReason.trim()) {
      setError("Please provide a reason for rejecting the recommendation.");
      return;
    }
    setSubmitting(true);
    setError(null);
    try {
      const res = await api.post<{ message: string }>(`/api/emergency/incidents/${incidentId}/reject`, {
        decision: "REJECT",
        reason: rejectReason,
      });
      setActionSuccess(res.message);
      setTimeout(() => router.push(`/emergency/incidents/${incidentId}`), 1800);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to reject emergency recommendation");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <ProtectedRoute>
      <AppShell>
        <div className="gov-page">
          <Breadcrumbs
            trail={[
              { label: "Dashboard", href: "/dashboard" },
              { label: "Emergency Control", href: "/emergency" },
              { label: incident?.incident_code || `Incident #${incidentId}`, href: `/emergency/incidents/${incidentId}` },
              { label: "Official Approval Center" },
            ]}
          />

          <div style={{ marginBottom: 20 }}>
            <span className="gov-badge gov-badge-danger" style={{ fontWeight: 700, marginBottom: 8, display: "inline-block" }}>
              RAILWAY AUTHORIZED OFFICIAL GATEWAY
            </span>
            <h1 className="gov-title">
              Official Decision: Emergency Block for {incident?.incident_code}
            </h1>
            <p className="gov-sub">
              Deterministic Safety Verified → OR-Tools CP-SAT Re-Optimized → Human-in-the-Loop Official Decision
            </p>
          </div>

          {error && <div className="gov-alert gov-alert-error" role="alert">{error}</div>}
          {actionSuccess && <div className="gov-alert gov-alert-success" role="status">{actionSuccess}</div>}

          {!isOfficial && (
            <div className="gov-alert gov-alert-warning" role="alert" style={{ marginBottom: 20 }}>
              <strong>Strict RBAC Notice:</strong> You are currently logged in as <code>{user?.role || "USER"}</code> ({user?.department || "N/A"}). 
              Only authenticated <strong>Railway Authorized Officials</strong> can authorize emergency railway blocks.
            </div>
          )}

          {loading ? (
            <p style={{ color: "var(--text-secondary)" }}>Loading recommendation data...</p>
          ) : !recommendation?.optimized_block ? (
            <div className="gov-card">
              <p>No CP-SAT optimized emergency recommendation exists for this incident yet.</p>
              <Link href={`/emergency/incidents/${incidentId}`} className="gov-btn gov-btn-primary">
                Return to Incident Planning →
              </Link>
            </div>
          ) : (
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 20 }}>
              {/* Left Column: Recommendation & Candidate Comparison */}
              <div>
                <div className="gov-card" style={{ marginBottom: 20, borderTop: "4px solid #f59e0b" }}>
                  <h3 style={{ fontSize: "1.1rem", fontWeight: 700, marginBottom: 12 }}>
                    OR-Tools Recommended Emergency Block
                  </h3>

                  <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12, marginBottom: 16 }}>
                    <div style={{ padding: 10, background: "rgba(0,0,0,0.03)", borderRadius: 6 }}>
                      <div style={{ fontSize: "0.75rem", color: "var(--text-secondary)" }}>BLOCK CODE</div>
                      <div style={{ fontWeight: 700, fontSize: "1rem" }}>{recommendation.optimized_block.block_code}</div>
                    </div>
                    <div style={{ padding: 10, background: "rgba(0,0,0,0.03)", borderRadius: 6 }}>
                      <div style={{ fontSize: "0.75rem", color: "var(--text-secondary)" }}>OPTIMIZATION SCORE</div>
                      <div style={{ fontWeight: 700, fontSize: "1.1rem", color: "#059669" }}>
                        {recommendation.optimized_block.optimization_score?.toFixed(1)} / 100
                      </div>
                    </div>
                    <div style={{ padding: 10, background: "rgba(0,0,0,0.03)", borderRadius: 6 }}>
                      <div style={{ fontSize: "0.75rem", color: "var(--text-secondary)" }}>RECOMMENDED WINDOW</div>
                      <div style={{ fontWeight: 600, fontSize: "0.9rem" }}>
                        {new Date(recommendation.optimized_block.start_time).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })} – {new Date(recommendation.optimized_block.end_time).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                      </div>
                      <div style={{ fontSize: "0.8rem", color: "var(--text-secondary)" }}>
                        Duration: {recommendation.optimized_block.total_duration_mins} mins
                      </div>
                    </div>
                    <div style={{ padding: 10, background: "rgba(0,0,0,0.03)", borderRadius: 6 }}>
                      <div style={{ fontSize: "0.75rem", color: "var(--text-secondary)" }}>PREDICTED TRAIN DELAY</div>
                      <div style={{ fontWeight: 600, fontSize: "0.9rem", color: "#dc2626" }}>
                        {recommendation.optimized_block.total_delay_mins} mins ({recommendation.optimized_block.affected_train_count} trains)
                      </div>
                    </div>
                  </div>

                  <div style={{ padding: 12, background: "rgba(245, 158, 11, 0.08)", borderRadius: 6, fontSize: "0.85rem", borderLeft: "3px solid #f59e0b" }}>
                    <strong>Solver Rationale:</strong> {recommendation.optimized_block.recommendation_reason}
                  </div>
                </div>

                {/* Candidate Comparison Matrix */}
                <div className="gov-card">
                  <h4 style={{ fontSize: "0.95rem", fontWeight: 700, marginBottom: 10 }}>Candidate Window Comparison Matrix</h4>
                  <div className="gov-table-container">
                    <table className="gov-table" style={{ fontSize: "0.82rem" }}>
                      <thead>
                        <tr>
                          <th>Window</th>
                          <th>Duration</th>
                          <th>Delay</th>
                          <th>Safety</th>
                          <th>Score</th>
                        </tr>
                      </thead>
                      <tbody>
                        {recommendation.comparison_matrix.map((c) => (
                          <tr key={c.candidate_id} style={{ background: c.is_selected ? "rgba(16, 185, 129, 0.1)" : undefined }}>
                            <td style={{ fontWeight: c.is_selected ? 700 : 400 }}>
                              {c.window} {c.is_selected && "★"}
                            </td>
                            <td>{c.predicted_duration_mins}m</td>
                            <td>{c.predicted_delay_mins}m</td>
                            <td>
                              <span className={`gov-badge ${c.safety_status === "SAFE" ? "gov-badge-success" : "gov-badge-danger"}`}>
                                {c.safety_status}
                              </span>
                            </td>
                            <td style={{ fontWeight: 700 }}>
                              {c.optimization_score ? c.optimization_score.toFixed(1) : "—"}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              </div>

              {/* Right Column: Decision Action Center */}
              <div className="gov-card" style={{ borderTop: "4px solid #2563eb" }}>
                <h3 style={{ fontSize: "1.1rem", fontWeight: 700, marginBottom: 12 }}>
                  Official Decision Execution
                </h3>

                {/* Tab selector */}
                <div style={{ display: "flex", gap: 8, marginBottom: 16, borderBottom: "1px solid var(--border-color)", paddingBottom: 8 }}>
                  <button
                    type="button"
                    className={`gov-btn ${activeTab === "APPROVE" ? "gov-btn-primary" : "gov-btn-secondary"}`}
                    style={{ fontSize: "0.85rem", padding: "6px 12px" }}
                    onClick={() => setActiveTab("APPROVE")}
                  >
                    ✓ Approve Recommendation
                  </button>
                  <button
                    type="button"
                    className={`gov-btn ${activeTab === "MODIFY" ? "gov-btn-primary" : "gov-btn-secondary"}`}
                    style={{ fontSize: "0.85rem", padding: "6px 12px" }}
                    onClick={() => setActiveTab("MODIFY")}
                  >
                    ✏ Modify & Approve
                  </button>
                  <button
                    type="button"
                    className={`gov-btn ${activeTab === "REJECT" ? "gov-btn-primary" : "gov-btn-secondary"}`}
                    style={{ fontSize: "0.85rem", padding: "6px 12px", background: activeTab === "REJECT" ? "#dc2626" : undefined, borderColor: activeTab === "REJECT" ? "#dc2626" : undefined }}
                    onClick={() => setActiveTab("REJECT")}
                  >
                    ✕ Reject
                  </button>
                </div>

                {activeTab === "APPROVE" && (
                  <div>
                    <p style={{ fontSize: "0.85rem", color: "var(--text-secondary)", marginBottom: 14 }}>
                      Authorizing this block will lock the restoration schedule, trigger immediate team dispatch alerts, and clear the track block window.
                    </p>
                    <div style={{ marginBottom: 12 }}>
                      <label style={{ display: "block", fontSize: "0.82rem", fontWeight: 600, marginBottom: 4 }}>
                        Assigned Response Team
                      </label>
                      <input
                        type="text"
                        className="gov-input"
                        value={teamName}
                        onChange={(e) => setTeamName(e.target.value)}
                        style={{ width: "100%", fontSize: "0.88rem" }}
                      />
                    </div>
                    <div style={{ marginBottom: 12 }}>
                      <label style={{ display: "block", fontSize: "0.82rem", fontWeight: 600, marginBottom: 4 }}>
                        Allocated Resources / Machinery
                      </label>
                      <input
                        type="text"
                        className="gov-input"
                        value={assignedResources}
                        onChange={(e) => setAssignedResources(e.target.value)}
                        style={{ width: "100%", fontSize: "0.88rem" }}
                      />
                    </div>
                    <div style={{ marginBottom: 16 }}>
                      <label style={{ display: "block", fontSize: "0.82rem", fontWeight: 600, marginBottom: 4 }}>
                        Official Approval Remarks & Directives
                      </label>
                      <textarea
                        className="gov-textarea"
                        rows={3}
                        value={remarks}
                        onChange={(e) => setRemarks(e.target.value)}
                        style={{ width: "100%", fontSize: "0.88rem" }}
                      />
                    </div>
                    <button
                      type="button"
                      className="gov-btn gov-btn-primary"
                      onClick={handleApprove}
                      disabled={submitting || !isOfficial}
                      style={{ width: "100%", background: "#059669", borderColor: "#059669", fontWeight: 700, padding: "10px 0" }}
                    >
                      {submitting ? "Processing Official Authorization..." : "Confirm & Authorize Emergency Block"}
                    </button>
                  </div>
                )}

                {activeTab === "MODIFY" && (
                  <div>
                    <p style={{ fontSize: "0.85rem", color: "var(--text-secondary)", marginBottom: 14 }}>
                      Adjust the emergency window start and end times before official authorization.
                    </p>
                    <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10, marginBottom: 12 }}>
                      <div>
                        <label style={{ display: "block", fontSize: "0.82rem", fontWeight: 600, marginBottom: 4 }}>
                          Modified Start Time
                        </label>
                        <input
                          type="datetime-local"
                          className="gov-input"
                          value={modStart}
                          onChange={(e) => setModStart(e.target.value)}
                          style={{ width: "100%", fontSize: "0.85rem" }}
                        />
                      </div>
                      <div>
                        <label style={{ display: "block", fontSize: "0.82rem", fontWeight: 600, marginBottom: 4 }}>
                          Modified End Time
                        </label>
                        <input
                          type="datetime-local"
                          className="gov-input"
                          value={modEnd}
                          onChange={(e) => setModEnd(e.target.value)}
                          style={{ width: "100%", fontSize: "0.85rem" }}
                        />
                      </div>
                    </div>
                    <div style={{ marginBottom: 12 }}>
                      <label style={{ display: "block", fontSize: "0.82rem", fontWeight: 600, marginBottom: 4 }}>
                        Assigned Response Team
                      </label>
                      <input
                        type="text"
                        className="gov-input"
                        value={teamName}
                        onChange={(e) => setTeamName(e.target.value)}
                        style={{ width: "100%", fontSize: "0.88rem" }}
                      />
                    </div>
                    <div style={{ marginBottom: 16 }}>
                      <label style={{ display: "block", fontSize: "0.82rem", fontWeight: 600, marginBottom: 4 }}>
                        Modification Justification
                      </label>
                      <textarea
                        className="gov-textarea"
                        rows={3}
                        value={remarks}
                        onChange={(e) => setRemarks(e.target.value)}
                        style={{ width: "100%", fontSize: "0.88rem" }}
                      />
                    </div>
                    <button
                      type="button"
                      className="gov-btn gov-btn-primary"
                      onClick={handleModify}
                      disabled={submitting || !isOfficial}
                      style={{ width: "100%", background: "#2563eb", borderColor: "#2563eb", fontWeight: 700, padding: "10px 0" }}
                    >
                      {submitting ? "Applying Modifications..." : "Authorize Modified Emergency Block"}
                    </button>
                  </div>
                )}

                {activeTab === "REJECT" && (
                  <div>
                    <p style={{ fontSize: "0.85rem", color: "var(--text-secondary)", marginBottom: 14 }}>
                      Rejecting the recommendation will return the incident to ASSESSED status for revised scenario planning.
                    </p>
                    <div style={{ marginBottom: 16 }}>
                      <label style={{ display: "block", fontSize: "0.82rem", fontWeight: 600, marginBottom: 4 }}>
                        Official Rejection Reason (Mandatory)
                      </label>
                      <textarea
                        className="gov-textarea"
                        rows={4}
                        placeholder="e.g., Heavy VIP express movement on section; delay block by 45 minutes or shift to adjacent loop line..."
                        value={rejectReason}
                        onChange={(e) => setRejectReason(e.target.value)}
                        style={{ width: "100%", fontSize: "0.88rem" }}
                      />
                    </div>
                    <button
                      type="button"
                      className="gov-btn gov-btn-primary"
                      onClick={handleReject}
                      disabled={submitting || !isOfficial}
                      style={{ width: "100%", background: "#dc2626", borderColor: "#dc2626", fontWeight: 700, padding: "10px 0" }}
                    >
                      {submitting ? "Rejecting Plan..." : "Confirm Rejection of Emergency Block"}
                    </button>
                  </div>
                )}
              </div>
            </div>
          )}
        </div>
      </AppShell>
    </ProtectedRoute>
  );
}
