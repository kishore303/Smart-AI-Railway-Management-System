"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import ProtectedRoute from "@/components/ProtectedRoute";
import AppShell from "@/components/AppShell";
import Breadcrumbs from "@/components/Breadcrumbs";
import { api, ApiError } from "@/lib/api-client";
import { IncidentRecord, EmergencyKPIs } from "@/types/emergency";

export default function EmergencyDashboardPage() {
  const [kpis, setKpis] = useState<EmergencyKPIs | null>(null);
  const [incidents, setIncidents] = useState<IncidentRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function load() {
      try {
        const [kpiData, incData] = await Promise.all([
          api.get<EmergencyKPIs>("/api/emergency/kpis"),
          api.get<IncidentRecord[]>("/api/emergency/incidents"),
        ]);
        setKpis(kpiData);
        setIncidents(incData || []);
      } catch (err) {
        setError(err instanceof ApiError ? err.message : "Failed to load emergency command center data");
      } finally {
        setLoading(false);
      }
    }
    load();
  }, []);

  const severityBadge = (s: string) => {
    switch (s) {
      case "CRITICAL":
        return <span className="gov-badge gov-badge-danger" style={{ fontWeight: 700 }}>CRITICAL</span>;
      case "HIGH":
        return <span className="gov-badge gov-badge-warning" style={{ fontWeight: 600 }}>HIGH</span>;
      case "MEDIUM":
        return <span className="gov-badge gov-badge-info">MEDIUM</span>;
      default:
        return <span className="gov-badge">{s}</span>;
    }
  };

  const statusBadge = (st: string) => {
    switch (st) {
      case "REPORTED":
      case "ACKNOWLEDGED":
        return <span className="gov-badge gov-badge-danger">{st}</span>;
      case "EMERGENCY_PLANNING":
        return <span className="gov-badge gov-badge-warning">PLANNING</span>;
      case "AWAITING_OFFICIAL_DECISION":
        return <span className="gov-badge gov-badge-warning" style={{ background: "#f59e0b", color: "#000", fontWeight: 700 }}>AWAITING OFFICIAL</span>;
      case "APPROVED":
      case "RESPONSE_DISPATCHED":
      case "ON_SITE":
      case "WORK_IN_PROGRESS":
        return <span className="gov-badge gov-badge-info">{st.replace(/_/g, " ")}</span>;
      case "CLEARANCE_PENDING":
        return <span className="gov-badge gov-badge-warning">CLEARANCE PENDING</span>;
      case "CLEARED":
      case "RELEASED":
      case "INCIDENT_CLOSED":
        return <span className="gov-badge gov-badge-success">{st.replace(/_/g, " ")}</span>;
      default:
        return <span className="gov-badge">{st}</span>;
    }
  };

  return (
    <ProtectedRoute>
      <AppShell>
        <div className="gov-page">
          <Breadcrumbs trail={[{ label: "Dashboard", href: "/dashboard" }, { label: "Emergency Control Center" }]} />
          
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16 }}>
            <div>
              <h1 className="gov-title" style={{ display: "flex", alignItems: "center", gap: 10 }}>
                🚨 Emergency Control & Response Command Center
              </h1>
              <p className="gov-sub">
                Real-time incident intelligence, train delay prediction, OR-Tools CP-SAT re-planning & Railway Official decision workflow
              </p>
            </div>
            <div style={{ display: "flex", gap: 10 }}>
              <Link href="/emergency/incidents" className="gov-btn gov-btn-primary" style={{ background: "#dc2626", borderColor: "#dc2626" }}>
                + Report New Emergency
              </Link>
            </div>
          </div>

          {error && <div className="gov-alert gov-alert-error" role="alert">{error}</div>}

          {/* Top KPI Cards */}
          <div className="stat-grid" style={{ marginTop: 16, marginBottom: 24, gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))" }}>
            <div className="stat-card" style={{ borderLeft: "4px solid #dc2626" }}>
              <h3>ACTIVE INCIDENTS</h3>
              <div className="stat-val" style={{ color: "#dc2626" }}>{loading ? "—" : kpis?.active_incidents ?? 0}</div>
              <div className="stat-sub">Requires active intervention</div>
            </div>
            <div className="stat-card" style={{ borderLeft: "4px solid #f59e0b" }}>
              <h3>AWAITING OFFICIAL</h3>
              <div className="stat-val" style={{ color: "#d97706" }}>{loading ? "—" : kpis?.awaiting_official_decision ?? 0}</div>
              <div className="stat-sub">OR-Tools optimized, decision pending</div>
            </div>
            <div className="stat-card" style={{ borderLeft: "4px solid #3b82f6" }}>
              <h3>WORK IN PROGRESS</h3>
              <div className="stat-val" style={{ color: "#2563eb" }}>{loading ? "—" : kpis?.work_in_progress ?? 0}</div>
              <div className="stat-sub">Emergency gang on-site</div>
            </div>
            <div className="stat-card" style={{ borderLeft: "4px solid #10b981" }}>
              <h3>CLEARED & CLOSED</h3>
              <div className="stat-val" style={{ color: "#059669" }}>{loading ? "—" : (kpis?.cleared_or_released ?? 0) + (kpis?.closed ?? 0)}</div>
              <div className="stat-sub">Track cleared / closed</div>
            </div>
          </div>

          {/* Active Incidents Table */}
          <div className="gov-card" style={{ marginBottom: 24 }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 14 }}>
              <h2 style={{ fontSize: "1.1rem", fontWeight: 700, margin: 0 }}>
                Active Incident Queue ({incidents.filter(i => i.status !== "INCIDENT_CLOSED").length})
              </h2>
              <Link href="/emergency/incidents" className="gov-btn gov-btn-secondary" style={{ fontSize: "0.85rem", padding: "4px 10px" }}>
                View All Incidents →
              </Link>
            </div>

            {loading ? (
              <p style={{ color: "var(--text-secondary)" }}>Loading emergency incidents...</p>
            ) : incidents.length === 0 ? (
              <p style={{ color: "var(--text-secondary)" }}>No emergency incidents reported. Operations nominal.</p>
            ) : (
              <div className="gov-table-container">
                <table className="gov-table">
                  <thead>
                    <tr>
                      <th>Code</th>
                      <th>Type</th>
                      <th>Severity</th>
                      <th>Section & Track</th>
                      <th>Reported</th>
                      <th>Workflow Status</th>
                      <th style={{ textAlign: "right" }}>Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {incidents.slice(0, 10).map((inc) => (
                      <tr key={inc.id} style={{ background: inc.severity === "CRITICAL" ? "rgba(220, 38, 38, 0.05)" : undefined }}>
                        <td style={{ fontWeight: 700 }}>
                          <Link href={`/emergency/incidents/${inc.id}`} style={{ color: "var(--primary-color)" }}>
                            {inc.incident_code}
                          </Link>
                        </td>
                        <td>{inc.incident_type.replace(/_/g, " ")}</td>
                        <td>{severityBadge(inc.severity)}</td>
                        <td>
                          {inc.section_name || `Section #${inc.section_id}`}
                          {inc.track_number ? ` (Track ${inc.track_number})` : ""}
                        </td>
                        <td style={{ fontSize: "0.85rem", color: "var(--text-secondary)" }}>
                          {new Date(inc.reported_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                        </td>
                        <td>{statusBadge(inc.status)}</td>
                        <td style={{ textAlign: "right" }}>
                          <div style={{ display: "flex", gap: 6, justifyContent: "flex-end" }}>
                            {inc.status === "AWAITING_OFFICIAL_DECISION" && (
                              <Link
                                href={`/emergency/approval/${inc.id}`}
                                className="gov-btn gov-btn-primary"
                                style={{ fontSize: "0.75rem", padding: "3px 8px", background: "#f59e0b", borderColor: "#f59e0b", color: "#000", fontWeight: 700 }}
                              >
                                Official Decision
                              </Link>
                            )}
                            <Link
                              href={`/emergency/incidents/${inc.id}`}
                              className="gov-btn gov-btn-secondary"
                              style={{ fontSize: "0.75rem", padding: "3px 8px" }}
                            >
                              Manage & Track
                            </Link>
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>

          {/* Workflow Architecture Overview */}
          <div className="gov-card" style={{ background: "var(--surface-color)", border: "1px solid var(--border-color)" }}>
            <h3 style={{ fontSize: "1rem", fontWeight: 700, marginBottom: 8 }}>Emergency Decision-Support Protocol</h3>
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))", gap: 12, fontSize: "0.85rem" }}>
              <div style={{ padding: 10, background: "rgba(0,0,0,0.03)", borderRadius: 6 }}>
                <strong>1. Incident Assessment:</strong> Operator reports/acknowledges incident, records notes and links emergency maintenance block.
              </div>
              <div style={{ padding: 10, background: "rgba(0,0,0,0.03)", borderRadius: 6 }}>
                <strong>2. Train Delay Intelligence:</strong> Timetable query runs ML delay predictions on affected express/freight services.
              </div>
              <div style={{ padding: 10, background: "rgba(0,0,0,0.03)", borderRadius: 6 }}>
                <strong>3. Safety Engine Gate:</strong> All candidate restoration windows must pass deterministic railway safety rules.
              </div>
              <div style={{ padding: 10, background: "rgba(0,0,0,0.03)", borderRadius: 6 }}>
                <strong>4. Official Decision (Strict RBAC):</strong> Railway Authorized Official approves or modifies; no autonomous dispatch.
              </div>
            </div>
          </div>
        </div>
      </AppShell>
    </ProtectedRoute>
  );
}
