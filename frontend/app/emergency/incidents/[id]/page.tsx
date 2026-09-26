"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import ProtectedRoute from "@/components/ProtectedRoute";
import AppShell from "@/components/AppShell";
import Breadcrumbs from "@/components/Breadcrumbs";
import { useAuth } from "@/lib/auth-context";
import { api, ApiError } from "@/lib/api-client";
import {
  IncidentRecord,
  AffectedTrainImpact,
  ConflictingBlock,
  EmergencyResource,
  EmergencyCandidate,
} from "@/types/emergency";

export default function IncidentDetailPage() {
  const params = useParams<{ id: string }>();
  const incidentId = params.id;
  const router = useRouter();
  const { user } = useAuth();

  const [incident, setIncident] = useState<IncidentRecord | null>(null);
  const [affectedTrains, setAffectedTrains] = useState<AffectedTrainImpact | null>(null);
  const [conflicts, setConflicts] = useState<ConflictingBlock[]>([]);
  const [resources, setResources] = useState<EmergencyResource[]>([]);
  const [candidates, setCandidates] = useState<EmergencyCandidate[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<"DETAILS" | "ASSESS" | "TRAINS" | "RESOURCES" | "PLANNING" | "TRACKING" | "CLEARANCE">("DETAILS");

  // Assessment Form
  const [assessNotes, setAssessNotes] = useState("");
  const [assessDuration, setAssessDuration] = useState(120);
  const [assessSeverity, setAssessSeverity] = useState("HIGH");

  // Clearance Form
  const [chkTrack, setChkTrack] = useState(true);
  const [chkOhe, setChkOhe] = useState(true);
  const [chkSignals, setChkSignals] = useState(true);
  const [clearanceNotes, setClearanceNotes] = useState("Track physically inspected, OHE energized, signals tested normal.");

  // Action Loading states
  const [actionLoading, setActionLoading] = useState(false);

  const loadAll = async () => {
    try {
      const inc = await api.get<IncidentRecord>(`/api/emergency/incidents/${incidentId}`);
      setIncident(inc);
      setAssessSeverity(inc.severity);
      if (inc.assessment_notes) setAssessNotes(inc.assessment_notes);

      // Load supporting data if assessed
      if (inc.block_request_id || inc.status !== "REPORTED") {
        try {
          const [tr, conf, res] = await Promise.all([
            api.get<AffectedTrainImpact>(`/api/emergency/incidents/${incidentId}/affected-trains`),
            api.get<ConflictingBlock[]>(`/api/emergency/incidents/${incidentId}/conflicting-blocks`),
            api.get<EmergencyResource[]>(`/api/emergency/incidents/${incidentId}/resources`),
          ]);
          setAffectedTrains(tr);
          setConflicts(conf || []);
          setResources(res || []);
        } catch {
          // Non-blocking
        }
      }
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to load incident details");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadAll();
  }, [incidentId]);

  // Handlers
  const handleAcknowledge = async () => {
    setActionLoading(true);
    setError(null);
    try {
      await api.post(`/api/emergency/incidents/${incidentId}/acknowledge`, {});
      setSuccess("Incident acknowledged successfully.");
      await loadAll();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to acknowledge");
    } finally {
      setActionLoading(false);
    }
  };

  const handleAssess = async () => {
    setActionLoading(true);
    setError(null);
    try {
      await api.post(`/api/emergency/incidents/${incidentId}/assess`, {
        assessment_notes: assessNotes,
        estimated_duration_mins: Number(assessDuration),
        severity: assessSeverity,
      });
      setSuccess("Incident assessed and emergency block request created.");
      await loadAll();
      setActiveTab("PLANNING");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to assess incident");
    } finally {
      setActionLoading(false);
    }
  };

  const handleGenerateCandidates = async () => {
    setActionLoading(true);
    setError(null);
    try {
      const res = await api.post<{ candidates: EmergencyCandidate[] }>(
        `/api/emergency/incidents/${incidentId}/generate-candidates`,
        {}
      );
      setCandidates(res.candidates || []);
      setSuccess(`Generated and safety-evaluated ${res.candidates?.length || 0} candidate restoration windows.`);
      await loadAll();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to generate candidates");
    } finally {
      setActionLoading(false);
    }
  };

  const handleOptimize = async () => {
    setActionLoading(true);
    setError(null);
    try {
      await api.post(`/api/emergency/incidents/${incidentId}/optimize`, {});
      setSuccess("OR-Tools CP-SAT emergency optimization completed. Recommendation awaiting Railway Official decision.");
      await loadAll();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Optimization failed");
    } finally {
      setActionLoading(false);
    }
  };

  const handleDispatch = async () => {
    setActionLoading(true);
    try {
      await api.post(`/api/emergency/incidents/${incidentId}/dispatch`, {
        team_name: "Rapid Emergency Response Gang",
        assigned_resources: "ART-01, TWR-03, P-Way Gang",
      });
      setSuccess("Emergency response team dispatched to incident site.");
      await loadAll();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Dispatch failed");
    } finally {
      setActionLoading(false);
    }
  };

  const handleArrive = async () => {
    setActionLoading(true);
    try {
      await api.post(`/api/emergency/incidents/${incidentId}/arrive`, {});
      setSuccess("Response team arrival on site recorded.");
      await loadAll();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to record arrival");
    } finally {
      setActionLoading(false);
    }
  };

  const handleStartWork = async () => {
    setActionLoading(true);
    try {
      await api.post(`/api/emergency/incidents/${incidentId}/start-work`, {});
      setSuccess("Physical restoration work commenced.");
      await loadAll();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to start work");
    } finally {
      setActionLoading(false);
    }
  };

  const handleRequestClearance = async () => {
    setActionLoading(true);
    try {
      await api.post(`/api/emergency/incidents/${incidentId}/request-clearance`, {});
      setSuccess("Restoration work finished. Track clearance requested.");
      await loadAll();
      setActiveTab("CLEARANCE");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to request clearance");
    } finally {
      setActionLoading(false);
    }
  };

  const handleGrantClearance = async () => {
    if (!chkTrack || !chkOhe || !chkSignals) {
      setError("All 3 safety checklist items must be physically verified before granting track clearance.");
      return;
    }
    setActionLoading(true);
    try {
      await api.post(`/api/emergency/incidents/${incidentId}/grant-clearance`, {
        track_inspected: chkTrack,
        ohe_tested: chkOhe,
        signals_normal: chkSignals,
        notes: clearanceNotes,
      });
      setSuccess("Track safety clearance certified.");
      await loadAll();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to grant clearance");
    } finally {
      setActionLoading(false);
    }
  };

  const handleReleaseBlock = async () => {
    setActionLoading(true);
    try {
      await api.post(`/api/emergency/incidents/${incidentId}/release-block`, {});
      setSuccess("Emergency block released. Section throughput restored.");
      await loadAll();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to release block");
    } finally {
      setActionLoading(false);
    }
  };

  const handleClose = async () => {
    setActionLoading(true);
    try {
      await api.post(`/api/emergency/incidents/${incidentId}/close`, {
        notes: "Restoration completed, block released, track traffic nominal.",
      });
      setSuccess("Incident formally closed.");
      await loadAll();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to close incident");
    } finally {
      setActionLoading(false);
    }
  };

  const stepIndex = (st: string) => {
    const map: Record<string, number> = {
      REPORTED: 0,
      ACKNOWLEDGED: 1,
      ASSESSED: 2,
      EMERGENCY_PLANNING: 3,
      AWAITING_OFFICIAL_DECISION: 4,
      APPROVED: 5,
      RESPONSE_DISPATCHED: 6,
      ON_SITE: 7,
      WORK_IN_PROGRESS: 8,
      CLEARANCE_PENDING: 9,
      CLEARED: 10,
      RELEASED: 11,
      INCIDENT_CLOSED: 12,
    };
    return map[st] ?? 0;
  };

  if (loading) {
    return (
      <ProtectedRoute>
        <AppShell>
          <div className="gov-page"><p>Loading incident data...</p></div>
        </AppShell>
      </ProtectedRoute>
    );
  }

  if (!incident) {
    return (
      <ProtectedRoute>
        <AppShell>
          <div className="gov-page"><div className="gov-alert gov-alert-error">Incident not found</div></div>
        </AppShell>
      </ProtectedRoute>
    );
  }

  const currentStep = stepIndex(incident.status);

  return (
    <ProtectedRoute>
      <AppShell>
        <div className="gov-page">
          <Breadcrumbs
            trail={[
              { label: "Dashboard", href: "/dashboard" },
              { label: "Emergency Control", href: "/emergency" },
              { label: incident.incident_code },
            ]}
          />

          {/* Header Banner */}
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 16 }}>
            <div>
              <div style={{ display: "flex", gap: 8, alignItems: "center", marginBottom: 6 }}>
                <span className="gov-badge gov-badge-danger" style={{ fontWeight: 700 }}>
                  {incident.severity}
                </span>
                <span className="gov-badge gov-badge-info">
                  {incident.incident_type.replace(/_/g, " ")}
                </span>
                {incident.is_simulated && (
                  <span className="gov-badge" style={{ background: "#6b7280", color: "#fff" }}>
                    SIMULATED
                  </span>
                )}
              </div>
              <h1 className="gov-title" style={{ margin: 0 }}>
                {incident.incident_code} — {incident.section_name || `Section #${incident.section_id}`}
              </h1>
              <p className="gov-sub" style={{ marginTop: 4 }}>
                Reported at {new Date(incident.reported_at).toLocaleString()} | Reporter: {incident.reporter_name || "Emergency Desk"}
              </p>
            </div>

            <div style={{ display: "flex", gap: 8 }}>
              {incident.status === "AWAITING_OFFICIAL_DECISION" && (
                <Link
                  href={`/emergency/approval/${incident.id}`}
                  className="gov-btn gov-btn-primary"
                  style={{ background: "#f59e0b", borderColor: "#f59e0b", color: "#000", fontWeight: 700 }}
                >
                  ⚡ Official Decision Gateway
                </Link>
              )}
            </div>
          </div>

          {error && <div className="gov-alert gov-alert-error" role="alert">{error}</div>}
          {success && <div className="gov-alert gov-alert-success" role="status">{success}</div>}

          {/* Step Progress Tracker */}
          <div className="gov-card" style={{ marginBottom: 20, padding: 14 }}>
            <div style={{ fontSize: "0.78rem", fontWeight: 700, color: "var(--text-secondary)", marginBottom: 8 }}>
              EMERGENCY LIFECYCLE PROGRESS
            </div>
            <div style={{ display: "flex", gap: 6, flexWrap: "wrap", alignItems: "center" }}>
              {[
                "1. Reported",
                "2. Acknowledged",
                "3. Assessed",
                "4. Re-Planning",
                "5. Official Decision",
                "6. Approved",
                "7. Dispatched",
                "8. On-Site Work",
                "9. Clearance",
                "10. Released & Closed",
              ].map((lbl, idx) => {
                const isPassed = currentStep >= idx;
                const isCurrent = currentStep === idx || (idx === 4 && incident.status === "AWAITING_OFFICIAL_DECISION");
                return (
                  <div
                    key={lbl}
                    style={{
                      padding: "4px 8px",
                      borderRadius: 4,
                      fontSize: "0.75rem",
                      fontWeight: isCurrent ? 700 : 500,
                      background: isCurrent ? "#2563eb" : isPassed ? "#10b981" : "rgba(0,0,0,0.06)",
                      color: isCurrent || isPassed ? "#ffffff" : "var(--text-secondary)",
                    }}
                  >
                    {lbl}
                  </div>
                );
              })}
            </div>
          </div>

          {/* Tab Navigation */}
          <div style={{ display: "flex", gap: 8, marginBottom: 16, borderBottom: "1px solid var(--border-color)", paddingBottom: 8, overflowX: "auto" }}>
            <button
              type="button"
              className={`gov-btn ${activeTab === "DETAILS" ? "gov-btn-primary" : "gov-btn-secondary"}`}
              style={{ fontSize: "0.85rem", padding: "6px 12px" }}
              onClick={() => setActiveTab("DETAILS")}
            >
              📋 Incident Details
            </button>
            <button
              type="button"
              className={`gov-btn ${activeTab === "ASSESS" ? "gov-btn-primary" : "gov-btn-secondary"}`}
              style={{ fontSize: "0.85rem", padding: "6px 12px" }}
              onClick={() => setActiveTab("ASSESS")}
            >
              📝 Assessment & MR
            </button>
            <button
              type="button"
              className={`gov-btn ${activeTab === "TRAINS" ? "gov-btn-primary" : "gov-btn-secondary"}`}
              style={{ fontSize: "0.85rem", padding: "6px 12px" }}
              onClick={() => setActiveTab("TRAINS")}
            >
              🚆 Train Delays ({affectedTrains?.affected_train_count || 0})
            </button>
            <button
              type="button"
              className={`gov-btn ${activeTab === "RESOURCES" ? "gov-btn-primary" : "gov-btn-secondary"}`}
              style={{ fontSize: "0.85rem", padding: "6px 12px" }}
              onClick={() => setActiveTab("RESOURCES")}
            >
              🛠 Available Relief Assets ({resources.length})
            </button>
            <button
              type="button"
              className={`gov-btn ${activeTab === "PLANNING" ? "gov-btn-primary" : "gov-btn-secondary"}`}
              style={{ fontSize: "0.85rem", padding: "6px 12px" }}
              onClick={() => setActiveTab("PLANNING")}
            >
              🤖 CP-SAT Optimization
            </button>
            <button
              type="button"
              className={`gov-btn ${activeTab === "TRACKING" ? "gov-btn-primary" : "gov-btn-secondary"}`}
              style={{ fontSize: "0.85rem", padding: "6px 12px" }}
              onClick={() => setActiveTab("TRACKING")}
            >
              ⏱ Response Gang Tracking
            </button>
            <button
              type="button"
              className={`gov-btn ${activeTab === "CLEARANCE" ? "gov-btn-primary" : "gov-btn-secondary"}`}
              style={{ fontSize: "0.85rem", padding: "6px 12px" }}
              onClick={() => setActiveTab("CLEARANCE")}
            >
              ✅ Track Clearance Certification
            </button>
          </div>

          {/* TAB CONTENT */}

          {/* 1. Details Tab */}
          {activeTab === "DETAILS" && (
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 20 }}>
              <div className="gov-card">
                <h3 style={{ fontSize: "1rem", fontWeight: 700, marginBottom: 12 }}>Incident Metadata</h3>
                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10, fontSize: "0.88rem" }}>
                  <div>
                    <span style={{ color: "var(--text-secondary)", display: "block", fontSize: "0.75rem" }}>SECTION</span>
                    <strong>{incident.section_name || `Section #${incident.section_id}`}</strong>
                  </div>
                  <div>
                    <span style={{ color: "var(--text-secondary)", display: "block", fontSize: "0.75rem" }}>TRACK</span>
                    <strong>{incident.track_number ? `Track #${incident.track_number}` : "All Tracks / Unspecified"}</strong>
                  </div>
                  <div>
                    <span style={{ color: "var(--text-secondary)", display: "block", fontSize: "0.75rem" }}>COORDINATES</span>
                    <span>{incident.latitude ? `${incident.latitude}, ${incident.longitude}` : "GPS N/A"}</span>
                  </div>
                  <div>
                    <span style={{ color: "var(--text-secondary)", display: "block", fontSize: "0.75rem" }}>LINKED BLOCK CODE</span>
                    <span>{incident.block_code || "Pending Assessment"}</span>
                  </div>
                  <div>
                    <span style={{ color: "var(--text-secondary)", display: "block", fontSize: "0.75rem" }}>RAILWAY ALERT</span>
                    <span className="gov-badge gov-badge-success">{incident.railway_alert_status || "SENT"}</span>
                  </div>
                  <div>
                    <span style={{ color: "var(--text-secondary)", display: "block", fontSize: "0.75rem" }}>POLICE ALERT</span>
                    <span className="gov-badge">{incident.police_alert_status || "NOT_APPLICABLE"}</span>
                  </div>
                </div>

                <div style={{ marginTop: 14 }}>
                  <span style={{ color: "var(--text-secondary)", display: "block", fontSize: "0.75rem" }}>DESCRIPTION</span>
                  <p style={{ marginTop: 4, fontSize: "0.88rem" }}>{incident.description || "No description provided."}</p>
                </div>

                {incident.status === "REPORTED" && (
                  <div style={{ marginTop: 16 }}>
                    <button
                      type="button"
                      className="gov-btn gov-btn-primary"
                      onClick={handleAcknowledge}
                      disabled={actionLoading}
                      style={{ background: "#2563eb", width: "100%" }}
                    >
                      {actionLoading ? "Acknowledging..." : "✓ Acknowledge Incident"}
                    </button>
                  </div>
                )}
              </div>

              <div className="gov-card">
                <h3 style={{ fontSize: "1rem", fontWeight: 700, marginBottom: 12 }}>Response History ({incident.responses.length})</h3>
                {incident.responses.length === 0 ? (
                  <p style={{ color: "var(--text-secondary)", fontSize: "0.85rem" }}>No response units logged yet.</p>
                ) : (
                  <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
                    {incident.responses.map((r) => (
                      <div key={r.id} style={{ padding: 10, background: "rgba(0,0,0,0.03)", borderRadius: 6, fontSize: "0.85rem" }}>
                        <div style={{ display: "flex", justifyContent: "space-between" }}>
                          <strong>{r.team_name || r.authority_name || r.authority_type}</strong>
                          <span className="gov-badge">{r.status}</span>
                        </div>
                        <div style={{ fontSize: "0.78rem", color: "var(--text-secondary)", marginTop: 4 }}>
                          {r.assigned_resources && <div>Resources: {r.assigned_resources}</div>}
                          {r.arrival_time && <div>Arrived: {new Date(r.arrival_time).toLocaleTimeString()}</div>}
                          {r.clearance_time && <div>Cleared: {new Date(r.clearance_time).toLocaleTimeString()}</div>}
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>
          )}

          {/* 2. Assessment Tab */}
          {activeTab === "ASSESS" && (
            <div className="gov-card" style={{ maxWidth: 700 }}>
              <h3 style={{ fontSize: "1.1rem", fontWeight: 700, marginBottom: 12 }}>
                Technical Assessment & Emergency Request Setup
              </h3>
              <p style={{ fontSize: "0.85rem", color: "var(--text-secondary)", marginBottom: 16 }}>
                Recording assessment generates a linked Critical Maintenance Request and Emergency Block Request.
              </p>

              <div style={{ marginBottom: 12 }}>
                <label style={{ display: "block", fontSize: "0.82rem", fontWeight: 600, marginBottom: 4 }}>
                  Severity Classification
                </label>
                <select
                  className="gov-input"
                  value={assessSeverity}
                  onChange={(e) => setAssessSeverity(e.target.value)}
                  style={{ width: "100%", fontSize: "0.88rem" }}
                >
                  <option value="CRITICAL">CRITICAL (Total Section Blockage)</option>
                  <option value="HIGH">HIGH (Single Track Blockage)</option>
                  <option value="MEDIUM">MEDIUM (Speed Restriction Required)</option>
                  <option value="LOW">LOW (Precautionary)</option>
                </select>
              </div>

              <div style={{ marginBottom: 12 }}>
                <label style={{ display: "block", fontSize: "0.82rem", fontWeight: 600, marginBottom: 4 }}>
                  Estimated Restoration Duration (Minutes)
                </label>
                <input
                  type="number"
                  className="gov-input"
                  value={assessDuration}
                  onChange={(e) => setAssessDuration(Number(e.target.value))}
                  style={{ width: "100%", fontSize: "0.88rem" }}
                />
              </div>

              <div style={{ marginBottom: 16 }}>
                <label style={{ display: "block", fontSize: "0.82rem", fontWeight: 600, marginBottom: 4 }}>
                  Technical Assessment Notes & Scope of Work
                </label>
                <textarea
                  className="gov-textarea"
                  rows={4}
                  placeholder="Describe damage, required cranes, OHE isolation, signal interlocking status..."
                  value={assessNotes}
                  onChange={(e) => setAssessNotes(e.target.value)}
                  style={{ width: "100%", fontSize: "0.88rem" }}
                />
              </div>

              <button
                type="button"
                className="gov-btn gov-btn-primary"
                onClick={handleAssess}
                disabled={actionLoading}
                style={{ width: "100%", background: "#dc2626", borderColor: "#dc2626", fontWeight: 700 }}
              >
                {actionLoading ? "Submitting Assessment..." : "Submit Technical Assessment & Initialize Emergency Block"}
              </button>
            </div>
          )}

          {/* 3. Affected Trains Tab */}
          {activeTab === "TRAINS" && (
            <div className="gov-card">
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 14 }}>
                <h3 style={{ fontSize: "1.1rem", fontWeight: 700, margin: 0 }}>
                  Timetable Impact & ML Delay Prediction
                </h3>
                {affectedTrains && (
                  <span className="gov-badge gov-badge-danger" style={{ fontWeight: 700 }}>
                    Total Delay: {affectedTrains.total_predicted_delay_minutes} mins ({affectedTrains.affected_train_count} trains)
                  </span>
                )}
              </div>

              {!affectedTrains || affectedTrains.individual_predictions.length === 0 ? (
                <p style={{ color: "var(--text-secondary)" }}>No timetable trains affected during the initial window.</p>
              ) : (
                <div className="gov-table-container">
                  <table className="gov-table">
                    <thead>
                      <tr>
                        <th>Train #</th>
                        <th>Train Name</th>
                        <th>Station</th>
                        <th>ML Predicted Delay</th>
                        <th>Impact Level</th>
                      </tr>
                    </thead>
                    <tbody>
                      {affectedTrains.individual_predictions.map((tr) => (
                        <tr key={tr.train_number}>
                          <td style={{ fontWeight: 700 }}>{tr.train_number}</td>
                          <td>{tr.train_name}</td>
                          <td>{tr.station_name} ({tr.station_code})</td>
                          <td style={{ fontWeight: 700, color: tr.predicted_delay_mins > 30 ? "#dc2626" : "#f59e0b" }}>
                            +{tr.predicted_delay_mins} mins
                          </td>
                          <td>
                            <span className={`gov-badge ${tr.impact_level === "CRITICAL" ? "gov-badge-danger" : "gov-badge-warning"}`}>
                              {tr.impact_level}
                            </span>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          )}

          {/* 4. Resources Tab */}
          {activeTab === "RESOURCES" && (
            <div className="gov-card">
              <h3 style={{ fontSize: "1.1rem", fontWeight: 700, marginBottom: 12 }}>
                Nearby Emergency Relief Assets & Depots
              </h3>
              <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))", gap: 14 }}>
                {resources.map((r) => (
                  <div key={r.resource_id} style={{ padding: 14, background: "rgba(0,0,0,0.03)", borderRadius: 8, border: "1px solid var(--border-color)" }}>
                    <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 6 }}>
                      <strong style={{ fontSize: "0.95rem" }}>{r.name}</strong>
                      <span className="gov-badge gov-badge-success">{r.status}</span>
                    </div>
                    <div style={{ fontSize: "0.82rem", color: "var(--text-secondary)", display: "flex", flexDirection: "column", gap: 3 }}>
                      <div>Depot: <strong>{r.depot_location}</strong></div>
                      <div>ETA to Site: <strong style={{ color: "#2563eb" }}>{r.eta_minutes} mins</strong></div>
                      <div>Contact Desk: <code>{r.contact}</code></div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* 5. Planning & CP-SAT Optimization Tab */}
          {activeTab === "PLANNING" && (
            <div>
              <div className="gov-card" style={{ marginBottom: 20 }}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 12 }}>
                  <div>
                    <h3 style={{ fontSize: "1.1rem", fontWeight: 700, margin: 0 }}>
                      Emergency Candidate Windows & Safety Gate
                    </h3>
                    <p style={{ fontSize: "0.82rem", color: "var(--text-secondary)", marginTop: 2 }}>
                      Deterministic Safety Engine evaluates candidates before OR-Tools CP-SAT re-optimization.
                    </p>
                  </div>
                  <div style={{ display: "flex", gap: 8 }}>
                    <button
                      type="button"
                      className="gov-btn gov-btn-secondary"
                      onClick={handleGenerateCandidates}
                      disabled={actionLoading}
                    >
                      {actionLoading ? "Generating..." : "⚡ Generate Candidates"}
                    </button>
                    <button
                      type="button"
                      className="gov-btn gov-btn-primary"
                      onClick={handleOptimize}
                      disabled={actionLoading}
                      style={{ background: "#2563eb" }}
                    >
                      {actionLoading ? "Solving CP-SAT..." : "🚀 Run OR-Tools Optimization"}
                    </button>
                  </div>
                </div>

                {candidates.length === 0 ? (
                  <p style={{ color: "var(--text-secondary)", fontSize: "0.85rem" }}>
                    Click &quot;Generate Candidates&quot; to synthesize immediate, post-express, and buffered restoration windows.
                  </p>
                ) : (
                  <div className="gov-table-container">
                    <table className="gov-table">
                      <thead>
                        <tr>
                          <th>Candidate Label</th>
                          <th>Window (Start – End)</th>
                          <th>Duration</th>
                          <th>Predicted Delay</th>
                          <th>Hard Safety Gate</th>
                        </tr>
                      </thead>
                      <tbody>
                        {candidates.map((c) => (
                          <tr key={c.candidate_id}>
                            <td style={{ fontWeight: 600 }}>{c.label}</td>
                            <td>
                              {new Date(c.start).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })} – {new Date(c.end).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                            </td>
                            <td>{c.duration_mins} mins</td>
                            <td style={{ color: "#dc2626", fontWeight: 600 }}>{c.predicted_delay_mins} mins</td>
                            <td>
                              <span className={`gov-badge ${c.safety_status === "SAFE" ? "gov-badge-success" : "gov-badge-danger"}`}>
                                {c.safety_status}
                              </span>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </div>

              {incident.status === "AWAITING_OFFICIAL_DECISION" && (
                <div className="gov-card" style={{ background: "rgba(245, 158, 11, 0.08)", borderLeft: "4px solid #f59e0b" }}>
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                    <div>
                      <h4 style={{ fontWeight: 700, margin: 0, color: "#92400e" }}>
                        OR-Tools Recommendation Ready for Official Decision
                      </h4>
                      <p style={{ margin: "4px 0 0 0", fontSize: "0.85rem" }}>
                        Human-in-the-loop: A Railway Authorized Official must review and approve before response execution.
                      </p>
                    </div>
                    <Link
                      href={`/emergency/approval/${incident.id}`}
                      className="gov-btn gov-btn-primary"
                      style={{ background: "#f59e0b", borderColor: "#f59e0b", color: "#000", fontWeight: 700 }}
                    >
                      Open Official Approval Center →
                    </Link>
                  </div>
                </div>
              )}
            </div>
          )}

          {/* 6. Response Gang Tracking Tab */}
          {activeTab === "TRACKING" && (
            <div className="gov-card">
              <h3 style={{ fontSize: "1.1rem", fontWeight: 700, marginBottom: 14 }}>
                Physical Response & Work Tracking
              </h3>

              <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 12, marginBottom: 20 }}>
                <button
                  type="button"
                  className="gov-btn"
                  onClick={handleDispatch}
                  disabled={actionLoading || currentStep >= 6}
                  style={{ background: currentStep >= 6 ? "#10b981" : "#2563eb", color: "#fff" }}
                >
                  1. Dispatch Gang {currentStep >= 6 && "✓"}
                </button>
                <button
                  type="button"
                  className="gov-btn"
                  onClick={handleArrive}
                  disabled={actionLoading || currentStep < 6 || currentStep >= 7}
                  style={{ background: currentStep >= 7 ? "#10b981" : "#2563eb", color: "#fff" }}
                >
                  2. Mark On-Site {currentStep >= 7 && "✓"}
                </button>
                <button
                  type="button"
                  className="gov-btn"
                  onClick={handleStartWork}
                  disabled={actionLoading || currentStep < 7 || currentStep >= 8}
                  style={{ background: currentStep >= 8 ? "#10b981" : "#2563eb", color: "#fff" }}
                >
                  3. Start Work {currentStep >= 8 && "✓"}
                </button>
                <button
                  type="button"
                  className="gov-btn"
                  onClick={handleRequestClearance}
                  disabled={actionLoading || currentStep < 8 || currentStep >= 9}
                  style={{ background: currentStep >= 9 ? "#10b981" : "#f59e0b", color: currentStep >= 9 ? "#fff" : "#000", fontWeight: 700 }}
                >
                  4. Finish Work & Request Clearance {currentStep >= 9 && "✓"}
                </button>
              </div>

              <div style={{ fontSize: "0.85rem", color: "var(--text-secondary)" }}>
                Current Operational State: <strong>{incident.status.replace(/_/g, " ")}</strong>
              </div>
            </div>
          )}

          {/* 7. Clearance Tab */}
          {activeTab === "CLEARANCE" && (
            <div className="gov-card" style={{ maxWidth: 700 }}>
              <h3 style={{ fontSize: "1.1rem", fontWeight: 700, marginBottom: 12 }}>
                Mandatory Track Clearance Verification Checklist
              </h3>
              <p style={{ fontSize: "0.85rem", color: "var(--text-secondary)", marginBottom: 16 }}>
                Before emergency block release and section throughput restoration, verify all physical safety conditions.
              </p>

              <div style={{ display: "flex", flexDirection: "column", gap: 10, marginBottom: 16 }}>
                <label style={{ display: "flex", alignItems: "center", gap: 8, fontSize: "0.88rem", cursor: "pointer" }}>
                  <input
                    type="checkbox"
                    checked={chkTrack}
                    onChange={(e) => setChkTrack(e.target.checked)}
                  />
                  <span><strong>Track Structure & Gauge Verification:</strong> Rails inspected, fastenings secure, no debris.</span>
                </label>
                <label style={{ display: "flex", alignItems: "center", gap: 8, fontSize: "0.88rem", cursor: "pointer" }}>
                  <input
                    type="checkbox"
                    checked={chkOhe}
                    onChange={(e) => setChkOhe(e.target.checked)}
                  />
                  <span><strong>OHE & Power Energization:</strong> Traction wires checked, clearances verified, 25kV power restored.</span>
                </label>
                <label style={{ display: "flex", alignItems: "center", gap: 8, fontSize: "0.88rem", cursor: "pointer" }}>
                  <input
                    type="checkbox"
                    checked={chkSignals}
                    onChange={(e) => setChkSignals(e.target.checked)}
                  />
                  <span><strong>Signaling & Interlocking:</strong> Track circuits clear, point machines tested, signal aspects green.</span>
                </label>
              </div>

              <div style={{ marginBottom: 16 }}>
                <label style={{ display: "block", fontSize: "0.82rem", fontWeight: 600, marginBottom: 4 }}>
                  Clearance Certification Notes
                </label>
                <textarea
                  className="gov-textarea"
                  rows={3}
                  value={clearanceNotes}
                  onChange={(e) => setClearanceNotes(e.target.value)}
                  style={{ width: "100%", fontSize: "0.88rem" }}
                />
              </div>

              <div style={{ display: "flex", gap: 10 }}>
                {incident.status !== "CLEARED" && incident.status !== "RELEASED" && incident.status !== "INCIDENT_CLOSED" && (
                  <button
                    type="button"
                    className="gov-btn gov-btn-primary"
                    onClick={handleGrantClearance}
                    disabled={actionLoading}
                    style={{ background: "#059669", borderColor: "#059669", fontWeight: 700 }}
                  >
                    {actionLoading ? "Certifying..." : "✓ Grant Track Safety Clearance"}
                  </button>
                )}

                {incident.status === "CLEARED" && (
                  <button
                    type="button"
                    className="gov-btn gov-btn-primary"
                    onClick={handleReleaseBlock}
                    disabled={actionLoading}
                    style={{ background: "#2563eb", fontWeight: 700 }}
                  >
                    {actionLoading ? "Releasing Block..." : "🚀 Release Emergency Block & Restore Section"}
                  </button>
                )}

                {incident.status === "RELEASED" && (
                  <button
                    type="button"
                    className="gov-btn gov-btn-secondary"
                    onClick={handleClose}
                    disabled={actionLoading}
                    style={{ fontWeight: 700 }}
                  >
                    {actionLoading ? "Closing..." : "🔒 Formally Close Incident"}
                  </button>
                )}
              </div>
            </div>
          )}
        </div>
      </AppShell>
    </ProtectedRoute>
  );
}
