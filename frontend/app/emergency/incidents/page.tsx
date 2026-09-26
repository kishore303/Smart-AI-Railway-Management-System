"use client";

import React, { useEffect, useState, useCallback } from "react";
import Link from "next/link";
import ProtectedRoute from "@/components/ProtectedRoute";
import AppShell from "@/components/AppShell";
import Breadcrumbs from "@/components/Breadcrumbs";
import { api, ApiError } from "@/lib/api-client";

const INCIDENT_TYPES = [
  "ACCIDENT", "DERAILMENT_RELATED", "TRACK_FAILURE", "SIGNAL_FAILURE",
  "OHE_FAILURE", "OBSTRUCTION", "PERSON_ON_TRACK", "SUSPECTED_SUICIDE",
  "OTHER_EMERGENCY",
];
const SEVERITIES = ["LOW", "MEDIUM", "HIGH", "CRITICAL"];

interface IncidentSummary {
  id: number;
  incident_code: string;
  incident_type: string;
  severity: string;
  response_status: string;
  latitude: number | null;
  longitude: number | null;
  reported_at: string | null;
}

export default function IncidentsListPage() {
  const [incidents, setIncidents] = useState<IncidentSummary[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showForm, setShowForm] = useState(false);
  const [creating, setCreating] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);
  const [formSuccess, setFormSuccess] = useState<string | null>(null);

  const [formType, setFormType] = useState("OTHER_EMERGENCY");
  const [formSeverity, setFormSeverity] = useState("HIGH");
  const [formDesc, setFormDesc] = useState("");
  const [formLat, setFormLat] = useState("");
  const [formLng, setFormLng] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await api.get<IncidentSummary[] | { total: number; items: IncidentSummary[] }>("/api/emergency/incidents?limit=50");
      const items = Array.isArray(res) ? res : res.items;
      setIncidents(items);
      setTotal(Array.isArray(res) ? items.length : res.total);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to load incidents");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  async function onCreate(e: React.FormEvent) {
    e.preventDefault();
    if (creating) return;
    setCreating(true);
    setFormError(null);
    setFormSuccess(null);
    try {
      const body: Record<string, unknown> = {
        incident_type: formType,
        severity: formSeverity,
        description: formDesc || undefined,
      };
      if (formLat && formLng) {
        body.latitude = parseFloat(formLat);
        body.longitude = parseFloat(formLng);
      }
      const res = await api.post<{ incident_code: string }>("/api/emergency/incidents", body);
      setFormSuccess(`Incident ${res.incident_code} created successfully.`);
      setShowForm(false);
      setFormDesc("");
      setFormLat("");
      setFormLng("");
      await load();
    } catch (err) {
      setFormError(err instanceof ApiError ? err.message : "Failed to create incident");
    } finally {
      setCreating(false);
    }
  }

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
          <Breadcrumbs trail={[{ label: "Dashboard", href: "/dashboard" }, { label: "Emergency", href: "/emergency" }, { label: "Incidents" }]} />
          <div className="gov-page-header">
            <div>
              <h1 className="gov-title">Incidents</h1>
              <p className="gov-sub">Railway incident tracking and response management</p>
            </div>
            <button className="gov-btn" onClick={() => setShowForm(!showForm)}>
              {showForm ? "Cancel" : "+ Report Incident"}
            </button>
          </div>

          {error && <div className="gov-alert gov-alert-error" role="alert">{error}</div>}
          {formSuccess && <div className="gov-alert gov-alert-success" role="status">{formSuccess}</div>}

          {showForm && (
            <div className="gov-card" style={{ marginTop: 16 }}>
              <h2>Report New Incident</h2>
              {formError && <div className="gov-alert gov-alert-error" role="alert">{formError}</div>}
              <form onSubmit={onCreate}>
                <div className="gov-form-grid">
                  <div>
                    <label className="gov-label" htmlFor="inc-type">Incident Type *</label>
                    <select id="inc-type" className="gov-select" value={formType} onChange={(e) => setFormType(e.target.value)} required>
                      {INCIDENT_TYPES.map((t) => <option key={t} value={t}>{t.replace(/_/g, " ")}</option>)}
                    </select>
                  </div>
                  <div>
                    <label className="gov-label" htmlFor="inc-sev">Severity *</label>
                    <select id="inc-sev" className="gov-select" value={formSeverity} onChange={(e) => setFormSeverity(e.target.value)} required>
                      {SEVERITIES.map((s) => <option key={s} value={s}>{s}</option>)}
                    </select>
                  </div>
                </div>
                <label className="gov-label" htmlFor="inc-desc">Description</label>
                <textarea id="inc-desc" className="gov-textarea" value={formDesc} onChange={(e) => setFormDesc(e.target.value)} rows={3} placeholder="Describe the incident…" />
                <div className="gov-form-grid">
                  <div>
                    <label className="gov-label" htmlFor="inc-lat">Latitude</label>
                    <input id="inc-lat" className="gov-input" type="number" step="0.000001" value={formLat} onChange={(e) => setFormLat(e.target.value)} placeholder="28.6139" />
                  </div>
                  <div>
                    <label className="gov-label" htmlFor="inc-lng">Longitude</label>
                    <input id="inc-lng" className="gov-input" type="number" step="0.000001" value={formLng} onChange={(e) => setFormLng(e.target.value)} placeholder="77.2090" />
                  </div>
                </div>
                <div className="gov-form-actions">
                  <button className="gov-btn" type="submit" disabled={creating}>{creating ? "Creating…" : "Submit Report"}</button>
                  <button className="gov-btn gov-btn-outline" type="button" onClick={() => setShowForm(false)}>Cancel</button>
                </div>
              </form>
            </div>
          )}

          <div className="gov-card" style={{ marginTop: 16 }}>
            <div className="gov-card-header">
              <h2>All Incidents ({total})</h2>
            </div>
            {loading ? (
              <div className="gov-loading">Loading…</div>
            ) : incidents.length === 0 ? (
              <div className="gov-empty">
                <div className="gov-empty-icon">✓</div>
                <p>No incidents recorded</p>
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
                      <th>Location</th>
                      <th>Reported</th>
                    </tr>
                  </thead>
                  <tbody>
                    {incidents.map((inc) => (
                      <tr key={inc.id}>
                        <td><Link className="gov-link" href={`/emergency/incidents/${inc.id}`}>{inc.incident_code}</Link></td>
                        <td>{inc.incident_type.replace(/_/g, " ")}</td>
                        <td><span className="gov-badge" style={{ background: severityColor(inc.severity), color: "#fff" }}>{inc.severity}</span></td>
                        <td><span className="gov-badge" style={{ background: statusColor(inc.response_status), color: "#fff" }}>{inc.response_status}</span></td>
                        <td>{inc.latitude && inc.longitude ? `${inc.latitude}, ${inc.longitude}` : "—"}</td>
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
