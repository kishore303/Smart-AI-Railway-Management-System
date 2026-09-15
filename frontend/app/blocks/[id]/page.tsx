"use client";

import React, { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import ProtectedRoute from "@/components/ProtectedRoute";
import AppShell from "@/components/AppShell";
import Breadcrumbs from "@/components/Breadcrumbs";
import { api, ApiError } from "@/lib/api-client";
import type { BlockRequest, Candidate, CandidateGenerateResponse } from "@/types/blocks";
import { planningBadgeKind } from "@/types/blocks";

export default function BlockDetailPage() {
  const params = useParams<{ id: string }>();
  const id = params.id;
  return (
    <ProtectedRoute>
      <AppShell>
        <DetailContent blockId={id} />
      </AppShell>
    </ProtectedRoute>
  );
}

function DetailContent({ blockId }: { blockId: string }) {
  const [block, setBlock] = useState<BlockRequest | null>(null);
  const [candidates, setCandidates] = useState<Candidate[]>([]);
  const [selected, setSelected] = useState<Candidate | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [windowDays, setWindowDays] = useState(7);
  const [maxCand, setMaxCand] = useState(5);
  const [buffer, setBuffer] = useState(30);
  const [genLoading, setGenLoading] = useState(false);
  const [genError, setGenError] = useState<string | null>(null);
  const [genMsg, setGenMsg] = useState<string | null>(null);

  const loadCandidates = useCallback(async () => {
    const c = await api.get<Candidate[]>(`/api/blocks/requests/${blockId}/candidates`);
    setCandidates(c);
  }, [blockId]);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const b = await api.get<BlockRequest>(`/api/blocks/requests/${blockId}`);
      setBlock(b);
      await loadCandidates();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Unable to connect to the railway service. Please try again.");
    } finally {
      setLoading(false);
    }
  }, [blockId, loadCandidates]);

  useEffect(() => {
    void load();
  }, [load]);

  async function onGenerate(e: React.FormEvent) {
    e.preventDefault();
    if (genLoading) return;
    setGenError(null);
    setGenMsg(null);
    setGenLoading(true);
    try {
      const res = await api.post<CandidateGenerateResponse>(`/api/blocks/requests/${blockId}/candidates/generate`, {
        candidate_window_days: windowDays,
        max_candidates: maxCand,
        min_duration_buffer_mins: buffer,
      });
      setGenMsg(res.message);
      setCandidates(res.candidates);
    } catch (err) {
      setGenError(err instanceof ApiError ? err.message : "Unable to connect to the railway service. Please try again.");
    } finally {
      setGenLoading(false);
    }
  }

  async function onSelectCandidate(id: number) {
    try {
      const c = await api.get<Candidate>(`/api/blocks/candidates/${id}`);
      setSelected(c);
    } catch (err) {
      setGenError(err instanceof ApiError ? err.message : "Unable to load candidate details.");
    }
  }

  function blockStatusBadge(s: string) {
    if (s === "APPROVED" || s === "COMPLETED") return "gov-badge gov-badge-green";
    if (s === "REJECTED" || s === "CANCELLED") return "gov-badge gov-badge-red";
    return "gov-badge gov-badge-amber";
  }

  if (loading) {
    return (
      <div className="gov-page">
        <Breadcrumbs trail={[{ label: "Dashboard", href: "/dashboard" }, { label: "Block Planning", href: "/blocks" }, { label: `Block #${blockId}` }]} />
        <div className="gov-card"><div className="gov-loading">Loading block request…</div></div>
      </div>
    );
  }

  if (error || !block) {
    return (
      <div className="gov-page">
        <Breadcrumbs trail={[{ label: "Dashboard", href: "/dashboard" }, { label: "Block Planning", href: "/blocks" }, { label: `Block #${blockId}` }]} />
        <div className="gov-card">
          <div className="gov-alert gov-alert-error" role="alert">{error ?? "Block request not found."}</div>
          <p style={{ marginTop: 12 }}><Link className="gov-link" href="/blocks">Back to Block Planning</Link></p>
        </div>
      </div>
    );
  }

  return (
    <div className="gov-page">
      <Breadcrumbs
        trail={[
          { label: "Dashboard", href: "/dashboard" },
          { label: "Block Planning", href: "/blocks" },
          { label: block.block_code },
        ]}
      />

      <div className="gov-page-header">
        <div>
          <h2 className="gov-title">
            {block.block_code}{" "}
            <span className={blockStatusBadge(block.status)}>{block.status}</span>
          </h2>
          <p className="gov-sub">Block request details and candidate window generation.</p>
        </div>
        <Link className="gov-btn gov-btn-secondary" href="/blocks">Back to List</Link>
      </div>

      <div className="gov-card">
        <div className="gov-section-header">
          <h3 className="gov-section-title">Block Request Details</h3>
        </div>
        <div className="gov-kv-grid">
          <div className="gov-kv-label">Maintenance Request</div>
          <div className="gov-kv-value">{block.maintenance_request_id}</div>
          <div className="gov-kv-label">Section</div>
          <div className="gov-kv-value">{block.section_id}</div>
          <div className="gov-kv-label">Track</div>
          <div className="gov-kv-value">{block.track_id ?? "—"}</div>
          <div className="gov-kv-label">Requested Start</div>
          <div className="gov-kv-value">{block.requested_start ? new Date(block.requested_start).toLocaleString() : "—"}</div>
          <div className="gov-kv-label">Requested End</div>
          <div className="gov-kv-value">{block.requested_end ? new Date(block.requested_end).toLocaleString() : "—"}</div>
          <div className="gov-kv-label">Duration (mins)</div>
          <div className="gov-kv-value">{block.duration_mins ?? "—"}</div>
          <div className="gov-kv-label">Block Type</div>
          <div className="gov-kv-value">{block.block_type ?? "—"}</div>
        </div>
      </div>

      <div className="gov-card">
        <div className="gov-section-header">
          <h3 className="gov-section-title">Generate Candidate Windows</h3>
        </div>
        <form onSubmit={onGenerate}>
          <div className="gov-form-grid">
            <div>
              <label className="gov-label" htmlFor="cw-days">Window Days (1–14)</label>
              <input id="cw-days" className="gov-input" type="number" min={1} max={14} value={windowDays} onChange={(e) => setWindowDays(Number(e.target.value))} required />
            </div>
            <div>
              <label className="gov-label" htmlFor="cw-max">Max Candidates (1–10)</label>
              <input id="cw-max" className="gov-input" type="number" min={1} max={10} value={maxCand} onChange={(e) => setMaxCand(Number(e.target.value))} required />
            </div>
            <div>
              <label className="gov-label" htmlFor="cw-buf">Min Buffer (mins, ≥0)</label>
              <input id="cw-buf" className="gov-input" type="number" min={0} value={buffer} onChange={(e) => setBuffer(Number(e.target.value))} required />
            </div>
          </div>
          <div className="gov-form-actions">
            <button className="gov-btn" type="submit" disabled={genLoading}>
              {genLoading ? "Generating…" : "Generate Candidates"}
            </button>
          </div>
        </form>
        {genError ? <div className="gov-alert gov-alert-error" role="alert">{genError}</div> : null}
        {genMsg ? <div className="gov-alert gov-alert-success" role="status">{genMsg}</div> : null}
      </div>

      <div className="gov-card">
        <div className="gov-section-header">
          <h3 className="gov-section-title">Candidate Windows ({candidates.length})</h3>
        </div>
        {candidates.length === 0 ? (
          <div className="gov-empty">
            <p>No candidates yet. Generate candidate windows above.</p>
          </div>
        ) : (
          <div className="gov-table-wrap">
            <table className="gov-table">
              <thead>
                <tr>
                  <th>ID</th>
                  <th>Start</th>
                  <th>End</th>
                  <th>Duration</th>
                  <th>Delay</th>
                  <th>Risk</th>
                  <th>Planning</th>
                  <th>Detail</th>
                </tr>
              </thead>
              <tbody>
                {candidates.map((c) => (
                  <tr key={c.id}>
                    <td>{c.id}</td>
                    <td>{c.candidate_start ? new Date(c.candidate_start).toLocaleString() : "—"}</td>
                    <td>{c.candidate_end ? new Date(c.candidate_end).toLocaleString() : "—"}</td>
                    <td>{c.predicted_duration_mins ?? "—"}</td>
                    <td>{c.predicted_delay_mins ?? "—"}</td>
                    <td>{c.asset_risk_score ?? "—"}</td>
                    <td><span className={`gov-badge gov-badge-${planningBadgeKind(c.safety_status)}`}>{c.safety_status}</span></td>
                    <td>
                      <button
                        type="button"
                        className="gov-btn gov-btn-primary gov-btn-sm"
                        style={{ color: "#ffffff", backgroundColor: "var(--navy)", borderColor: "var(--navy-dark)" }}
                        onClick={() => void onSelectCandidate(c.id)}
                      >
                        View
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        {selected ? (
          <div style={{ marginTop: 16, borderTop: "1px solid var(--border-light)", paddingTop: 16 }}>
            <div className="gov-section-header">
              <h4 className="gov-section-title">Candidate #{selected.id}</h4>
            </div>
            <div className="gov-kv-grid">
              <div className="gov-kv-label">Window</div>
              <div className="gov-kv-value">{selected.candidate_start ? new Date(selected.candidate_start).toLocaleString() : "—"} → {selected.candidate_end ? new Date(selected.candidate_end).toLocaleString() : "—"}</div>
              <div className="gov-kv-label">Predicted Duration</div>
              <div className="gov-kv-value">{selected.predicted_duration_mins ?? "—"}</div>
              <div className="gov-kv-label">Predicted Delay</div>
              <div className="gov-kv-value">{selected.predicted_delay_mins ?? "—"}</div>
              <div className="gov-kv-label">Asset Risk</div>
              <div className="gov-kv-value">{selected.asset_risk_score ?? "—"}</div>
              <div className="gov-kv-label">Planning Status</div>
              <div className="gov-kv-value">{selected.safety_status}</div>
              <div className="gov-kv-label">Planning Reason</div>
              <div className="gov-kv-value">{selected.safety_rejection_reason ?? "—"}</div>
              <div className="gov-kv-label">Optimization Score</div>
              <div className="gov-kv-value">{selected.optimization_score ?? "Pending OR-Tools module"}</div>
              <div className="gov-kv-label">Selected</div>
              <div className="gov-kv-value">{selected.is_selected ? "Yes" : "No"}</div>
            </div>
            <div className="gov-info-box">
              Planning-level status only — Safety Engine validation and OR-Tools optimization still required before approval.
            </div>
          </div>
        ) : null}
      </div>
    </div>
  );
}
