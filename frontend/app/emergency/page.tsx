"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import ProtectedRoute from "@/components/ProtectedRoute";
import AppShell from "@/components/AppShell";
import Breadcrumbs from "@/components/Breadcrumbs";
import { api, ApiError } from "@/lib/api-client";

interface EmergencyStats {
  total_incidents: number;
  active_incidents: number;
  critical_incidents: number;
  sections_affected: number;
}

interface IncidentSummary {
  id: number;
  incident_code: string;
  incident_type: string;
  severity: string;
  response_status: string;
  latitude: number | null;
  longitude: number | null;
  reported_at: string | null;
  railway_alert_status: string | null;
  police_alert_status: string | null;
}

export default function EmergencyDashboardPage() {
  const [stats, setStats] = useState<EmergencyStats | null>(null);
  const [recent, setRecent] = useState<IncidentSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function load() {
      try {
        const [s, inc] = await Promise.all([
          api.get<EmergencyStats>("/api/emergency/stats"),
          api.get<{ total: number; items: IncidentSummary[] }>("/api/emergency/incidents?limit=5"),
        ]);
        setStats(s);
        setRecent(inc.items || []);
      } catch (err) {
        setError(err instanceof ApiError ? err.message : "Failed to load emergency data");
      } finally {
        setLoading(false);
      }
    }
    load();
  }, []);

  const severityColor = (s: string) => {
    switch (s) {
      case "CRITICAL": return "var(--red)";
      case "HIGH": return "var(--amber)";
      case "MEDIUM": return "var(--blue)";
      default: return "var(--text-secondary)";
    }
  };

  const statusColor = (s: string) => {
    if (s === "CLEARED") return "var(--green)";
    if (s === "OPEN" || s === "IN_PROGRESS") return "var(--amber)";
    return "var(--blue)";
  };

  return (
    <ProtectedRoute>
      <AppShell>
        <div className="gov-page">
          <Breadcrumbs trail={[{ label: "Dashboard", href: "/dashboard" }, { label: "Emergency" }]} />
          <h1 className="gov-title">Emergency Dashboard</h1>
          <p className="gov-sub">Emergency incident monitoring and response coordination</p>

          {error && <div className="gov-alert gov-alert-error" role="alert">{error}</div>}

          <div className="stat-grid" style={{ marginTop: 20 }}>
            <div className="stat-card">
              <h3>TOTAL INCIDENTS</h3>
              <div className="stat-val">{loading ? "—" : stats?.total_incidents ?? 0}</div>
              <div className="stat-sub">All incidents in system</div>
            </div>
            <div className="stat-card">
              <h3>ACTIVE INCIDENTS</h3>
              <div className="stat-val" style={{ color: "var(--amber)" }}>{loading ? "—" : stats?.active_incidents ?? 0}</div>
              <div className="stat-sub">Open / unresolved</div>
            </div>
            <div className="stat-card">
              <h3>CRITICAL</h3>
              <div className="stat-val" style={{ color: "var(--red)" }}>{loading ? "—" : stats?.critical_incidents ?? 0}</div>
              <div className="stat-sub">Critical severity active</div>
            </div>
            <div className="stat-card">
              <h3>SECTIONS AFFECTED</h3>
              <div className="stat-val">{loading ? "—" : stats?.sections_affected ?? 0}</div>
              <div className="stat-sub">Under emergency restriction</div>
            </div>
          </div>

          <div className="gov-card" style={{ marginTop: 20 }}>
            <h2>Recent Incidents</h2>
            {loading ? (
              <div className="gov-loading">Loading…</div>
            ) : recent.length === 0 ? (
              <div className="gov-empty">
                <div className="gov-empty-icon">✓</div>
                <p>No active incidents</p>
              </div>
            ) : (
              <div className="gov-table-wrap">
                <table className="gov-table">
                  <thead>
                    <tr>
                      <th>Code</th>
                      <th>Type</th>
                      <th>Severity</th>
                      <th>Status</th>
                      <th>Reported</th>
                    </tr>
                  </thead>
                  <tbody>
                    {recent.map((inc) => (
                      <tr key={inc.id}>
                        <td><Link className="gov-link" href={`/emergency/incidents/${inc.id}`}>{inc.incident_code}</Link></td>
                        <td>{inc.incident_type}</td>
                        <td><span className="gov-badge" style={{ background: severityColor(inc.severity), color: "#fff" }}>{inc.severity}</span></td>
                        <td><span className="gov-badge" style={{ background: statusColor(inc.response_status), color: "#fff" }}>{inc.response_status}</span></td>
                        <td>{inc.reported_at ? new Date(inc.reported_at).toLocaleString() : "—"}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </div>
      </AppShell>
    </ProtectedRoute>
  );
}
