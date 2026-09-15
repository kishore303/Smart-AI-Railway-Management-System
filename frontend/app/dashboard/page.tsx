"use client";

import React, { useEffect, useState } from "react";
import ProtectedRoute from "@/components/ProtectedRoute";
import AppShell from "@/components/AppShell";
import Breadcrumbs from "@/components/Breadcrumbs";
import { api, ApiError } from "@/lib/api-client";
import { useAuth } from "@/lib/auth-context";
import type { DashboardHealth, DashboardOverview } from "@/types/dashboard";

function StatCard({
  title,
  value,
  accent,
  children,
}: {
  title: string;
  value: string | number;
  accent?: "red" | "amber" | "green" | "blue" | "navy";
  children?: React.ReactNode;
}) {
  return (
    <div className={`stat-card${accent ? ` stat-card-accent-${accent}` : ""}`}>
      <h3>{title}</h3>
      <div className="stat-val">{value}</div>
      {children ? <div style={{ marginTop: 6 }}>{children}</div> : null}
    </div>
  );
}

export default function DashboardPage() {
  return (
    <ProtectedRoute>
      <AppShell>
        <DashboardContent />
      </AppShell>
    </ProtectedRoute>
  );
}

function DashboardContent() {
  const { user } = useAuth();
  const [data, setData] = useState<DashboardOverview | null>(null);
  const [health, setHealth] = useState<DashboardHealth | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      setLoading(true);
      setError(null);
      try {
        const [overview, h] = await Promise.all([
          api.get<DashboardOverview>("/api/dashboard/overview"),
          api.get<DashboardHealth>("/api/dashboard/health"),
        ]);
        if (!cancelled) {
          setData(overview);
          setHealth(h);
        }
      } catch (err) {
        if (!cancelled) setError(err instanceof ApiError ? err.message : "Unable to connect to the railway service.");
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    void load();
    return () => { cancelled = true; };
  }, []);

  const roleLabel = user?.role?.replace(/_/g, " ") ?? "";
  const deptLabel = user?.department ?? "";

  return (
    <div className="gov-page">
      <Breadcrumbs trail={[{ label: "Dashboard" }]} />

      <div className="gov-page-header">
        <div>
          <h1 className="gov-title">Operational Dashboard</h1>
          <p className="gov-sub">
            Live operational overview of maintenance demand, block planning, safety posture and system health.
          </p>
          <div className="gov-context-row" aria-label="Session context">
            <span className="gov-context-chip">{user ? roleLabel : "Loading…"}</span>
            <span className="gov-context-chip">{user ? deptLabel : "—"}</span>
          </div>
        </div>
      </div>

      {loading && (
        <div className="gov-card">
          <div className="gov-loading">Loading operational overview…</div>
        </div>
      )}

      {error && !loading && (
        <div className="gov-card">
          <div className="gov-alert gov-alert-error" role="alert">{error}</div>
          <button className="gov-btn gov-btn-secondary" type="button" onClick={() => window.location.reload()} style={{ marginTop: 12 }}>
            Retry
          </button>
        </div>
      )}

      {!loading && !error && data && (
        <>
          <section className="dash-band" aria-label="Primary operational indicators">
            <div className="dash-band-head">
              <span className="dash-band-index">01</span>
              <span className="dash-band-title">Operational Summary</span>
              <span className="dash-band-sub">Demand · Planning · Approval · Safety</span>
            </div>
            <div className="stat-grid">
              <StatCard title="Maintenance Requests" value={data.maintenance_requests.total} accent="navy">
                {data.maintenance_requests.pending_review > 0 && (
                  <span className="badge badge-amber">{data.maintenance_requests.pending_review} pending review</span>
                )}
              </StatCard>
              <StatCard title="Block Requests" value={data.block_planning.block_requests} accent="blue">
                <span className="gov-muted">{data.block_planning.candidates} candidates generated</span>
              </StatCard>
              <StatCard title="Approved Blocks" value={data.block_planning.approved} accent="green">
                <span className="badge badge-green">{data.block_planning.active} active</span>
              </StatCard>
              <StatCard title="Safety Validations" value={`${data.safety.safe}/${data.safety.total_validations}`} accent="green">
                <span className="badge badge-green">All checks passing</span>
              </StatCard>
            </div>
          </section>

          <section className="dash-band" aria-label="Current operational status">
            <div className="dash-band-head">
              <span className="dash-band-index">02</span>
              <span className="dash-band-title">Current Operational Status</span>
              <span className="dash-band-sub">Coordination · Resources · Correspondence · Records</span>
            </div>
            <div className="stat-grid">
              <StatCard title="Integration" value={data.integration.pending} accent="amber">
                <span className="gov-muted">{data.integration.total} total requests</span>
              </StatCard>
              <StatCard title="Resources" value={data.resources.allocated} accent="blue">
                <span className="gov-muted">{data.resources.total} total available</span>
              </StatCard>
              <StatCard title="Notifications" value={data.notifications.unread} accent={data.notifications.unread > 0 ? "amber" : "green"}>
                {data.notifications.unread > 0 ? (
                  <span className="badge badge-amber">Action needed</span>
                ) : (
                  <span className="badge badge-green">All clear</span>
                )}
              </StatCard>
              <StatCard title="Audit Trail" value={data.audit.total} accent="navy">
                <span className="gov-muted">{data.simulation.total} simulations run</span>
              </StatCard>
            </div>
          </section>

          <section className="dash-band" aria-label="System status and recent activity">
            <div className="dash-band-head">
              <span className="dash-band-index">03</span>
              <span className="dash-band-title">System Status &amp; Activity</span>
              <span className="dash-band-sub">Service health · Audit record</span>
            </div>
            <div className="dash-grid-2">
              <section className="gov-card" aria-label="System health">
                <div className="gov-section-header"><h3 className="gov-section-title">System Health</h3></div>
              {health ? (
                <table className="gov-table">
                  <thead>
                    <tr><th>Service</th><th>Status</th></tr>
                  </thead>
                  <tbody>
                    {Object.entries(health.checks).map(([k, v]) => (
                      <tr key={k}>
                        <td style={{ fontWeight: 500 }}>{k}</td>
                        <td>
                          {v === "ok" ? (
                            <span className="badge badge-green">Healthy</span>
                          ) : (
                            <span className="badge badge-red">Unavailable</span>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              ) : (
                <p className="gov-muted">Health data unavailable.</p>
              )}
            </section>

            <section className="gov-card" aria-label="Recent activity">
              <div className="gov-section-header"><h3 className="gov-section-title">Recent Activity</h3></div>
              {data.audit.recent.length === 0 ? (
                <p className="gov-muted">No recent activity recorded.</p>
              ) : (
                <table className="gov-table">
                  <thead>
                    <tr><th>Action</th><th>Type</th><th>Time</th></tr>
                  </thead>
                  <tbody>
                    {data.audit.recent.slice(0, 8).map((r, i) => (
                      <tr key={`${r.action}-${i}`}>
                        <td style={{ fontWeight: 500 }}>{r.action}</td>
                        <td>{r.entity_type ?? "—"}</td>
                        <td style={{ fontSize: 12, color: "var(--muted)" }}>{r.created_at}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
                )}
              </section>
            </div>
          </section>
        </>
      )}

      {!loading && !error && !data && (
        <div className="gov-card">
          <div className="gov-empty">
            <div className="gov-empty-icon">📊</div>
            <p>Dashboard data is currently unavailable.</p>
          </div>
        </div>
      )}
    </div>
  );
}
