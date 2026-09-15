"use client";

import React, { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import ProtectedRoute from "@/components/ProtectedRoute";
import AppShell from "@/components/AppShell";
import Breadcrumbs from "@/components/Breadcrumbs";
import { api, ApiError } from "@/lib/api-client";
import type { DigitalTwinSnapshot } from "@/types/simulation";

export default function DigitalTwinPage() {
  return (
    <ProtectedRoute>
      <AppShell>
        <TwinContent />
      </AppShell>
    </ProtectedRoute>
  );
}

function TwinContent() {
  const [snap, setSnap] = useState<DigitalTwinSnapshot | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const r = await api.get<DigitalTwinSnapshot>("/api/simulation/digital-twin");
      setSnap(r);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Unable to connect to the railway service. Please try again.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  if (loading) {
    return (
      <div className="gov-page">
        <Breadcrumbs trail={[{ label: "Dashboard", href: "/dashboard" }, { label: "Digital Twin" }]} />
        <div className="gov-card"><div className="gov-loading">Loading current railway state…</div></div>
      </div>
    );
  }

  if (error || !snap) {
    return (
      <div className="gov-page">
        <Breadcrumbs trail={[{ label: "Dashboard", href: "/dashboard" }, { label: "Digital Twin" }]} />
        <div className="gov-card">
          <div className="gov-alert gov-alert-error" role="alert">{error ?? "Current state unavailable."}</div>
          <div className="gov-btn-group">
            <button className="gov-btn gov-btn-secondary" onClick={() => void load()}>
              Retry
            </button>
          </div>
        </div>
      </div>
    );
  }

  const counts: [string, number][] = [
    ["Sections", snap.sections],
    ["Tracks", snap.tracks],
    ["Stations", snap.stations],
    ["Assets", snap.assets],
    ["Maintenance Requests", snap.maintenance_requests],
    ["Block Requests", snap.block_requests],
    ["Block Candidates", snap.block_candidates],
    ["Optimized Blocks", snap.optimized_blocks],
    ["Resources", snap.resources],
    ["Trains", snap.trains],
    ["Incidents", snap.incidents],
  ];

  return (
    <div className="gov-page">
      <Breadcrumbs trail={[{ label: "Dashboard", href: "/dashboard" }, { label: "Digital Twin" }]} />

      <div className="gov-page-header">
        <div>
          <h2 className="gov-title">Digital Twin — Current / Baseline State</h2>
          <p className="gov-sub">
            Read-only visualization of real persisted backend state. Snapshot taken at{" "}
            {new Date(snap.snapshot_at).toLocaleString()}. To evaluate a hypothetical change, use{" "}
            <Link className="gov-link" href="/what-if">What-If Simulation</Link>.
          </p>
        </div>
        <button className="gov-btn gov-btn-secondary" onClick={() => void load()}>
          Refresh Snapshot
        </button>
      </div>

      <div className="gov-card">
        <div className="gov-section-header">
          <h3>State Summary (Persisted Counts)</h3>
        </div>
        <div className="gov-table-wrap">
          <table className="gov-table">
            <thead><tr><th>Entity</th><th>Count</th></tr></thead>
            <tbody>
              {counts.map(([label, v]) => (
                <tr key={label}>
                  <td>{label}</td>
                  <td><strong>{v}</strong></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <div className="gov-info-box" style={{ marginTop: 12 }}>{snap.note}</div>
      </div>

      <div className="gov-card">
        <div className="gov-section-header">
          <h3>Approved / Active Blocks Sample ({snap.active_blocks_sample.length})</h3>
        </div>
        {snap.active_blocks_sample.length === 0 ? (
          <div className="gov-info-box">No approved or active blocks at snapshot time.</div>
        ) : (
          <div className="gov-table-wrap">
            <table className="gov-table">
              <thead><tr><th>Block Code</th><th>Status</th><th>Start Time</th></tr></thead>
              <tbody>
                {snap.active_blocks_sample.map((b, i) => (
                  <tr key={`${b.block_code}-${i}`}>
                    <td>{b.block_code}</td>
                    <td>
                      <span className={`gov-badge gov-badge-${b.status === "ACTIVE" ? "green" : b.status === "COMPLETED" ? "blue" : "amber"}`}>
                        {b.status}
                      </span>
                    </td>
                    <td>{b.start_time}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
