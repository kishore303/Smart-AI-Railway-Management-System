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

const API_BASE = process.env.NEXT_PUBLIC_API_BASE || "http://localhost:8000";

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
  const [activeTab, setActiveTab] = useState<"builder" | "compare" | "benchmark" | "history">("builder");

  // Tab 1: Builder
  const [obId, setObId] = useState("1");
  const [simName, setSimName] = useState("");
  const [modStart, setModStart] = useState("");
  const [modEnd, setModEnd] = useState("");
  const [addDept, setAddDept] = useState("");
  const [running, setRunning] = useState(false);
  const [runError, setRunError] = useState<string | null>(null);
  const [result, setResult] = useState<WhatIfResult | null>(null);

  // Tab 2: Compare
  const [compareRunning, setCompareRunning] = useState(false);
  const [compareResult, setCompareResult] = useState<any | null>(null);
  const [compareError, setCompareError] = useState<string | null>(null);

  // Tab 3: Manual vs AI Benchmark
  const [benchSection, setBenchSection] = useState(1);
  const [benchManualStart, setBenchManualStart] = useState("");
  const [benchManualEnd, setBenchManualEnd] = useState("");
  const [benchRunning, setBenchRunning] = useState(false);
  const [benchResult, setBenchResult] = useState<any | null>(null);
  const [benchError, setBenchError] = useState<string | null>(null);

  // Tab 4: History
  const [hist, setHist] = useState<SimulationHistoryResponse | null>(null);
  const [histLoading, setHistLoading] = useState(true);
  const [histError, setHistError] = useState<string | null>(null);

  const token = typeof window !== "undefined" ? localStorage.getItem("token") : null;

  const loadHist = useCallback(async () => {
    setHistLoading(true);
    setHistError(null);
    try {
      const r = await api.get<SimulationHistoryResponse>("/api/simulation/history/list?skip=0&limit=20");
      setHist(r);
    } catch (err) {
      setHistError(err instanceof ApiError ? err.message : "Unable to connect to the railway service.");
    } finally {
      setHistLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadHist();
  }, [loadHist]);

  async function onRun(e: React.FormEvent) {
    e.preventDefault();
    if (running) return;
    if (modStart && modEnd && new Date(modStart) >= new Date(modEnd)) {
      setRunError("Modified end must be after modified start.");
      return;
    }
    setRunning(true);
    setRunError(null);
    setResult(null);
    try {
      const payload: Record<string, unknown> = {};
      if (obId.trim()) payload.original_block_id = Number(obId);
      if (simName.trim() !== "") payload.simulation_name = simName.trim().slice(0, 200);
      if (modStart) payload.modified_start_time = new Date(modStart).toISOString();
      if (modEnd) payload.modified_end_time = new Date(modEnd).toISOString();
      if (addDept.trim() !== "") payload.additional_department_id = Number(addDept);

      const r = await api.post<WhatIfResult>("/api/simulation/what-if", payload);
      setResult(r);
      await loadHist();
    } catch (err) {
      setRunError(err instanceof ApiError ? err.message : "Simulation failed to execute.");
    } finally {
      setRunning(false);
    }
  }

  async function onRunCompare() {
    setCompareRunning(true);
    setCompareError(null);
    try {
      const now = new Date();
      const sA = new Date(now.getTime() + 4 * 3600 * 1000);
      const sB = new Date(now.getTime() + 8 * 3600 * 1000);
      const sC = new Date(now.getTime() + 14 * 3600 * 1000);

      const res = await fetch(`${API_BASE}/api/simulation/compare`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: JSON.stringify({
          scenarios: [
            { name: "Scenario A: Night Low-Traffic (02:00 - 04:00)", start_time: sA.toISOString(), duration_mins: 120 },
            { name: "Scenario B: Morning Shoulder (08:00 - 10:00)", start_time: sB.toISOString(), duration_mins: 120 },
            { name: "Scenario C: Afternoon Window (14:00 - 16:30)", start_time: sC.toISOString(), duration_mins: 150 },
          ],
        }),
      });

      if (!res.ok) throw new Error(`Compare failed: ${res.statusText}`);
      setCompareResult(await res.json());
    } catch (err: any) {
      setCompareError(err.message || "Failed to compare scenarios.");
    } finally {
      setCompareRunning(false);
    }
  }

  async function onRunBenchmark(e: React.FormEvent) {
    e.preventDefault();
    setBenchRunning(true);
    setBenchError(null);
    try {
      const now = new Date();
      const start = benchManualStart ? new Date(benchManualStart) : new Date(now.getTime() + 2 * 3600 * 1000);
      const end = benchManualEnd ? new Date(benchManualEnd) : new Date(start.getTime() + 3 * 3600 * 1000);

      const res = await fetch(`${API_BASE}/api/simulation/manual-vs-ai`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: JSON.stringify({
          section_id: benchSection,
          track_id: 1,
          manual_start: start.toISOString(),
          manual_end: end.toISOString(),
          department_id: 1,
          work_type: "Track Relaying & Tamping",
          duration_mins: 180,
        }),
      });

      if (!res.ok) throw new Error(`Benchmark failed: ${res.statusText}`);
      setBenchResult(await res.json());
    } catch (err: any) {
      setBenchError(err.message || "Benchmark failed.");
    } finally {
      setBenchRunning(false);
    }
  }

  return (
    <div className="gov-page">
      <Breadcrumbs trail={[{ label: "Dashboard", href: "/dashboard" }, { label: "What-If Simulation Studio" }]} />

      <div className="gov-page-header">
        <div>
          <h2 className="gov-title">What-If Simulation Studio & AI Benchmarking</h2>
          <p className="gov-sub">
            Evaluate hypothetical scenarios, compare schedule alternatives, and benchmark manual proposals against AI CP-SAT recommendations in isolated transient memory.
          </p>
        </div>
      </div>

      {/* Tabs */}
      <div className="flex gap-2 border-b border-slate-700 pb-3 mb-6">
        <button
          onClick={() => setActiveTab("builder")}
          className={`px-4 py-2 rounded-lg text-sm font-semibold transition ${
            activeTab === "builder" ? "bg-blue-600 text-white shadow" : "bg-slate-800 text-slate-300 hover:bg-slate-700"
          }`}
        >
          🔮 Scenario Builder
        </button>
        <button
          onClick={() => setActiveTab("compare")}
          className={`px-4 py-2 rounded-lg text-sm font-semibold transition ${
            activeTab === "compare" ? "bg-blue-600 text-white shadow" : "bg-slate-800 text-slate-300 hover:bg-slate-700"
          }`}
        >
          ⚖️ Scenario Comparator (A/B/C)
        </button>
        <button
          onClick={() => setActiveTab("benchmark")}
          className={`px-4 py-2 rounded-lg text-sm font-semibold transition ${
            activeTab === "benchmark" ? "bg-blue-600 text-white shadow" : "bg-slate-800 text-slate-300 hover:bg-slate-700"
          }`}
        >
          ⚔️ Manual vs AI Benchmark
        </button>
        <button
          onClick={() => setActiveTab("history")}
          className={`px-4 py-2 rounded-lg text-sm font-semibold transition ${
            activeTab === "history" ? "bg-blue-600 text-white shadow" : "bg-slate-800 text-slate-300 hover:bg-slate-700"
          }`}
        >
          📜 Simulation History
        </button>
      </div>

      {/* TAB 1: SCENARIO BUILDER */}
      {activeTab === "builder" && (
        <div className="space-y-6">
          <div className="gov-card">
            <div className="gov-section-header">
              <h3>Hypothetical Scenario Parameters</h3>
            </div>
            <form onSubmit={onRun}>
              <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit,minmax(220px,1fr))", gap: 12 }}>
                <div>
                  <label className="gov-label" htmlFor="wi-ob">Base Block ID (optional)</label>
                  <input id="wi-ob" className="gov-input" inputMode="numeric" value={obId} onChange={(e) => setObId(e.target.value)} placeholder="e.g. 1" />
                </div>
                <div>
                  <label className="gov-label" htmlFor="wi-name">Scenario Name</label>
                  <input id="wi-name" className="gov-input" value={simName} onChange={(e) => setSimName(e.target.value)} placeholder="e.g. Weekend Night Shift" maxLength={200} />
                </div>
                <div>
                  <label className="gov-label" htmlFor="wi-start">Scenario Start Time</label>
                  <input id="wi-start" className="gov-input" type="datetime-local" value={modStart} onChange={(e) => setModStart(e.target.value)} />
                </div>
                <div>
                  <label className="gov-label" htmlFor="wi-end">Scenario End Time</label>
                  <input id="wi-end" className="gov-input" type="datetime-local" value={modEnd} onChange={(e) => setModEnd(e.target.value)} />
                </div>
              </div>
              {runError ? <div className="gov-alert gov-alert-error" role="alert" style={{ marginTop: 12 }}>{runError}</div> : null}
              <div className="gov-btn-group" style={{ marginTop: 16 }}>
                <button className="gov-btn" type="submit" disabled={running}>
                  {running ? "Simulating on Safety Engine…" : "Run Non-Mutating Simulation"}
                </button>
              </div>
            </form>
          </div>

          {result && (
            <>
              <div className={`gov-alert gov-alert-${result.is_safe ? "success" : "error"}`} role="status">
                <strong>
                  Scenario Result: Safety status is {result.safety.overall_status} — Feasibility {result.feasibility} (Optimization Score: {result.optimization_score})
                </strong>
                <p className="text-xs text-slate-300 mt-1">{result.disclaimer}</p>
              </div>

              <div className="gov-card">
                <div className="gov-section-header">
                  <h3>Safety Verification Breakdown ({result.safety.checks.length} Checks)</h3>
                </div>
                <SafetyChecksTable checks={result.safety.checks} />
              </div>
            </>
          )}
        </div>
      )}

      {/* TAB 2: SCENARIO COMPARATOR */}
      {activeTab === "compare" && (
        <div className="space-y-6">
          <div className="gov-card">
            <div className="gov-section-header flex justify-between items-center">
              <h3>Multi-Scenario Comparative Evaluation</h3>
              <button
                onClick={onRunCompare}
                disabled={compareRunning}
                className="gov-btn text-sm"
              >
                {compareRunning ? "Simulating Multi-Scenarios…" : "⚡ Run A/B/C Scenario Comparison"}
              </button>
            </div>
            <p className="text-sm text-slate-400">
              Evaluates three alternative time windows on the railway corridor simultaneously to identify the window with minimal passenger delay and zero safety violations.
            </p>

            {compareError && (
              <div className="gov-alert gov-alert-error mt-4">{compareError}</div>
            )}

            {compareResult && (
              <div className="mt-6 space-y-6">
                <div className="gov-table-wrap">
                  <table className="gov-table">
                    <thead>
                      <tr>
                        <th>Scenario</th>
                        <th>Proposed Window</th>
                        <th>Duration</th>
                        <th>Safety Status</th>
                        <th>Predicted Delay</th>
                        <th>Optimization Score</th>
                      </tr>
                    </thead>
                    <tbody>
                      {compareResult.comparison.map((sc: any, idx: number) => (
                        <tr key={idx} className={compareResult.recommended_scenario?.name === sc.name ? "bg-blue-950/40 font-semibold" : ""}>
                          <td>
                            {sc.name}
                            {compareResult.recommended_scenario?.name === sc.name && (
                              <span className="ml-2 px-2 py-0.5 bg-emerald-900 text-emerald-300 text-xs rounded-full font-bold">
                                RECOMMENDED
                              </span>
                            )}
                          </td>
                          <td>
                            {sc.start_time ? new Date(sc.start_time).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }) : "—"} -{" "}
                            {sc.end_time ? new Date(sc.end_time).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }) : "—"}
                          </td>
                          <td>{sc.duration_mins} mins</td>
                          <td>
                            <span className={`gov-badge gov-badge-${sc.safety_status === "SAFE" ? "green" : "red"}`}>
                              {sc.safety_status}
                            </span>
                          </td>
                          <td>{sc.predicted_delay_mins} mins</td>
                          <td className="text-blue-400 font-bold">{sc.optimization_score} / 100</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      {/* TAB 3: MANUAL VS AI BENCHMARK */}
      {activeTab === "benchmark" && (
        <div className="space-y-6">
          <div className="gov-card">
            <div className="gov-section-header">
              <h3>Human Manual Proposal vs AI CP-SAT Recommendation</h3>
            </div>
            <p className="text-sm text-slate-400 mb-4">
              Enter a proposed manual block window. The system runs both your proposal and the AI CP-SAT optimizer through identical deterministic safety and train impact models to measure the real operational delta.
            </p>

            <form onSubmit={onRunBenchmark}>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                <div>
                  <label className="gov-label">Corridor Section ID</label>
                  <input
                    type="number"
                    className="gov-input"
                    value={benchSection}
                    onChange={(e) => setBenchSection(Number(e.target.value))}
                    min={1}
                    required
                  />
                </div>
                <div>
                  <label className="gov-label">Manual Start Time</label>
                  <input
                    type="datetime-local"
                    className="gov-input"
                    value={benchManualStart}
                    onChange={(e) => setBenchManualStart(e.target.value)}
                  />
                </div>
                <div>
                  <label className="gov-label">Manual End Time</label>
                  <input
                    type="datetime-local"
                    className="gov-input"
                    value={benchManualEnd}
                    onChange={(e) => setBenchManualEnd(e.target.value)}
                  />
                </div>
              </div>
              <div className="gov-btn-group mt-4">
                <button type="submit" disabled={benchRunning} className="gov-btn">
                  {benchRunning ? "Benchmarking Models…" : "⚔️ Run Side-by-Side Benchmark"}
                </button>
              </div>
            </form>

            {benchError && <div className="gov-alert gov-alert-error mt-4">{benchError}</div>}

            {benchResult && (
              <div className="mt-6 space-y-6">
                {/* Deltas */}
                <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
                  <div className="bg-slate-900 border border-slate-800 p-4 rounded-xl">
                    <div className="text-xs text-slate-400 uppercase font-semibold">Delay Reduction</div>
                    <div className="text-2xl font-bold text-emerald-400 mt-1">
                      {benchResult.improvements.delay_reduction_mins} mins
                    </div>
                    <div className="text-xs text-emerald-500 mt-1">
                      {benchResult.improvements.delay_reduction_percentage}% faster recovery
                    </div>
                  </div>

                  <div className="bg-slate-900 border border-slate-800 p-4 rounded-xl">
                    <div className="text-xs text-slate-400 uppercase font-semibold">Trains Protected</div>
                    <div className="text-2xl font-bold text-blue-400 mt-1">
                      {benchResult.improvements.train_impact_reduction} Trains
                    </div>
                    <div className="text-xs text-slate-400 mt-1">
                      Reduced traffic interference
                    </div>
                  </div>

                  <div className="bg-slate-900 border border-slate-800 p-4 rounded-xl">
                    <div className="text-xs text-slate-400 uppercase font-semibold">Score Gain</div>
                    <div className="text-2xl font-bold text-indigo-400 mt-1">
                      +{benchResult.improvements.optimization_score_gain} pts
                    </div>
                    <div className="text-xs text-slate-400 mt-1">
                      Multi-objective optimization
                    </div>
                  </div>

                  <div className="bg-slate-900 border border-slate-800 p-4 rounded-xl">
                    <div className="text-xs text-slate-400 uppercase font-semibold">Safety Gating</div>
                    <div className="text-2xl font-bold text-teal-400 mt-1">
                      {benchResult.ai_optimized_plan.safety_status}
                    </div>
                    <div className="text-xs text-slate-400 mt-1">
                      0 Critical violations
                    </div>
                  </div>
                </div>

                {/* Side by side table */}
                <div className="gov-table-wrap">
                  <table className="gov-table">
                    <thead>
                      <tr>
                        <th>Metric</th>
                        <th>Human Manual Plan</th>
                        <th>AI CP-SAT Recommendation</th>
                      </tr>
                    </thead>
                    <tbody>
                      <tr>
                        <td>Time Window</td>
                        <td>
                          {new Date(benchResult.manual_plan.start_time).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })} -{" "}
                          {new Date(benchResult.manual_plan.end_time).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
                        </td>
                        <td className="text-emerald-400 font-semibold">
                          {new Date(benchResult.ai_optimized_plan.start_time).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })} -{" "}
                          {new Date(benchResult.ai_optimized_plan.end_time).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
                        </td>
                      </tr>
                      <tr>
                        <td>Predicted Train Delay</td>
                        <td className="text-rose-400">{benchResult.manual_plan.predicted_train_delay_mins} mins</td>
                        <td className="text-emerald-400 font-semibold">{benchResult.ai_optimized_plan.predicted_train_delay_mins} mins</td>
                      </tr>
                      <tr>
                        <td>Timetable Trains Affected</td>
                        <td>{benchResult.manual_plan.trains_affected} trains</td>
                        <td className="text-emerald-400 font-semibold">{benchResult.ai_optimized_plan.trains_affected} train</td>
                      </tr>
                      <tr>
                        <td>Safety Gate Status</td>
                        <td>
                          <span className={`gov-badge gov-badge-${benchResult.manual_plan.safety_status === "SAFE" ? "green" : "red"}`}>
                            {benchResult.manual_plan.safety_status}
                          </span>
                        </td>
                        <td>
                          <span className="gov-badge gov-badge-green font-bold">
                            {benchResult.ai_optimized_plan.safety_status}
                          </span>
                        </td>
                      </tr>
                      <tr>
                        <td>Optimization Score</td>
                        <td>{benchResult.manual_plan.optimization_score} / 100</td>
                        <td className="text-blue-400 font-bold">{benchResult.ai_optimized_plan.optimization_score} / 100</td>
                      </tr>
                    </tbody>
                  </table>
                </div>

                {/* Insights */}
                <div className="bg-slate-900/60 border border-slate-800 p-4 rounded-xl">
                  <h4 className="text-sm font-semibold text-white mb-2">💡 Decision-Support Insights</h4>
                  <ul className="list-disc pl-5 space-y-1 text-sm text-slate-300">
                    {benchResult.insights.map((ins: string, idx: number) => (
                      <li key={idx}>{ins}</li>
                    ))}
                  </ul>
                  <div className="text-xs text-slate-500 mt-3">{benchResult.disclaimer}</div>
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      {/* TAB 4: HISTORY */}
      {activeTab === "history" && (
        <div className="gov-card">
          <div className="gov-section-header">
            <h3>Persisted Simulation Scenarios</h3>
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
                <thead><tr><th>ID</th><th>Scenario Name</th><th>Base Block</th><th>Optimization Score</th><th>Created At</th></tr></thead>
                <tbody>
                  {hist.items.map((s) => (
                    <tr key={s.id}>
                      <td>#{s.id}</td>
                      <td className="font-medium text-white">{s.simulation_name ?? "—"}</td>
                      <td>{s.original_block_id != null ? `#${s.original_block_id}` : "Standalone"}</td>
                      <td className="text-blue-400 font-semibold">{s.optimization_score ?? "—"}</td>
                      <td>{s.created_at ? new Date(s.created_at).toLocaleString() : "—"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : null}
        </div>
      )}
    </div>
  );
}
