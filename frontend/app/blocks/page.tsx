"use client";

import React, { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import ProtectedRoute from "@/components/ProtectedRoute";
import AppShell from "@/components/AppShell";
import Breadcrumbs from "@/components/Breadcrumbs";
import { api, ApiError } from "@/lib/api-client";
import type { BlockRequestListResponse } from "@/types/blocks";

const STATUSES = ["", "REQUESTED", "UNDER_REVIEW", "PROPOSED", "PENDING_APPROVAL", "APPROVED", "REJECTED", "ACTIVE", "COMPLETED", "CANCELLED"];

export default function BlockListPage() {
  return (
    <ProtectedRoute>
      <AppShell>
        <ListContent />
      </AppShell>
    </ProtectedRoute>
  );
}

function ListContent() {
  const [data, setData] = useState<BlockRequestListResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [status, setStatus] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const params = new URLSearchParams({ skip: "0", limit: "20" });
      if (status) params.set("status", status);
      const res = await api.get<BlockRequestListResponse>(`/api/blocks/requests?${params.toString()}`);
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

  function statusBadge(s: string) {
    if (s === "APPROVED" || s === "COMPLETED") return "gov-badge gov-badge-green";
    if (s === "REJECTED" || s === "CANCELLED") return "gov-badge gov-badge-red";
    return "gov-badge gov-badge-amber";
  }

  return (
    <div className="gov-page">
      <Breadcrumbs trail={[{ label: "Dashboard", href: "/dashboard" }, { label: "Block Planning" }]} />

      <div className="gov-page-header">
        <div>
          <h2 className="gov-title">Block Planning</h2>
          <p className="gov-sub">Block requests derived from verified maintenance. Planning feasibility is not safety approval.</p>
        </div>
        <Link className="gov-btn" href="/blocks/new">New Block Request</Link>
      </div>

      <div className="gov-card">
        <form
          onSubmit={(e) => {
            e.preventDefault();
            void load();
          }}
          className="gov-filter-bar"
        >
          <div>
            <label className="gov-label" htmlFor="b-status">Status</label>
            <select id="b-status" className="gov-select" value={status} onChange={(e) => setStatus(e.target.value)}>
              {STATUSES.map((s) => (
                <option key={s} value={s}>{s === "" ? "All statuses" : s}</option>
              ))}
            </select>
          </div>
          <button className="gov-btn gov-btn-secondary" type="submit">Apply Filter</button>
        </form>
      </div>

      {loading ? (
        <div className="gov-card"><div className="gov-loading">Loading block requests…</div></div>
      ) : null}
      {error && !loading ? (
        <div className="gov-card"><div className="gov-alert gov-alert-error" role="alert">{error}</div></div>
      ) : null}
      {!loading && !error && data && data.items.length === 0 ? (
        <div className="gov-card"><div className="gov-empty"><p>No block requests found.</p></div></div>
      ) : null}
      {!loading && !error && data && data.items.length > 0 ? (
        <div className="gov-card">
          <div className="gov-table-wrap">
            <table className="gov-table">
              <thead>
                <tr>
                  <th>Block Code</th>
                  <th>Maint. Req</th>
                  <th>Section</th>
                  <th>Track</th>
                  <th>Window</th>
                  <th>Status</th>
                  <th>Detail</th>
                </tr>
              </thead>
              <tbody>
                {data.items.map((b) => (
                  <tr key={b.id}>
                    <td>{b.block_code}</td>
                    <td>{b.maintenance_request_id}</td>
                    <td>{b.section_id}</td>
                    <td>{b.track_id ?? "—"}</td>
                    <td>{b.requested_start ? new Date(b.requested_start).toLocaleString() : "—"}</td>
                    <td><span className={statusBadge(b.status)}>{b.status}</span></td>
                    <td><Link className="gov-btn gov-btn-sm" href={`/blocks/${b.id}`}>View</Link></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="gov-muted" style={{ marginTop: 8 }}>Total: {data.total}</p>
        </div>
      ) : null}
    </div>
  );
}
