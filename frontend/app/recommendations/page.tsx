"use client";

import React, { useState } from "react";
import Link from "next/link";
import ProtectedRoute from "@/components/ProtectedRoute";
import AppShell from "@/components/AppShell";
import Breadcrumbs from "@/components/Breadcrumbs";
import { api, ApiError } from "@/lib/api-client";
import type {
  LatestOptimization,
  OptimizationHistoryResponse,
  OptimizeRunResult,
} from "@/types/recommendations";

export default function RecommendationsPage() {
  return (
    <ProtectedRoute>
      <AppShell>
        <RecContent />
      </AppShell>
    </ProtectedRoute>
  );
}

function errMsg(err: unknown): string {
  return err instanceof ApiError ? err.message : "Unable to connect to the railway service. Please try again.";
}

function RecContent() {
  const [obId, setObId] = useState("");

  const [optBlock, setOptBlock] = useState("");
  const [optLoading, setOptLoading] = useState(false);
  const [optError, setOptError] = useState<string | null>(null);
  const [optResult, setOptResult] = useState<OptimizeRunResult | null>(null);

  const [latestBlock, setLatestBlock] = useState("");
  const [latestLoading, setLatestLoading] = useState(false);
  const [latestError, setLatestError] = useState<string | null>(null);
  const [latest, setLatest] = useState<LatestOptimization | null>(null);
  const [hist, setHist] = useState<OptimizationHistoryResponse | null>(null);

  async function onOptimize(e: React.FormEvent) {
    e.preventDefault();
    if (optLoading || optBlock.trim() === "") return;
    setOptLoading(true);
    setOptError(null);
    setOptResult(null);
    try {
      const r = await api.post<OptimizeRunResult>(`/api/optimization/blocks/${optBlock.trim()}/optimize`, {});
      setOptResult(r);
    } catch (err) {
      setOptError(
        err instanceof ApiError && err.status === 403
          ? "Your role cannot run optimization (Engineer Reviewer, Controller, or Authorized Official required)."
          : errMsg(err)
      );
    } finally {
      setOptLoading(false);
    }
  }

  async function onLatest(e: React.FormEvent) {
    e.preventDefault();
    if (latestLoading || latestBlock.trim() === "") return;
    setLatestLoading(true);
    setLatestError(null);
    setLatest(null);
    setHist(null);
    try {
      const id = latestBlock.trim();
      const l = await api.get<LatestOptimization>(`/api/optimization/blocks/${id}`);
      setLatest(l);
      try {
        const h = await api.get<OptimizationHistoryResponse>(`/api/optimization/blocks/${id}/history`);
        setHist(h);
      } catch {
        setHist(null);
      }
    } catch (err) {
      setLatestError(errMsg(err));
    } finally {
      setLatestLoading(false);
    }
  }

  return (
    <div className="gov-page">
      <Breadcrumbs trail={[{ label: "Dashboard", href: "/dashboard" }, { label: "Recommendations" }]} />

      <div className="gov-page-header">
        <div>
          <h2 className="gov-title">Recommendations — OR-Tools Optimization</h2>
          <p className="gov-sub">
            Optimization output is a recommendation only. Only SAFE candidates are eligible, and only an
            Authorized Official can approve. Access is per optimized block or per block request.
          </p>
        </div>
      </div>

      <div className="gov-card">
        <div className="gov-section-header">
          <h3>Open a Recommendation</h3>
        </div>
        <form
          onSubmit={(e) => e.preventDefault()}
          style={{ display: "flex", gap: 12, alignItems: "end", flexWrap: "wrap" }}
        >
          <div style={{ flex: 1, minWidth: 200 }}>
            <label className="gov-label" htmlFor="rec-ob">Optimized Block ID *</label>
            <input
              id="rec-ob"
              className="gov-input"
              inputMode="numeric"
              value={obId}
              onChange={(e) => setObId(e.target.value)}
              placeholder="e.g. 5"
            />
          </div>
          {obId.trim() !== "" ? (
            <Link className="gov-btn" style={{ textDecoration: "none", textAlign: "center" }} href={`/recommendations/${obId.trim()}`}>
              Open Recommendation
            </Link>
          ) : (
            <button className="gov-btn" type="submit" disabled>
              Open Recommendation
            </button>
          )}
        </form>
      </div>

      <div className="gov-card">
        <div className="gov-section-header">
          <h3>Run Optimization for a Block Request</h3>
        </div>
        <div className="gov-info-box">
          Runs the backend OR-Tools optimizer with the Safety Engine gate. Only SAFE candidates are
          eligible; unsafe candidates are excluded and reported.
        </div>
        <form onSubmit={onOptimize} style={{ display: "flex", gap: 12, alignItems: "end", flexWrap: "wrap" }}>
          <div style={{ flex: 1, minWidth: 200 }}>
            <label className="gov-label" htmlFor="rec-opt">Block Request ID *</label>
            <input
              id="rec-opt"
              className="gov-input"
              inputMode="numeric"
              value={optBlock}
              onChange={(e) => setOptBlock(e.target.value)}
              placeholder="e.g. 3"
              required
            />
          </div>
          <button className="gov-btn" type="submit" disabled={optLoading}>
            {optLoading ? "Optimizing…" : "Run Optimization"}
          </button>
        </form>
        {optError ? <div className="gov-alert gov-alert-error" role="alert" style={{ marginTop: 12 }}>{optError}</div> : null}
        {optResult ? (
          <div style={{ marginTop: 12 }}>
            <div className="gov-kv-grid">
              <span className="gov-kv-label">Status</span>
              <span className="gov-kv-value">
                <span className={`gov-badge gov-badge-${optResult.status === "OPTIMIZED" ? "green" : optResult.status === "FAILED" ? "red" : "amber"}`}>{optResult.status}</span>
              </span>
              {optResult.reason ? (
                <>
                  <span className="gov-kv-label">Reason</span>
                  <span className="gov-kv-value">{optResult.reason}</span>
                </>
              ) : null}
              {optResult.optimized_block_id != null ? (
                <>
                  <span className="gov-kv-label">Optimized Block</span>
                  <span className="gov-kv-value">{optResult.optimized_block_code ?? optResult.optimized_block_id}</span>
                </>
              ) : null}
              {optResult.selected_candidate_id != null ? (
                <>
                  <span className="gov-kv-label">Selected Candidate</span>
                  <span className="gov-kv-value">{optResult.selected_candidate_id}</span>
                </>
              ) : null}
              {optResult.optimization_score != null ? (
                <>
                  <span className="gov-kv-label">Optimization Score</span>
                  <span className="gov-kv-value">{optResult.optimization_score}</span>
                </>
              ) : null}
              {optResult.total_considered != null ? (
                <>
                  <span className="gov-kv-label">Considered / Eligible</span>
                  <span className="gov-kv-value">{optResult.total_considered} / {optResult.eligible ?? "—"}</span>
                </>
              ) : null}
            </div>
            {optResult.explanation ? <p className="gov-muted" style={{ marginTop: 12 }}>{optResult.explanation}</p> : null}
            {optResult.disclaimer ? <p className="gov-muted">{optResult.disclaimer}</p> : null}
            {optResult.excluded_details && optResult.excluded_details.length > 0 ? (
              <div style={{ marginTop: 12 }}>
                <div className="gov-section-header">
                  <h4>Excluded Candidates</h4>
                </div>
                <ul className="gov-list">
                  {optResult.excluded_details.map((x) => (
                    <li key={x.candidate_id}>Candidate {x.candidate_id}: {x.reason}</li>
                  ))}
                </ul>
              </div>
            ) : null}
            {optResult.optimized_block_id != null ? (
              <p style={{ marginTop: 8 }}>
                <Link className="gov-link" href={`/recommendations/${optResult.optimized_block_id}`}>
                  Open Recommendation #{optResult.optimized_block_id}
                </Link>
              </p>
            ) : null}
          </div>
        ) : null}
      </div>

      <div className="gov-card">
        <div className="gov-section-header">
          <h3>Latest Optimization &amp; History by Block Request</h3>
        </div>
        <form onSubmit={onLatest} style={{ display: "flex", gap: 12, alignItems: "end", flexWrap: "wrap" }}>
          <div style={{ flex: 1, minWidth: 200 }}>
            <label className="gov-label" htmlFor="rec-latest">Block Request ID *</label>
            <input
              id="rec-latest"
              className="gov-input"
              inputMode="numeric"
              value={latestBlock}
              onChange={(e) => setLatestBlock(e.target.value)}
              placeholder="e.g. 3"
              required
            />
          </div>
          <button className="gov-btn gov-btn-secondary" type="submit" disabled={latestLoading}>
            {latestLoading ? "Loading…" : "Load Latest"}
          </button>
        </form>
        {latestError ? <div className="gov-alert gov-alert-error" role="alert" style={{ marginTop: 12 }}>{latestError}</div> : null}
        {latest ? (
          <div style={{ marginTop: 12 }}>
            <div className="gov-kv-grid">
              <span className="gov-kv-label">Optimized Block</span>
              <span className="gov-kv-value">
                <Link className="gov-link" href={`/recommendations/${latest.optimized_block_id}`}>{latest.block_code}</Link>
              </span>
              <span className="gov-kv-label">Status</span>
              <span className="gov-kv-value">
                <span className={`gov-badge gov-badge-${latest.status === "APPROVED" ? "green" : latest.status === "REJECTED" ? "red" : "amber"}`}>{latest.status}</span>
              </span>
              <span className="gov-kv-label">Window</span>
              <span className="gov-kv-value">
                {latest.start_time ? new Date(latest.start_time).toLocaleString() : "—"} → {latest.end_time ? new Date(latest.end_time).toLocaleString() : "—"}
              </span>
              <span className="gov-kv-label">Optimization Score</span>
              <span className="gov-kv-value">{latest.optimization_score ?? "—"}</span>
              <span className="gov-kv-label">Reason</span>
              <span className="gov-kv-value">{latest.recommendation_reason ?? "—"}</span>
            </div>
            {hist && hist.history.length > 0 ? (
              <div style={{ marginTop: 16 }}>
                <div className="gov-section-header">
                  <h4>Optimization History ({hist.total})</h4>
                </div>
                <div className="gov-table-wrap">
                  <table className="gov-table">
                    <thead><tr><th>ID</th><th>Code</th><th>Score</th><th>Status</th><th>Created</th></tr></thead>
                    <tbody>
                      {hist.history.map((h) => (
                        <tr key={h.optimized_block_id}>
                          <td><Link className="gov-link" href={`/recommendations/${h.optimized_block_id}`}>{h.optimized_block_id}</Link></td>
                          <td>{h.block_code}</td>
                          <td>{h.optimization_score ?? "—"}</td>
                          <td><span className={`gov-badge gov-badge-${h.status === "APPROVED" ? "green" : h.status === "REJECTED" ? "red" : "amber"}`}>{h.status}</span></td>
                          <td>{h.created_at ? new Date(h.created_at).toLocaleString() : "—"}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            ) : null}
          </div>
        ) : null}
      </div>
    </div>
  );
}
