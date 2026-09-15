"use client";

import React, { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import ProtectedRoute from "@/components/ProtectedRoute";
import AppShell from "@/components/AppShell";
import Breadcrumbs from "@/components/Breadcrumbs";
import { api, ApiError } from "@/lib/api-client";
import type { IntegrationListResponse, IntegrationRequest } from "@/types/integration";
import { compatibilityNote, integrationBadgeKind } from "@/types/integration";

const STATUSES = ["", "PENDING", "ACCEPTED", "REJECTED", "MODIFIED"];

export default function IntegrationListPage() {
  return (
    <ProtectedRoute>
      <AppShell>
        <ListContent />
      </AppShell>
    </ProtectedRoute>
  );
}

function ListContent() {
  const [data, setData] = useState<IntegrationListResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [status, setStatus] = useState("");

  const [srcBlock, setSrcBlock] = useState("");
  const [tgtBlock, setTgtBlock] = useState("");
  const [reason, setReason] = useState("");
  const [creating, setCreating] = useState(false);
  const [createError, setCreateError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const params = new URLSearchParams({ skip: "0", limit: "20" });
      if (status) params.set("status", status);
      const res = await api.get<IntegrationListResponse>(`/api/integration/requests?${params.toString()}`);
      setData(res);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Unable to connect to the railway service. Please try again.");
    } finally {
      setLoading(false);
    }
  }, [status]);

  useEffect(() => {
    void load();
  }, [load]);

  async function onCreate(e: React.FormEvent) {
    e.preventDefault();
    if (creating) return;
    setCreateError(null);
    if (!srcBlock || !tgtBlock) {
      setCreateError("Source and target block IDs are required.");
      return;
    }
    if (srcBlock === tgtBlock) {
      setCreateError("Source and target blocks must differ.");
      return;
    }
    setCreating(true);
    try {
      const payload: Record<string, unknown> = {
        source_block_id: Number(srcBlock),
        target_block_id: Number(tgtBlock),
      };
      if (reason.trim() !== "") payload.reason = reason.trim().slice(0, 1000);
      await api.post<IntegrationRequest>("/api/integration/requests", payload);
      setSrcBlock("");
      setTgtBlock("");
      setReason("");
      await load();
    } catch (err) {
      setCreateError(err instanceof ApiError ? err.message : "Unable to connect to the railway service. Please try again.");
    } finally {
      setCreating(false);
    }
  }

  return (
    <div className="gov-page">
      <Breadcrumbs trail={[{ label: "Dashboard", href: "/dashboard" }, { label: "Department Integration" }]} />

      <div className="gov-page-header">
        <div>
          <h2 className="gov-title">Cross-Department Integration</h2>
          <p className="gov-sub">
            Pairwise cross-department block integration. Acceptance is a planning-level agreement only —
            it is not safety approval and does not approve any block.
          </p>
        </div>
      </div>

      <div className="gov-card">
        <div className="gov-section-header">
          <h3>Request Integration</h3>
        </div>
        <div className="gov-info-box">
          Blocks must belong to different departments. You must belong to the source block&apos;s
          department (unless Authorized Official).
        </div>
        <form onSubmit={onCreate} style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit,minmax(200px,1fr))", gap: 12 }}>
          <div>
            <label className="gov-label" htmlFor="int-src">Source Block ID *</label>
            <input id="int-src" className="gov-input" inputMode="numeric" value={srcBlock} onChange={(e) => setSrcBlock(e.target.value)} required />
          </div>
          <div>
            <label className="gov-label" htmlFor="int-tgt">Target Block ID *</label>
            <input id="int-tgt" className="gov-input" inputMode="numeric" value={tgtBlock} onChange={(e) => setTgtBlock(e.target.value)} required />
          </div>
          <div>
            <label className="gov-label" htmlFor="int-reason">Reason (optional)</label>
            <input id="int-reason" className="gov-input" value={reason} onChange={(e) => setReason(e.target.value)} maxLength={1000} />
          </div>
          <div className="gov-btn-group" style={{ gridColumn: "1 / -1" }}>
            <button className="gov-btn" type="submit" disabled={creating}>
              {creating ? "Submitting…" : "Submit Integration Request"}
            </button>
          </div>
        </form>
        {createError ? <div className="gov-alert gov-alert-error" role="alert" style={{ marginTop: 12 }}>{createError}</div> : null}
      </div>

      <div className="gov-card">
        <div className="gov-section-header">
          <h3>Integration Queue</h3>
        </div>
        <form
          onSubmit={(e) => {
            e.preventDefault();
            void load();
          }}
          style={{ display: "flex", gap: 12, alignItems: "end", flexWrap: "wrap", marginBottom: 12 }}
        >
          <div>
            <label className="gov-label" htmlFor="int-status">Final Status</label>
            <select id="int-status" className="gov-input" value={status} onChange={(e) => setStatus(e.target.value)}>
              {STATUSES.map((s) => (
                <option key={s} value={s}>{s === "" ? "All statuses" : s}</option>
              ))}
            </select>
          </div>
          <button className="gov-btn gov-btn-secondary" type="submit">
            Apply Filter
          </button>
        </form>
        {loading ? <div className="gov-loading">Loading integration requests…</div> : null}
        {error && !loading ? <div className="gov-alert gov-alert-error" role="alert">{error}</div> : null}
        {!loading && !error && data && data.items.length === 0 ? (
          <div className="gov-empty">
            <div className="gov-empty-icon">📋</div>
            <p>No integration requests found.</p>
          </div>
        ) : null}
        {!loading && !error && data && data.items.length > 0 ? (
          <div className="gov-table-wrap">
            <table className="gov-table">
              <thead>
                <tr><th>ID</th><th>Blocks</th><th>Departments</th><th>Compatibility</th><th>Status</th><th>Detail</th></tr>
              </thead>
              <tbody>
                {data.items.map((r) => (
                  <tr key={r.id}>
                    <td>{r.id}</td>
                    <td>{r.source_block_id} → {r.target_block_id}</td>
                    <td>{r.requesting_department_code} → {r.target_department_code}</td>
                    <td title={compatibilityNote(r.compatibility_status)}>
                      {r.compatibility_status ? (
                        <span className={`gov-badge gov-badge-${r.compatibility_status === "COMPATIBLE" ? "green" : r.compatibility_status === "INCOMPATIBLE" ? "red" : "amber"}`}>
                          {r.compatibility_status}
                        </span>
                      ) : "—"}
                    </td>
                    <td><span className={`gov-badge gov-badge-${integrationBadgeKind(r.final_status)}`}>{r.final_status}</span></td>
                    <td><Link className="gov-link" href={`/integration/${r.id}`}>View</Link></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : null}
        {!loading && !error && data && data.items.length > 0 ? (
          <p className="gov-muted" style={{ marginTop: 8 }}>Total: {data.total}</p>
        ) : null}
      </div>
    </div>
  );
}
