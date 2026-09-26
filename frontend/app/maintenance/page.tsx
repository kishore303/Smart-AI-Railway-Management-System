"use client";

import React, { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import ProtectedRoute from "@/components/ProtectedRoute";
import AppShell from "@/components/AppShell";
import Breadcrumbs from "@/components/Breadcrumbs";
import { api, ApiError } from "@/lib/api-client";
import type { MaintenanceListResponse } from "@/types/maintenance";
import { statusBadgeKind } from "@/types/maintenance";

const STATUSES = ["", "DRAFT", "SUBMITTED", "UNDER_REVIEW", "VERIFIED", "REVISION_REQUIRED", "REJECTED", "BLOCK_PLANNING", "AI_RECOMMENDATION", "OFFICIAL_REVIEW", "APPROVED", "MODIFIED"];
const PRIORITIES = ["", "LOW", "MEDIUM", "HIGH", "CRITICAL"];

export default function MaintenanceListPage() {
  return (
    <ProtectedRoute>
      <AppShell>
        <ListContent />
      </AppShell>
    </ProtectedRoute>
  );
}

function ListContent() {
  const [data, setData] = useState<MaintenanceListResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [status, setStatus] = useState("");
  const [priority, setPriority] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const params = new URLSearchParams({ skip: "0", limit: "20" });
      if (status) params.set("status", status);
      if (priority) params.set("priority", priority);
      const res = await api.get<MaintenanceListResponse>(`/api/maintenance/requests?${params.toString()}`);
      setData(res);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Unable to connect to the railway service. Please try again.");
    } finally {
      setLoading(false);
    }
  }, [status, priority]);

  useEffect(() => {
    void load();
  }, [load]);

  return (
    <div className="gov-page">
      <Breadcrumbs trail={[{ label: "Dashboard", href: "/dashboard" }, { label: "Maintenance Requests" }]} />

      <div className="gov-page-header">
        <div>
          <h2 className="gov-title">Maintenance Requests</h2>
          <p className="gov-sub">Department-scoped maintenance requests. Backend authorization remains authoritative.</p>
        </div>
        <Link className="gov-btn" href="/maintenance/new">
          New Request
        </Link>
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
            <label className="gov-label" htmlFor="f-status">Status</label>
            <select id="f-status" className="gov-select" value={status} onChange={(e) => setStatus(e.target.value)}>
              {STATUSES.map((s) => (
                <option key={s} value={s}>{s === "" ? "All statuses" : s}</option>
              ))}
            </select>
          </div>
          <div>
            <label className="gov-label" htmlFor="f-priority">Priority</label>
            <select id="f-priority" className="gov-select" value={priority} onChange={(e) => setPriority(e.target.value)}>
              {PRIORITIES.map((p) => (
                <option key={p} value={p}>{p === "" ? "All priorities" : p}</option>
              ))}
            </select>
          </div>
          <div style={{ alignSelf: "flex-end" }}>
            <button className="gov-btn gov-btn-secondary" type="submit">
              Apply Filters
            </button>
          </div>
        </form>
      </div>

      {loading ? (
        <div className="gov-card">
          <div className="gov-loading">Loading maintenance requests…</div>
        </div>
      ) : null}

      {error && !loading ? (
        <div className="gov-alert gov-alert-error" role="alert">{error}</div>
      ) : null}

      {!loading && !error && data && (data.items ?? []).length === 0 ? (
        <div className="gov-card">
          <div className="gov-empty">
            <p className="gov-muted">No maintenance requests found.</p>
          </div>
        </div>
      ) : null}

      {!loading && !error && data && (data.items ?? []).length > 0 ? (
        <div className="gov-card">
          <div className="gov-table-wrap">
            <table className="gov-table">
              <thead>
                <tr>
                  <th>Request Code</th>
                  <th>Type</th>
                  <th>Dept</th>
                  <th>Priority</th>
                  <th>Status</th>
                  <th>Start</th>
                  <th>Detail</th>
                </tr>
              </thead>
              <tbody>
                {(data.items ?? []).map((r) => (
                  <tr key={r.id}>
                    <td>{r.request_code}</td>
                    <td>{r.maintenance_type}</td>
                    <td>{r.department_code}</td>
                    <td>{r.priority}</td>
                    <td>
                      <span className={`gov-badge gov-badge-${statusBadgeKind(r.status)}`}>
                        {r.status}
                      </span>
                    </td>
                    <td>{r.requested_start ? new Date(r.requested_start).toLocaleString() : "—"}</td>
                    <td>
                      <Link className="gov-btn gov-btn-sm gov-btn-secondary" href={`/maintenance/${r.id}`}>
                        View
                      </Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="gov-muted" style={{ marginTop: 8 }}>Total: {data.total ?? 0}</p>
        </div>
      ) : null}
    </div>
  );
}
