"use client";

import React, { useState } from "react";
import Link from "next/link";
import ProtectedRoute from "@/components/ProtectedRoute";
import AppShell from "@/components/AppShell";
import Breadcrumbs from "@/components/Breadcrumbs";
import { api, ApiError } from "@/lib/api-client";
import type { AvailabilityResult, ExecutionDetail, ResourceListResponse } from "@/types/execution";

export default function ResourcesPage() {
  return (
    <ProtectedRoute>
      <AppShell>
        <ResContent />
      </AppShell>
    </ProtectedRoute>
  );
}

function ResContent() {
  const [obId, setObId] = useState("");
  const [resources, setResources] = useState<ResourceListResponse | null>(null);
  const [detail, setDetail] = useState<ExecutionDetail | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [availRes, setAvailRes] = useState("");
  const [availResult, setAvailResult] = useState<AvailabilityResult | null>(null);
  const [availBusy, setAvailBusy] = useState(false);
  const [availErr, setAvailErr] = useState<string | null>(null);

  async function onLoad(e: React.FormEvent) {
    e.preventDefault();
    if (loading || obId.trim() === "") return;
    setLoading(true);
    setError(null);
    setResources(null);
    setDetail(null);
    setAvailResult(null);
    try {
      const id = obId.trim();
      const d = await api.get<ExecutionDetail>(`/api/execution/${id}`);
      setDetail(d);
      const r = await api.get<ResourceListResponse>(`/api/execution/${id}/resources`);
      setResources(r);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Unable to connect to the railway service. Please try again.");
    } finally {
      setLoading(false);
    }
  }

  async function onAvailability(e: React.FormEvent) {
    e.preventDefault();
    if (availBusy || availRes.trim() === "" || !detail) return;
    setAvailBusy(true);
    setAvailErr(null);
    setAvailResult(null);
    try {
      const params = new URLSearchParams({
        resource_id: availRes.trim(),
        start_time: detail.start_time ?? "",
        end_time: detail.end_time ?? "",
      });
      const r = await api.get<AvailabilityResult>(
        `/api/execution/${obId.trim()}/resources/availability?${params.toString()}`
      );
      setAvailResult(r);
    } catch (err) {
      setAvailErr(err instanceof ApiError ? err.message : "Unable to connect to the railway service. Please try again.");
    } finally {
      setAvailBusy(false);
    }
  }

  return (
    <div className="gov-page">
      <Breadcrumbs trail={[{ label: "Dashboard", href: "/dashboard" }, { label: "Resources" }]} />

      <div className="gov-page-header">
        <div>
          <h2 className="gov-title">Resource Management</h2>
          <p className="gov-sub">
            Resources are scoped to an optimized block&apos;s departments. Availability is determined by
            the backend (resource flag plus overlapping allocations) — never assumed.
            Allocation and release are performed on the <Link className="gov-link" href="/execution">Execution</Link> page.
          </p>
        </div>
      </div>

      <div className="gov-card">
        <div className="gov-section-header">
          <h3>Load Resources for an Optimized Block</h3>
        </div>
        <form onSubmit={onLoad} style={{ display: "flex", gap: 12, alignItems: "end", flexWrap: "wrap" }}>
          <div style={{ flex: 1, minWidth: 200 }}>
            <label className="gov-label" htmlFor="res-ob">Optimized Block ID *</label>
            <input
              id="res-ob"
              className="gov-input"
              inputMode="numeric"
              value={obId}
              onChange={(e) => setObId(e.target.value)}
              placeholder="e.g. 5"
              required
            />
          </div>
          <button className="gov-btn" type="submit" disabled={loading}>
            {loading ? "Loading…" : "Load Resources"}
          </button>
        </form>
        {error ? <div className="gov-alert gov-alert-error" role="alert" style={{ marginTop: 12 }}>{error}</div> : null}
      </div>

      {detail ? (
        <div className="gov-card">
          <div className="gov-section-header">
            <h3>
              {detail.block_code}{" "}
              <span className={`gov-badge gov-badge-${detail.status === "ACTIVE" ? "green" : detail.status === "COMPLETED" ? "blue" : "amber"}`}>
                {detail.status}
              </span>
            </h3>
            <Link className="gov-btn gov-btn-sm gov-btn-secondary" href={`/execution/${detail.optimized_block_id}`}>
              Manage in Execution
            </Link>
          </div>
          {resources && resources.items.length === 0 ? (
            <div className="gov-info-box">No resources visible for your departments on this block.</div>
          ) : null}
          {resources && resources.items.length > 0 ? (
            <div className="gov-table-wrap">
              <table className="gov-table">
                <thead><tr><th>ID</th><th>Code</th><th>Name</th><th>Type</th><th>Dept</th><th>Qty</th><th>Available</th></tr></thead>
                <tbody>
                  {resources.items.map((r) => (
                    <tr key={r.id}>
                      <td>{r.id}</td>
                      <td>{r.resource_code}</td>
                      <td>{r.name ?? "—"}</td>
                      <td>{r.resource_type ?? "—"}</td>
                      <td>{r.department_code ?? "—"}</td>
                      <td>{r.quantity}</td>
                      <td><span className={`gov-badge gov-badge-${r.is_available ? "green" : "red"}`}>{r.is_available ? "Yes" : "No"}</span></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : null}
          {resources && resources.items.length > 0 ? (
            <p className="gov-muted" style={{ marginTop: 8 }}>Total: {resources.total}</p>
          ) : null}

          <div className="gov-section-header" style={{ marginTop: 16 }}>
            <h4>Check Availability (Backend)</h4>
          </div>
          <form onSubmit={onAvailability} style={{ display: "flex", gap: 12, alignItems: "end", flexWrap: "wrap" }}>
            <div style={{ flex: 1, minWidth: 160 }}>
              <label className="gov-label" htmlFor="res-avail">Resource ID *</label>
              <input id="res-avail" className="gov-input" inputMode="numeric" value={availRes} onChange={(e) => setAvailRes(e.target.value)} required />
            </div>
            <button className="gov-btn gov-btn-secondary" type="submit" disabled={availBusy}>
              {availBusy ? "Checking…" : "Check Availability"}
            </button>
          </form>
          {availErr ? <div className="gov-alert gov-alert-error" role="alert" style={{ marginTop: 8 }}>{availErr}</div> : null}
          {availResult ? (
            <div className={`gov-alert gov-alert-${availResult.is_available ? "success" : "error"}`} role="status" style={{ marginTop: 8 }}>
              {availResult.resource_code}: {availResult.is_available ? "Available" : "Unavailable"} — {availResult.reason}
            </div>
          ) : null}

          {detail.allocated_resources.length > 0 ? (
            <div style={{ marginTop: 16 }}>
              <div className="gov-section-header">
                <h4>Current Allocations ({detail.allocated_resources.length})</h4>
              </div>
              <div className="gov-table-wrap">
                <table className="gov-table">
                  <thead><tr><th>ID</th><th>Resource</th><th>Qty</th><th>Status</th></tr></thead>
                  <tbody>
                    {detail.allocated_resources.map((a) => (
                      <tr key={a.id}>
                        <td>{a.id}</td>
                        <td>{a.resource_code ?? a.resource_id}</td>
                        <td>{a.quantity_required}</td>
                        <td><span className={`gov-badge gov-badge-${a.status === "ALLOCATED" ? "green" : a.status === "RELEASED" ? "blue" : "amber"}`}>{a.status}</span></td>
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
  );
}
