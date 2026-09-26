"use client";

import React, { useCallback, useEffect, useState } from "react";
import { useParams } from "next/navigation";
import ProtectedRoute from "@/components/ProtectedRoute";
import AppShell from "@/components/AppShell";
import Breadcrumbs from "@/components/Breadcrumbs";
import { api, ApiError } from "@/lib/api-client";
import { useAuth } from "@/lib/auth-context";
import type { MaintenanceRequest, ReviewHistoryItem } from "@/types/maintenance";
import type { UnifiedPredictionResult } from "@/types/ml";
import type { MaintenanceAreaOut, MaintenanceAreaCreate, MaintenanceAreaUpdate } from "@/types/maintenance";
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
  const [prediction, setPrediction] = useState<UnifiedPredictionResult | null>(null);
  const [predLoading, setPredLoading] = useState(false);
  const [predRunning, setPredRunning] = useState(false);
  const [predError, setPredError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [actionLoading, setActionLoading] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);
  const [newStatus, setNewStatus] = useState("SUBMITTED");
  const [reason, setReason] = useState("");
  const [editDesc, setEditDesc] = useState("");
  const [editPriority, setEditPriority] = useState("");
  const [area, setArea] = useState<MaintenanceAreaOut | null>(null);
  const [areaLoading, setAreaLoading] = useState(false);
  const [areaError, setAreaError] = useState<string | null>(null);
  const [areaEditing, setAreaEditing] = useState(false);
  const [areaSaving, setAreaSaving] = useState(false);
  const [areaSaveError, setAreaSaveError] = useState<string | null>(null);
  const [formSection, setFormSection] = useState("");
  const [formTrack, setFormTrack] = useState("");
  const [formStart, setFormStart] = useState("");
  const [formEnd, setFormEnd] = useState("");
  const { user } = useAuth();

  const loadPrediction = useCallback(async () => {
    setPredLoading(true);
    setPredError(null);
    try {
      const p = await api.get<UnifiedPredictionResult>(`/api/ml/predictions/${id}`);
      setPrediction(p);
    } catch {
      setPrediction(null);
    } finally {
      setPredLoading(false);
    }
  }, [id]);

  const loadArea = useCallback(async () => {
    setAreaLoading(true);
    setAreaError(null);
    try {
      const a = await api.get<MaintenanceAreaOut>(`/api/maintenance/requests/${id}/maintenance-area`);
      setArea(a);
    } catch (err) {
      // Area might not exist yet, which is fine
      setArea(null);
      setAreaError(err instanceof ApiError ? err.message : "Unable to load maintenance area");
    } finally {
      setAreaLoading(false);
    }
  }, [id]);

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
      void loadPrediction();
      void loadArea();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Unable to connect to the railway service. Please try again.");
    } finally {
      setLoading(false);
    }
  }, [id, loadPrediction, loadArea]);

  const runPrediction = async () => {
    setPredRunning(true);
    setPredError(null);
    try {
      const result = await api.post<UnifiedPredictionResult>(`/api/ml/predict/maintenance-request/${id}`, {});
      setPrediction(result);
    } catch (err) {
      setPredError(err instanceof ApiError ? err.message : "AI Prediction service encountered an error.");
    } finally {
      setPredRunning(false);
    }
  };

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

  const canDefineArea = user?.role === "SENIOR_SECTION_ENGINEER";

  const areaLengthPreview = (() => {
    const s = parseFloat(formStart);
    const e = parseFloat(formEnd);
    if (!Number.isFinite(s) || !Number.isFinite(e) || e <= s) return "—";
    return (e - s).toFixed(3);
  })();

  useEffect(() => {
    if (data) {
      setFormSection((v) => v || String(data.section_id));
      setFormTrack((v) => v || (data.track_id ? String(data.track_id) : ""));
    }
  }, [data]);

  useEffect(() => {
    if (area && !areaEditing) {
      setFormStart(String(area.start_km));
      setFormEnd(String(area.end_km));
    }
  }, [area, areaEditing]);

  async function onSaveArea(e: React.FormEvent) {
    e.preventDefault();
    if (areaSaving) return;
    const sectionId = parseInt(formSection, 10);
    const trackId = parseInt(formTrack, 10);
    const start = parseFloat(formStart);
    const end = parseFloat(formEnd);
    if (!Number.isInteger(sectionId) || sectionId <= 0 || !Number.isInteger(trackId) || trackId <= 0) {
      setAreaSaveError("Valid Section ID and Track ID are required.");
      return;
    }
    if (!Number.isFinite(start) || !Number.isFinite(end) || start <= 0 || end <= 0) {
      setAreaSaveError("Start KM and End KM must be positive numbers.");
      return;
    }
    if (end <= start) {
      setAreaSaveError("End KM must be greater than Start KM.");
      return;
    }
    setAreaSaving(true);
    setAreaSaveError(null);
    try {
      const saved = area
        ? await api.put<MaintenanceAreaOut>(`/api/maintenance/requests/${id}/maintenance-area`, { start_km: start, end_km: end })
        : await api.post<MaintenanceAreaOut>(`/api/maintenance/requests/${id}/maintenance-area`, {
            section_id: sectionId,
            track_id: trackId,
            start_km: start,
            end_km: end,
          });
      setArea(saved);
      setAreaError(null);
      setAreaEditing(false);
    } catch (err) {
      setAreaSaveError(err instanceof ApiError ? err.message : "Unable to save the maintenance area.");
    } finally {
      setAreaSaving(false);
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

          {/* AI / ML Prediction Summary */}
          <div className="gov-card gov-card-accent">
            <div className="gov-section-header" style={{ display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: 8 }}>
              <div>
                <h3 className="gov-section-title">AI / ML Impact &amp; Risk Assessment</h3>
                <p className="gov-section-sub">
                  Automated analytics powered by Random Forest regression &amp; operational risk pipelines.
                </p>
              </div>
              <button
                type="button"
                className="gov-btn gov-btn-sm"
                onClick={runPrediction}
                disabled={predRunning}
              >
                {predRunning ? "Running Prediction Pipeline…" : prediction ? "Re-run AI Prediction" : "Run AI Prediction"}
              </button>
            </div>

            {predError && (
              <div className="gov-alert gov-alert-error" role="alert" style={{ marginTop: 12 }}>
                {predError}
              </div>
            )}

            {predLoading ? (
              <div className="gov-loading" style={{ margin: "16px 0" }}>Checking previous AI predictions…</div>
            ) : prediction ? (
              <div style={{ marginTop: 16 }}>
                {prediction.is_stale && (
                  <div className="gov-alert gov-alert-warning" style={{ marginBottom: 12 }}>
                    Prediction inputs have changed since this estimate was generated. Consider re-running the prediction.
                  </div>
                )}
                
                <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))", gap: 12, marginBottom: 16 }}>
                  <div style={{ padding: 12, background: "#f8fafc", borderRadius: 8, border: "1px solid #e2e8f0" }}>
                    <div className="gov-stat-label">Predicted Duration</div>
                    <div style={{ fontSize: 20, fontWeight: 700, color: "#0f172a" }}>
                      {prediction.duration ? `${prediction.duration.predicted_duration_minutes} mins` : "—"}
                    </div>
                    {prediction.duration?.confidence_interval_lower_mins != null && (
                      <div className="gov-muted" style={{ fontSize: 12 }}>
                        95% CI: {prediction.duration.confidence_interval_lower_mins} – {prediction.duration.confidence_interval_upper_mins}m
                      </div>
                    )}
                  </div>

                  <div style={{ padding: 12, background: "#f8fafc", borderRadius: 8, border: "1px solid #e2e8f0" }}>
                    <div className="gov-stat-label">Operational Risk</div>
                    <div style={{ fontSize: 20, fontWeight: 700, color: prediction.risk?.risk_level === "CRITICAL" || prediction.risk?.risk_level === "HIGH" ? "#dc2626" : "#059669" }}>
                      {prediction.risk?.risk_level ?? "LOW"}
                    </div>
                    {prediction.risk?.risk_probability != null && (
                      <div className="gov-muted" style={{ fontSize: 12 }}>
                        Probability: {(prediction.risk.risk_probability * 100).toFixed(1)}%
                      </div>
                    )}
                  </div>

                  <div style={{ padding: 12, background: "#f8fafc", borderRadius: 8, border: "1px solid #e2e8f0" }}>
                    <div className="gov-stat-label">Affected Trains</div>
                    <div style={{ fontSize: 20, fontWeight: 700, color: "#0f172a" }}>
                      {prediction.train_impact?.affected_train_count ?? 0} trains
                    </div>
                    <div className="gov-muted" style={{ fontSize: 12 }}>
                      Impact: {prediction.train_impact?.impact_level ?? "LOW"}
                    </div>
                  </div>

                  <div style={{ padding: 12, background: "#f8fafc", borderRadius: 8, border: "1px solid #e2e8f0" }}>
                    <div className="gov-stat-label">Total Induced Delay</div>
                    <div style={{ fontSize: 20, fontWeight: 700, color: (prediction.train_impact?.total_predicted_delay_minutes ?? 0) > 60 ? "#d97706" : "#0f172a" }}>
                      {prediction.train_impact?.total_predicted_delay_minutes ?? 0} mins
                    </div>
                    <div className="gov-muted" style={{ fontSize: 12 }}>
                      Max delay: {prediction.train_impact?.maximum_predicted_delay_minutes ?? 0}m
                    </div>
                  </div>
                </div>

                <div className="gov-muted" style={{ fontSize: 12, display: "flex", justifyContent: "space-between", flexWrap: "wrap", borderTop: "1px solid #e2e8f0", paddingTop: 8 }}>
                  <span>Generated: {fmt(prediction.predicted_at)} ({prediction.is_demo ? "Demo Mode" : "Production ML Pipeline"})</span>
                  <a href="/ml" style={{ color: "var(--gov-navy, #1e3a8a)", textDecoration: "underline", fontWeight: 500 }}>
                    Open ML Hub for In-Depth Analytics →
                  </a>
                </div>
              </div>
            ) : (
              <p className="gov-muted" style={{ marginTop: 12 }}>
                No AI prediction has been generated for this request yet. Click <strong>Run AI Prediction</strong> to assess operational risks, estimated completion duration, and train delay impact.
              </p>
            )}
          </div>

        {/* Maintenance Area Definition */}
        <div className="gov-card">
          <div className="gov-section-header">
            <h3 className="gov-section-title">Maintenance Area Definition</h3>
          </div>
          {areaLoading ? (
            <div className="gov-loading">Loading maintenance area…</div>
          ) : (
            <div>
              {areaError && !area ? (
                <div className="gov-alert gov-alert-warning" role="alert">{areaError}</div>
              ) : null}

              {area ? (
                <div>
                  <div className="gov-section-header" style={{ marginBottom: 12 }}>
                    <h4 className="gov-section-title" style={{ fontSize: "0.95rem" }}>Defined Area</h4>
                  </div>
                  <div className="gov-kv-grid" style={{ marginBottom: 16 }}>
                    <div className="gov-kv-label">Section</div>
                    <div className="gov-kv-value">{area.section_id}</div>
                    <div className="gov-kv-label">Track</div>
                    <div className="gov-kv-value">{area.track_id ?? "—"}</div>
                    <div className="gov-kv-label">Start KM</div>
                    <div className="gov-kv-value">{area.start_km}</div>
                    <div className="gov-kv-label">End KM</div>
                    <div className="gov-kv-value">{area.end_km}</div>
                    <div className="gov-kv-label">Length (KM)</div>
                    <div className="gov-kv-value"><strong>{area.length_km}</strong></div>
                    <div className="gov-kv-label">Defined By</div>
                    <div className="gov-kv-value">{area.defined_by_name ?? `User ${area.defined_by}`}</div>
                    <div className="gov-kv-label">Created</div>
                    <div className="gov-kv-value">{fmt(area.created_at)}</div>
                  </div>
                  {/* Schematic Timeline */}
                  <div className="gov-info-box" style={{ marginTop: 12 }}>
                    <strong>Track Schematic:</strong>
                    <div style={{ marginTop: 8, position: "relative", height: 40, background: "#f1f5f9", borderRadius: 4, overflow: "hidden" }}>
                      <div
                        style={{
                          position: "absolute",
                          left: 0,
                          top: 0,
                          width: "100%",
                          height: "100%",
                          background: "linear-gradient(90deg, #e2e8f0 0%, #e2e8f0 100%)",
                        }}
                      />
                      <div
                        style={{
                          position: "absolute",
                          left: "0%",
                          width: "100%",
                          height: "100%",
                          background: "linear-gradient(90deg, #3b82f6 0%, #3b82f6 100%)",
                          opacity: 0.3,
                        }}
                      />
                      <div
                        style={{
                          position: "absolute",
                          left: `${((area.start_km || 0) / (area.end_km || 1)) * 100}%`,
                          width: `${Math.max(0, ((area.end_km || 1) - (area.start_km || 0)) / (area.end_km || 1)) * 100}%`,
                          height: "100%",
                          background: "#1e3a5f",
                          borderRadius: 2,
                        }}
                      >
                        <div style={{ padding: "2px 6px", color: "white", fontSize: "0.7rem", whiteSpace: "nowrap" }}>
                          {area.start_km}–{area.end_km} km ({area.length_km} km)
                        </div>
                      </div>
                    </div>
                  </div>
                </div>
              ) : null}

              {!area && !areaLoading ? (
                <div className="gov-empty">
                  <p>No maintenance area defined for this request.</p>
                  <p className="gov-muted" style={{ marginTop: 4 }}>
                    {canDefineArea
                      ? "Define the maintenance area below using Section, Track, Start KM, and End KM."
                      : "Only SSE can define the maintenance area."}
                  </p>
                </div>
              ) : null}

              {canDefineArea ? (
                <div style={{ marginTop: 16 }}>
                  <div className="gov-section-header" style={{ marginBottom: 12 }}>
                    <h4 className="gov-section-title" style={{ fontSize: "0.95rem" }}>
                      {area && areaEditing ? "Edit Maintenance Area" : area ? "Maintenance Area" : "Define Maintenance Area"}
                    </h4>
                  </div>

                  {areaSaveError ? (
                    <div className="gov-alert gov-alert-error" role="alert" style={{ marginBottom: 12 }}>
                      {areaSaveError}
                    </div>
                  ) : null}

                  {!area || areaEditing ? (
                    <form onSubmit={onSaveArea} style={{ display: "flex", gap: 12, flexWrap: "wrap", alignItems: "end" }}>
                      <div>
                        <label className="gov-label" htmlFor="ma-section">Section ID</label>
                        <input
                          id="ma-section"
                          className="gov-input"
                          type="number"
                          min={1}
                          value={formSection}
                          onChange={(e) => setFormSection(e.target.value)}
                          disabled={areaSaving}
                          required
                        />
                      </div>
                      <div>
                        <label className="gov-label" htmlFor="ma-track">Track ID</label>
                        <input
                          id="ma-track"
                          className="gov-input"
                          type="number"
                          min={1}
                          value={formTrack}
                          onChange={(e) => setFormTrack(e.target.value)}
                          disabled={areaSaving}
                          required
                        />
                      </div>
                      <div>
                        <label className="gov-label" htmlFor="ma-start">Start KM</label>
                        <input
                          id="ma-start"
                          className="gov-input"
                          type="number"
                          step="0.001"
                          min="0.001"
                          value={formStart}
                          onChange={(e) => setFormStart(e.target.value)}
                          disabled={areaSaving}
                          required
                        />
                      </div>
                      <div>
                        <label className="gov-label" htmlFor="ma-end">End KM</label>
                        <input
                          id="ma-end"
                          className="gov-input"
                          type="number"
                          step="0.001"
                          min="0.001"
                          value={formEnd}
                          onChange={(e) => setFormEnd(e.target.value)}
                          disabled={areaSaving}
                          required
                        />
                      </div>
                      <div>
                        <label className="gov-label">Length (KM)</label>
                        <div style={{ fontWeight: 700, lineHeight: "40px" }}>{areaLengthPreview}</div>
                      </div>
                      <div style={{ display: "flex", gap: 8 }}>
                        <button className="gov-btn gov-btn-primary" type="submit" disabled={areaSaving}>
                          {areaSaving ? "Saving…" : area ? "Save Changes" : "Define Area"}
                        </button>
                        {area && areaEditing ? (
                          <button
                            className="gov-btn"
                            type="button"
                            disabled={areaSaving}
                            onClick={() => {
                              setAreaEditing(false);
                              setAreaSaveError(null);
                              setFormStart(String(area.start_km));
                              setFormEnd(String(area.end_km));
                            }}
                          >
                            Cancel
                          </button>
                        ) : null}
                      </div>
                    </form>
                  ) : (
                    <button
                      className="gov-btn"
                      type="button"
                      onClick={() => {
                        setAreaEditing(true);
                        setAreaSaveError(null);
                      }}
                    >
                      Edit Maintenance Area
                    </button>
                  )}
                </div>
              ) : null}
            </div>
          )}
        </div>
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
