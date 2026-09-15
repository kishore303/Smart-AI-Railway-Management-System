"use client";

import React, { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import ProtectedRoute from "@/components/ProtectedRoute";
import AppShell from "@/components/AppShell";
import Breadcrumbs from "@/components/Breadcrumbs";
import SafetyChecksTable from "@/components/SafetyChecksTable";
import { api, ApiError } from "@/lib/api-client";
import type {
  SimulationHistoryResponse,
  SimulationRecord,
  WhatIfResult,
} from "@/types/simulation";
import { feasibilityBadgeKind } from "@/types/simulation";
import { safetyBadgeKind } from "@/types/safety";

export default function WhatIfPage() {
  return (
    <ProtectedRoute>
      <AppShell>
        <WhatIfContent />
      </AppShell>
    </ProtectedRoute>
  );
}

function WhatIfContent() {
  const [obId, setObId] = useState("");
  const [simName, setSimName] = useState("");
  const [modStart, setModStart] = useState("");
  const [modEnd, setModEnd] = useState("");
  const [addDept, setAddDept] = useState("");
  const [running, setRunning] = useState(false);
  const [runError, setRunError] = useState<string | null>(null);
  const [result, setResult] = useState<WhatIfResult | null>(null);

  const [hist, setHist] = useState<SimulationHistoryResponse | null>(null);
  const [histLoading, setHistLoading] = useState(true);
  const [histError, setHistError] = useState<string | null>(null);

  const [openId, setOpenId] = useState("");
  const [opened, setOpened] = useState<SimulationRecord | null>(null);
  const [openLoading, setOpenLoading] = useState(false);
  const [openError, setOpenError] = useState<string | null>(null);

  const loadHist = useCallback(async () => {
    setHistLoading(true);
    setHistError(null);
    try {
      const r = await api.get<SimulationHistoryResponse>("/api/simulation/history/list?skip=0&limit=20");
      setHist(r);
    } catch (err) {
      setHistError(err instanceof ApiError ? err.message : "Unable to connect to the railway service. Please try again.");
    } finally {
      setHistLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadHist();
  }, [loadHist]);

  async function onRun(e: React.FormEvent) {
    e.preventDefault();
    if (running || obId.trim() === "") return;
    if (modStart && modEnd && new Date(modStart) >= new Date(modEnd)) {
      setRunError("Modified end must be after modified start.");
      return;
    }
    setRunning(true);
    setRunError(null);
    setResult(null);
    try {
      const payload: Record<string, unknown> = { original_block_id: Number(obId) };
      if (simName.trim() !== "") payload.simulation_name = simName.trim().slice(0, 200);
      if (modStart) payload.modified_start_time = new Date(modStart).toISOString();
      if (modEnd) payload.modified_end_time = new Date(modEnd).toISOString();
      if (addDept.trim() !== "") payload.additional_department_id = Number(addDept);
      const r = await api.post<WhatIfResult>("/api/simulation/what-if", payload);
      setResult(r);
      await loadHist();
    } catch (err) {
      setRunError(err instanceof ApiError ? err.message : "Unable to connect to the railway service. Please try again.");
    } finally {
      setRunning(false);
    }
  }

  async function onOpen(e: React.FormEvent) {
    e.preventDefault();
    if (openLoading || openId.trim() === "") return;
    setOpenLoading(true);
    setOpenError(null);
    setOpened(null);
    try {
      const r = await api.get<SimulationRecord>(`/api/simulation/${openId.trim()}`);
      setOpened(r);
    } catch (err) {
      setOpenError(err instanceof ApiError ? err.message : "Unable to connect to the railway service. Please try again.");
    } finally {
      setOpenLoading(false);
    }
  }

  return (
    <div className="gov-page">
      <Breadcrumbs trail={[{ label: "Dashboard", href: "/dashboard" }, { label: "What-If Simulation" }]} />

      <div className="gov-page-header">
        <div>
          <h2 className="gov-title">What-If Simulation — Hypothetical Only</h2>
          <p className="gov-sub">
            Evaluate a hypothetical timing change against the backend Safety Engine without touching the
            real approved plan. A simulation never approves, executes, or allocates anything.
          </p>
        </div>
      </div>

      <div className="gov-card">
        <div className="gov-section-header">
          <h3>New Scenario</h3>
        </div>
        <form onSubmit={onRun}>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit,minmax(220px,1fr))", gap: 12 }}>
            <div>
              <label className="gov-label" htmlFor="wi-ob">Optimized Block ID *</label>
              <input id="wi-ob" className="gov-input" inputMode="numeric" value={obId} onChange={(e) => setObId(e.target.value)} placeholder="e.g. 5" required />
            </div>
            <div>
              <label className="gov-label" htmlFor="wi-name">Scenario Name (optional)</label>
              <input id="wi-name" className="gov-input" value={simName} onChange={(e) => setSimName(e.target.value)} maxLength={200} />
            </div>
            <div>
              <label className="gov-label" htmlFor="wi-start">Modified Start (optional)</label>
              <input id="wi-start" className="gov-input" type="datetime-local" value={modStart} onChange={(e) => setModStart(e.target.value)} />
            </div>
            <div>
              <label className="gov-label" htmlFor="wi-end">Modified End (optional)</label>
              <input id="wi-end" className="gov-input" type="datetime-local" value={modEnd} onChange={(e) => setModEnd(e.target.value)} />
            </div>
            <div>
              <label className="gov-label" htmlFor="wi-dept">Additional Department ID (optional)</label>
              <input id="wi-dept" className="gov-input" inputMode="numeric" value={addDept} onChange={(e) => setAddDept(e.target.value)} />
            </div>
          </div>
          {runError ? <div className="gov-alert gov-alert-error" role="alert" style={{ marginTop: 12 }}>{runError}</div> : null}
          <div className="gov-btn-group">
            <button className="gov-btn" type="submit" disabled={running}>
              {running ? "Running simulation…" : "Run What-If Simulation"}
            </button>
          </div>
        </form>
      </div>

      {result ? (
        <>
          <div className={`gov-alert gov-alert-${result.is_safe ? "success" : "error"}`} role="status">
            <strong>
              Scenario {result.simulation_id}: safety {result.safety.overall_status} — feasibility {result.feasibility}
            </strong>
            <span className="gov-muted"> — {result.disclaimer}</span>
          </div>

          <div className="gov-card">
            <div className="gov-section-header">
              <h3>Baseline vs What-If (Backend Comparison)</h3>
            </div>
            <div className="gov-table-wrap">
              <table className="gov-table">
                <thead><tr><th>Metric</th><th>Current / Baseline</th><th>What-If Scenario</th></tr></thead>
                <tbody>
                  <tr>
                    <td>Start</td>
                    <td>{result.comparison.baseline_start ? new Date(result.comparison.baseline_start).toLocaleString() : "—"}</td>
                    <td>{result.comparison.scenario_start ? new Date(result.comparison.scenario_start).toLocaleString() : "—"}</td>
                  </tr>
                  <tr>
                    <td>Duration (mins)</td>
                    <td>{result.comparison.baseline_duration ?? "—"}</td>
                    <td>{result.comparison.scenario_duration ?? "—"}</td>
                  </tr>
                  <tr>
                    <td>Safety</td>
                    <td><span className={`gov-badge gov-badge-${safetyBadgeKind(result.comparison.baseline_safety)}`}>{result.comparison.baseline_safety ?? "—"}</span></td>
                    <td><span className={`gov-badge gov-badge-${safetyBadgeKind(result.comparison.scenario_safety)}`}>{result.comparison.scenario_safety ?? "—"}</span></td>
                  </tr>
                  <tr>
                    <td>Optimization Score</td>
                    <td>{result.baseline.optimization_score ?? "—"}</td>
                    <td>{result.scenario.optimization_score ?? result.optimization_score ?? "—"}</td>
                  </tr>
                  <tr>
                    <td>Feasibility</td>
                    <td>—</td>
                    <td><span className={`gov-badge gov-badge-${feasibilityBadgeKind(result.feasibility)}`}>{result.feasibility}</span></td>
                  </tr>
                </tbody>
              </table>
            </div>
            <div className="gov-info-box" style={{ marginTop: 12 }}>Comparison values come from the backend response; no frontend calculation is used.</div>
          </div>

          {result.rejection_reasons.length > 0 ? (
            <div className="gov-card gov-card-danger">
              <div className="gov-section-header">
                <h3>Rejection Reasons</h3>
              </div>
              <ul className="gov-list">
                {result.rejection_reasons.map((r, i) => <li key={i}>{r}</li>)}
              </ul>
            </div>
          ) : null}
          {result.warnings.length > 0 ? (
            <div className="gov-card gov-card-warning">
              <div className="gov-section-header">
                <h3>Warnings</h3>
              </div>
              <ul className="gov-list">
                {result.warnings.map((w, i) => <li key={i}>{w}</li>)}
              </ul>
            </div>
          ) : null}

          <div className="gov-card">
            <div className="gov-section-header">
              <h3>Scenario Safety Checks ({result.safety.checks.length})</h3>
            </div>
            <SafetyChecksTable checks={result.safety.checks} />
          </div>
        </>
      ) : null}

      <div className="gov-card">
        <div className="gov-section-header">
          <h3>Scenario History</h3>
        </div>
        {histLoading ? <div className="gov-loading">Loading history…</div> : null}
        {histError && !histLoading ? <div className="gov-alert gov-alert-error" role="alert">{histError}</div> : null}
        {!histLoading && !histError && hist && hist.items.length === 0 ? (
          <div className="gov-empty">
            <div className="gov-empty-icon">📊</div>
            <p>No simulations recorded yet.</p>
          </div>
        ) : null}
        {!histLoading && !histError && hist && hist.items.length > 0 ? (
          <div className="gov-table-wrap">
            <table className="gov-table">
              <thead><tr><th>ID</th><th>Name</th><th>Block</th><th>Created</th></tr></thead>
              <tbody>
                {hist.items.map((s) => (
                  <tr key={s.id}>
                    <td>{s.id}</td>
                    <td>{s.simulation_name ?? "—"}</td>
                    <td>{s.original_block_id != null ? (
                      <Link className="gov-link" href={`/recommendations/${s.original_block_id}`}>{s.original_block_id}</Link>
                    ) : "—"}</td>
                    <td>{s.created_at ? new Date(s.created_at).toLocaleString() : "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : null}
        {!histLoading && !histError && hist && hist.items.length > 0 ? (
          <p className="gov-muted" style={{ marginTop: 8 }}>Total: {hist.total}</p>
        ) : null}
      </div>

      <div className="gov-card">
        <div className="gov-section-header">
          <h3>Open Persisted Scenario Record</h3>
        </div>
        <div className="gov-info-box">
          The record stores the scenario summary only; the full safety-check detail is shown at run time above.
        </div>
        <form onSubmit={onOpen} style={{ display: "flex", gap: 12, alignItems: "end", flexWrap: "wrap" }}>
          <div style={{ flex: 1, minWidth: 200 }}>
            <label className="gov-label" htmlFor="wi-open">Simulation ID *</label>
            <input id="wi-open" className="gov-input" inputMode="numeric" value={openId} onChange={(e) => setOpenId(e.target.value)} required />
          </div>
          <button className="gov-btn gov-btn-secondary" type="submit" disabled={openLoading}>
            {openLoading ? "Loading…" : "Open Record"}
          </button>
        </form>
        {openError ? <div className="gov-alert gov-alert-error" role="alert" style={{ marginTop: 12 }}>{openError}</div> : null}
        {opened ? (
          <div className="gov-kv-grid" style={{ marginTop: 12 }}>
            <span className="gov-kv-label">Name</span>
            <span className="gov-kv-value">{opened.simulation_name ?? "—"}</span>
            <span className="gov-kv-label">Original Block</span>
            <span className="gov-kv-value">
              {opened.original_block_id != null ? (
                <Link className="gov-link" href={`/recommendations/${opened.original_block_id}`}>{opened.original_block_id}</Link>
              ) : "—"}
            </span>
            <span className="gov-kv-label">Modified Window</span>
            <span className="gov-kv-value">
              {opened.modified_start_time ? new Date(opened.modified_start_time).toLocaleString() : "—"}
              {" → "}
              {opened.modified_end_time ? new Date(opened.modified_end_time).toLocaleString() : "—"}
            </span>
            <span className="gov-kv-label">Predicted Delay</span>
            <span className="gov-kv-value">
              {opened.predicted_delay_mins != null ? (
                <span className={`gov-badge gov-badge-${opened.predicted_delay_mins === 0 ? "green" : opened.predicted_delay_mins <= 10 ? "amber" : "red"}`}>
                  {opened.predicted_delay_mins} mins
                </span>
              ) : "—"}
            </span>
            <span className="gov-kv-label">Optimization Score</span>
            <span className="gov-kv-value">{opened.optimization_score ?? "—"}</span>
            <span className="gov-kv-label">Result Summary</span>
            <span className="gov-kv-value">{opened.result_summary ?? "—"}</span>
            <span className="gov-kv-label">Created</span>
            <span className="gov-kv-value">{opened.created_at ? new Date(opened.created_at).toLocaleString() : "—"}</span>
            <span className="gov-kv-label">Created By</span>
            <span className="gov-kv-value">{opened.created_by != null ? `User #${opened.created_by}` : "—"}</span>
          </div>
        ) : null}
      </div>
    </div>
  );
}
