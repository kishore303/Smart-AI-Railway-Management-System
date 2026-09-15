"use client";

import React, { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import ProtectedRoute from "@/components/ProtectedRoute";
import AppShell from "@/components/AppShell";
import Breadcrumbs from "@/components/Breadcrumbs";
import SafetyChecksTable from "@/components/SafetyChecksTable";
import { api, ApiError } from "@/lib/api-client";
import type {
  BlockValidationsResponse,
  SafetyValidationResult,
  SafetyValidationSummary,
} from "@/types/safety";
import { safetyBadgeKind } from "@/types/safety";

export default function SafetyPage() {
  return (
    <ProtectedRoute>
      <AppShell>
        <SafetyContent />
      </AppShell>
    </ProtectedRoute>
  );
}

function friendlyError(err: unknown): string {
  if (err instanceof ApiError) {
    if (err.status === 403) return "You are not permitted to perform safety validation with your current role.";
    return err.message;
  }
  return "Unable to connect to the railway service. Please try again.";
}

function SafetyContent() {
  const [list, setList] = useState<SafetyValidationSummary[] | null>(null);
  const [listLoading, setListLoading] = useState(true);
  const [listError, setListError] = useState<string | null>(null);

  const [candId, setCandId] = useState("");
  const [validating, setValidating] = useState(false);
  const [valError, setValError] = useState<string | null>(null);
  const [result, setResult] = useState<SafetyValidationResult | null>(null);

  const [blockId, setBlockId] = useState("");
  const [histLoading, setHistLoading] = useState(false);
  const [histError, setHistError] = useState<string | null>(null);
  const [history, setHistory] = useState<BlockValidationsResponse | null>(null);

  const loadList = useCallback(async () => {
    setListLoading(true);
    setListError(null);
    try {
      const rows = await api.get<SafetyValidationSummary[]>("/api/safety/validations?limit=20");
      setList(rows);
    } catch (err) {
      setListError(friendlyError(err));
    } finally {
      setListLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadList();
  }, [loadList]);

  async function onValidate(e: React.FormEvent) {
    e.preventDefault();
    if (validating || candId.trim() === "") return;
    setValidating(true);
    setValError(null);
    setResult(null);
    try {
      const r = await api.post<SafetyValidationResult>(
        `/api/safety/validate/candidate/${candId.trim()}`,
        {}
      );
      setResult(r);
      void loadList();
    } catch (err) {
      setValError(friendlyError(err));
    } finally {
      setValidating(false);
    }
  }

  async function onHistory(e: React.FormEvent) {
    e.preventDefault();
    if (histLoading || blockId.trim() === "") return;
    setHistLoading(true);
    setHistError(null);
    setHistory(null);
    try {
      const r = await api.get<BlockValidationsResponse>(
        `/api/safety/validations/block/${blockId.trim()}`
      );
      setHistory(r);
    } catch (err) {
      setHistError(err instanceof ApiError ? err.message : "Unable to connect to the railway service. Please try again.");
    } finally {
      setHistLoading(false);
    }
  }

  return (
    <div className="gov-page">
      <Breadcrumbs trail={[{ label: "Dashboard", href: "/dashboard" }, { label: "Safety Validation" }]} />

      <div className="gov-page-header">
        <div>
          <h2 className="gov-title">Safety Validation — Safety Engine</h2>
          <p className="gov-sub">
            The backend Safety Engine is the sole authority on safety. ML predictions and planning-level
            FEASIBLE status are never safety approval. A SAFE result does not approve a block.
          </p>
        </div>
      </div>

      <div className="gov-card">
        <div className="gov-section-header">
          <h3 className="gov-section-title">Validate a Block Candidate</h3>
        </div>
        <p className="gov-muted" style={{ marginBottom: 12 }}>
          Select a candidate from Block Planning and run the 10-check Safety Engine validation.
          Allowed roles: Engineer Reviewer, Controller, Authorized Official, Emergency Operator.
        </p>
        <form onSubmit={onValidate} className="gov-filter-bar">
          <div style={{ flex: 1, minWidth: 200 }}>
            <label className="gov-label" htmlFor="sv-cand">Candidate ID <span className="gov-required">*</span></label>
            <input
              id="sv-cand"
              className="gov-input"
              inputMode="numeric"
              value={candId}
              onChange={(e) => setCandId(e.target.value)}
              placeholder="e.g. 7"
              required
            />
          </div>
          <button className="gov-btn" type="submit" disabled={validating}>
            {validating ? "Validating…" : "Run Safety Validation"}
          </button>
        </form>
        {valError ? <div className="gov-alert gov-alert-error" role="alert">{valError}</div> : null}
        {result ? (
          <div style={{ marginTop: 16 }}>
            <div className={result.overall_status === "SAFE" ? "gov-card gov-card-success" : "gov-card gov-card-danger"}>
              <div className="gov-section-header">
                <h3 className="gov-section-title">
                  <span className={`gov-badge gov-badge-${result.overall_status === "SAFE" ? "green" : "red"}`} style={{ marginRight: 8 }}>
                    {result.overall_status}
                  </span>
                  {result.overall_status === "SAFE" ? "Safety validation passed" : "Safety validation failed"}
                </h3>
              </div>
              {result.disclaimer ? <p className="gov-muted">{result.disclaimer}</p> : null}
              <div className="gov-kv-grid" style={{ marginTop: 12 }}>
                <div className="gov-kv-label">Candidate</div>
                <div className="gov-kv-value">{result.candidate_id}</div>
                <div className="gov-kv-label">Block Request</div>
                <div className="gov-kv-value">{result.block_request_id}</div>
                <div className="gov-kv-label">Safe for Optimization</div>
                <div className="gov-kv-value">{result.is_safe_for_optimization ? "Yes" : "No"}</div>
                <div className="gov-kv-label">Validated At</div>
                <div className="gov-kv-value">{result.validated_at ? new Date(result.validated_at).toLocaleString() : "—"}</div>
                <div className="gov-kv-label">Planning Status</div>
                <div className="gov-kv-value">{result.planning_safety_status ?? "—"}</div>
              </div>
            </div>

            {result.rejection_reasons.length > 0 ? (
              <div className="gov-card" style={{ marginTop: 12 }}>
                <div className="gov-section-header">
                  <h3 className="gov-section-title">Failure Reasons</h3>
                </div>
                <ul className="gov-list">
                  {result.rejection_reasons.map((r, i) => <li key={i}>{r}</li>)}
                </ul>
              </div>
            ) : null}

            {result.warnings.length > 0 ? (
              <div className="gov-card" style={{ marginTop: 12 }}>
                <div className="gov-section-header">
                  <h3 className="gov-section-title">Warnings</h3>
                </div>
                <ul className="gov-list">
                  {result.warnings.map((w, i) => <li key={i}>{w}</li>)}
                </ul>
              </div>
            ) : null}

            <div className="gov-card" style={{ marginTop: 12 }}>
              <div className="gov-section-header">
                <h3 className="gov-section-title">All Safety Checks ({result.checks.length})</h3>
              </div>
              <SafetyChecksTable checks={result.checks} />
            </div>

            <p style={{ marginTop: 12 }}>
              <Link className="gov-link" href={`/safety/${result.candidate_id}`}>Open persisted validation detail</Link>
            </p>
          </div>
        ) : null}
      </div>

      <div className="gov-card">
        <div className="gov-section-header">
          <h3 className="gov-section-title">Recent Safety Validations</h3>
        </div>
        {listLoading ? <div className="gov-loading">Loading validations…</div> : null}
        {listError && !listLoading ? <div className="gov-alert gov-alert-error" role="alert">{listError}</div> : null}
        {!listLoading && !listError && list && list.length === 0 ? (
          <div className="gov-empty"><p>No safety validations recorded yet.</p></div>
        ) : null}
        {!listLoading && !listError && list && list.length > 0 ? (
          <div className="gov-table-wrap">
            <table className="gov-table">
              <thead>
                <tr>
                  <th>Candidate</th>
                  <th>Block</th>
                  <th>Result</th>
                  <th>Safe for Opt.</th>
                  <th>Validated At</th>
                  <th>Detail</th>
                </tr>
              </thead>
              <tbody>
                {list.map((v) => (
                  <tr key={v.id}>
                    <td>{v.candidate_id}</td>
                    <td>{v.block_request_id}</td>
                    <td><span className={`gov-badge gov-badge-${safetyBadgeKind(v.overall_status)}`}>{v.overall_status}</span></td>
                    <td>{v.is_safe_for_optimization ? "Yes" : "No"}</td>
                    <td>{v.validated_at ? new Date(v.validated_at).toLocaleString() : "—"}</td>
                    <td><Link className="gov-btn gov-btn-sm" href={`/safety/${v.candidate_id}`}>View</Link></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : null}
      </div>

      <div className="gov-card">
        <div className="gov-section-header">
          <h3 className="gov-section-title">Validation History by Block Request</h3>
        </div>
        <form onSubmit={onHistory} className="gov-filter-bar">
          <div style={{ flex: 1, minWidth: 200 }}>
            <label className="gov-label" htmlFor="sv-block">Block Request ID <span className="gov-required">*</span></label>
            <input
              id="sv-block"
              className="gov-input"
              inputMode="numeric"
              value={blockId}
              onChange={(e) => setBlockId(e.target.value)}
              placeholder="e.g. 3"
              required
            />
          </div>
          <button className="gov-btn gov-btn-secondary" type="submit" disabled={histLoading}>
            {histLoading ? "Loading…" : "Load History"}
          </button>
        </form>
        {histError ? <div className="gov-alert gov-alert-error" role="alert">{histError}</div> : null}
        {history ? (
          <div style={{ marginTop: 12 }}>
            <div className="gov-info-box">
              Block #{history.block_id} — {history.total} candidate(s).
            </div>
            <div className="gov-table-wrap">
              <table className="gov-table">
                <thead>
                  <tr>
                    <th>Candidate</th>
                    <th>Window</th>
                    <th>Planning</th>
                    <th>Validated</th>
                    <th>Safety</th>
                    <th>Selected</th>
                  </tr>
                </thead>
                <tbody>
                  {history.validations.map((v) => (
                    <tr key={v.candidate_id}>
                      <td><Link className="gov-link" href={`/safety/${v.candidate_id}`}>{v.candidate_id}</Link></td>
                      <td>{new Date(v.candidate_start).toLocaleString()} → {new Date(v.candidate_end).toLocaleString()}</td>
                      <td>{v.planning_safety_status}</td>
                      <td>{v.validated ? "Yes" : "No"}</td>
                      <td>
                        {v.safety_validation ? (
                          <span className={`gov-badge gov-badge-${safetyBadgeKind(v.safety_validation.overall_status)}`}>
                            {v.safety_validation.overall_status}
                          </span>
                        ) : "—"}
                      </td>
                      <td>{v.is_selected ? "Yes" : "No"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        ) : null}
      </div>
    </div>
  );
}
