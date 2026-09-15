"use client";

import React, { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import ProtectedRoute from "@/components/ProtectedRoute";
import AppShell from "@/components/AppShell";
import Breadcrumbs from "@/components/Breadcrumbs";
import { api, ApiError } from "@/lib/api-client";

// Exact value sets from backend/app/api/emergency.py (DB enums authoritative).
const RESPONSE_STATUSES = ["OPEN", "IN_PROGRESS", "CLEARED"];
const SEVERITIES = ["LOW", "MEDIUM", "HIGH", "CRITICAL"];
const AUTHORITY_TYPES = [
  "RAILWAY_PROTECTION_FORCE",
  "GOVERNMENT_RAILWAY_POLICE",
  "LOCAL_POLICE",
  "FIRE_BRIGADE",
  "NDRF",
  "MEDICAL",
  "DISTRICT_ADMINISTRATION",
  "OTHER",
];
const RESPONSE_LIFECYCLE = [
  "ALERT_RECEIVED",
  "TEAM_DISPATCHED",
  "TEAM_ARRIVED",
  "INCIDENT_HANDED_OVER",
  "AREA_CLEARED",
];

interface EmergencyResponse {
  id: number;
  authority_type: string | null;
  authority_name: string | null;
  notification_time: string | null;
  acknowledgement_time: string | null;
  arrival_time: string | null;
  clearance_time: string | null;
  status: string;
  notes: string | null;
  created_at: string | null;
}

interface IncidentDetail {
  id: number;
  incident_code: string;
  incident_type: string;
  severity: string;
  description: string | null;
  section_id: number | null;
  track_id: number | null;
  latitude: number | null;
  longitude: number | null;
  reported_at: string | null;
  reported_by: number | null;
  railway_alert_status: string | null;
  police_alert_status: string | null;
  response_status: string;
  clearance_time: string | null;
  responses: EmergencyResponse[];
}

function fmt(dt: string | null): string {
  if (!dt) return "—";
  try {
    return new Date(dt).toLocaleString();
  } catch {
    return dt;
  }
}

export default function IncidentDetailPage() {
  return (
    <ProtectedRoute>
      <AppShell>
        <DetailContent />
      </AppShell>
    </ProtectedRoute>
  );
}

function severityColor(s: string): string {
  switch (s) {
    case "CRITICAL": return "var(--red)";
    case "HIGH": return "var(--amber)";
    case "MEDIUM": return "var(--blue)";
    default: return "var(--text-secondary)";
  }
}

function statusColor(s: string): string {
  if (s === "CLEARED" || s === "AREA_CLEARED") return "var(--green)";
  if (s === "OPEN" || s === "IN_PROGRESS" || s === "ALERT_RECEIVED") return "var(--amber)";
  return "var(--blue)";
}

function DetailContent() {
  const params = useParams<{ id: string }>();
  const id = params.id;
  const [data, setData] = useState<IncidentDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const dataRef = React.useRef<IncidentDetail | null>(null);

  const load = useCallback(async (silent = false) => {
    // Silent reloads (after a successful mutation) must NOT flip the page
    // back to the loading skeleton: that would unmount the cards and wipe
    // their success feedback. Only show the skeleton on first load.
    if (!silent || !dataRef.current) {
      setLoading(true);
    }
    setError(null);
    try {
      const res = await api.get<IncidentDetail>(`/api/emergency/incidents/${id}`);
      dataRef.current = res;
      setData(res);
    } catch (err) {
      // On silent reload failure keep showing the (freshly mutated) data
      // instead of replacing the page with an error.
      if (!dataRef.current) {
        setError(err instanceof ApiError ? err.message : "Failed to load incident");
      }
    } finally {
      setLoading(false);
    }
  }, [id]);

  useEffect(() => {
    void load();
  }, [load]);

  // Quiet refresh passed to mutation cards: preserves their feedback.
  const refreshQuiet = useCallback(() => load(true), [load]);

  if (loading) {
    return (
      <div className="gov-page">
        <Breadcrumbs trail={[{ label: "Dashboard", href: "/dashboard" }, { label: "Emergency", href: "/emergency" }, { label: "Incidents", href: "/emergency/incidents" }, { label: `Incident ${id}` }]} />
        <div className="gov-card"><div className="gov-loading">Loading incident…</div></div>
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="gov-page">
        <Breadcrumbs trail={[{ label: "Dashboard", href: "/dashboard" }, { label: "Emergency", href: "/emergency" }, { label: "Incidents", href: "/emergency/incidents" }, { label: `Incident ${id}` }]} />
        <div className="gov-card">
          <div className="gov-alert gov-alert-error" role="alert">{error ?? "Incident not found."}</div>
          <p style={{ marginTop: 12 }}><Link className="gov-link" href="/emergency/incidents">Back to Incidents</Link></p>
        </div>
      </div>
    );
  }

  return (
    <div className="gov-page">
      <Breadcrumbs trail={[{ label: "Dashboard", href: "/dashboard" }, { label: "Emergency", href: "/emergency" }, { label: "Incidents", href: "/emergency/incidents" }, { label: data.incident_code }]} />
      <div className="gov-page-header">
        <div>
          <h1 className="gov-title">
            {data.incident_code}{" "}
            <span className="gov-badge" style={{ background: statusColor(data.response_status), color: "#fff" }}>{data.response_status}</span>{" "}
            <span className="gov-badge" style={{ background: severityColor(data.severity), color: "#fff" }}>{data.severity}</span>
          </h1>
          <p className="gov-sub">{data.incident_type.replace(/_/g, " ")} — incident details and response coordination.</p>
        </div>
        <Link className="gov-btn gov-btn-secondary" href="/emergency/incidents">Back to List</Link>
      </div>

      <div className="gov-card">
        <div className="gov-section-header">
          <h2 className="gov-section-title">Incident Details</h2>
        </div>
        <div className="gov-kv-grid">
          <div className="gov-kv-label">Incident ID</div>
          <div className="gov-kv-value">{data.id}</div>
          <div className="gov-kv-label">Type</div>
          <div className="gov-kv-value">{data.incident_type.replace(/_/g, " ")}</div>
          <div className="gov-kv-label">Severity</div>
          <div className="gov-kv-value">{data.severity}</div>
          <div className="gov-kv-label">Status</div>
          <div className="gov-kv-value">{data.response_status}</div>
          <div className="gov-kv-label">Section ID</div>
          <div className="gov-kv-value">{data.section_id ?? "—"}</div>
          <div className="gov-kv-label">Track ID</div>
          <div className="gov-kv-value">{data.track_id ?? "—"}</div>
          <div className="gov-kv-label">Latitude</div>
          <div className="gov-kv-value">{data.latitude ?? "—"}</div>
          <div className="gov-kv-label">Longitude</div>
          <div className="gov-kv-value">{data.longitude ?? "—"}</div>
          <div className="gov-kv-label">Description</div>
          <div className="gov-kv-value">{data.description || "—"}</div>
          <div className="gov-kv-label">Reported At</div>
          <div className="gov-kv-value">{fmt(data.reported_at)}</div>
          <div className="gov-kv-label">Reported By (user ID)</div>
          <div className="gov-kv-value">{data.reported_by ?? "—"}</div>
          <div className="gov-kv-label">Railway Alert</div>
          <div className="gov-kv-value">{data.railway_alert_status ?? "—"}</div>
          <div className="gov-kv-label">Police Alert</div>
          <div className="gov-kv-value">{data.police_alert_status ?? "—"}</div>
          <div className="gov-kv-label">Clearance Time</div>
          <div className="gov-kv-value">{fmt(data.clearance_time)}</div>
        </div>
      </div>

      <StatusUpdateCard incident={data} onUpdated={refreshQuiet} />
      <ResponseSection incidentId={data.id} responses={data.responses} onChanged={refreshQuiet} />
    </div>
  );
}

function StatusUpdateCard({ incident, onUpdated }: { incident: IncidentDetail; onUpdated: () => Promise<void> }) {
  const [status, setStatus] = useState(incident.response_status);
  const [severity, setSeverity] = useState(incident.severity);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    setStatus(incident.response_status);
    setSeverity(incident.severity);
  }, [incident.response_status, incident.severity]);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (busy) return;
    setBusy(true);
    setMsg(null);
    setErr(null);
    try {
      const res = await api.patch<{ response_status: string }>(`/api/emergency/incidents/${incident.id}`, {
        response_status: status,
        severity,
      });
      setMsg(`Incident updated — status is now ${res.response_status}.`);
      await onUpdated();
    } catch (e2) {
      setErr(e2 instanceof ApiError ? e2.message : "Failed to update incident");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="gov-card">
      <div className="gov-section-header">
        <h2 className="gov-section-title">Update Status</h2>
      </div>
      <div className="gov-info-box">Current status: <strong>{incident.response_status}</strong>. Only backend-supported statuses are offered.</div>
      <form onSubmit={onSubmit}>
        <div className="gov-form-grid">
          <div>
            <label className="gov-label" htmlFor="inc-status">Response Status *</label>
            <select id="inc-status" className="gov-select" value={status} onChange={(e) => setStatus(e.target.value)} required>
              {RESPONSE_STATUSES.map((s) => <option key={s} value={s}>{s}</option>)}
            </select>
          </div>
          <div>
            <label className="gov-label" htmlFor="inc-sev">Severity *</label>
            <select id="inc-sev" className="gov-select" value={severity} onChange={(e) => setSeverity(e.target.value)} required>
              {SEVERITIES.map((s) => <option key={s} value={s}>{s}</option>)}
            </select>
          </div>
        </div>
        <div className="gov-form-actions">
          <button className="gov-btn" type="submit" disabled={busy}>{busy ? "Updating…" : "Update Incident"}</button>
        </div>
      </form>
      {err ? <div className="gov-alert gov-alert-error" role="alert" style={{ marginTop: 12 }}>{err}</div> : null}
      {msg ? <div className="gov-alert gov-alert-success" role="status" style={{ marginTop: 12 }}>{msg}</div> : null}
    </div>
  );
}

function ResponseSection({ incidentId, responses, onChanged }: { incidentId: number; responses: EmergencyResponse[]; onChanged: () => Promise<void> }) {
  const [authority, setAuthority] = useState(AUTHORITY_TYPES[0]);
  const [authorityName, setAuthorityName] = useState("");
  const [notes, setNotes] = useState("");
  const [creating, setCreating] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);
  const [formSuccess, setFormSuccess] = useState<string | null>(null);
  const [updatingId, setUpdatingId] = useState<number | null>(null);

  async function onCreate(e: React.FormEvent) {
    e.preventDefault();
    if (creating) return;
    setCreating(true);
    setFormError(null);
    setFormSuccess(null);
    try {
      const body: Record<string, unknown> = { authority_type: authority };
      if (authorityName.trim() !== "") body.authority_name = authorityName.trim().slice(0, 150);
      if (notes.trim() !== "") body.notes = notes.trim();
      const res = await api.post<{ id: number }>(`/api/emergency/incidents/${incidentId}/responses`, body);
      setFormSuccess(`Response #${res.id} recorded.`);
      setAuthorityName("");
      setNotes("");
      await onChanged();
    } catch (err) {
      setFormError(err instanceof ApiError ? err.message : "Failed to record response");
    } finally {
      setCreating(false);
    }
  }

  return (
    <div className="gov-card">
      <div className="gov-section-header">
        <h2 className="gov-section-title">Emergency Responses ({responses.length})</h2>
      </div>
      {responses.length === 0 ? (
        <div className="gov-empty">
          <p>No responses recorded yet. Dispatch an authority below.</p>
        </div>
      ) : (
        <div className="gov-table-wrap">
          <table className="gov-table">
            <thead>
              <tr>
                <th>ID</th>
                <th>Authority</th>
                <th>Name</th>
                <th>Status</th>
                <th>Notified</th>
                <th>Acknowledged</th>
                <th>Arrived</th>
                <th>Notes</th>
                <th>Update</th>
              </tr>
            </thead>
            <tbody>
              {responses.map((r) => (
                <ResponseRow key={r.id} response={r} busy={updatingId === r.id} setBusy={(b) => setUpdatingId(b ? r.id : null)} onChanged={onChanged} />
              ))}
            </tbody>
          </table>
        </div>
      )}

      <div className="gov-section-header" style={{ marginTop: 16 }}>
        <h3 className="gov-section-title">Dispatch Response Authority</h3>
      </div>
      {formError ? <div className="gov-alert gov-alert-error" role="alert">{formError}</div> : null}
      {formSuccess ? <div className="gov-alert gov-alert-success" role="status">{formSuccess}</div> : null}
      <form onSubmit={onCreate}>
        <div className="gov-form-grid">
          <div>
            <label className="gov-label" htmlFor="resp-authority">Authority Type *</label>
            <select id="resp-authority" className="gov-select" value={authority} onChange={(e) => setAuthority(e.target.value)} required>
              {AUTHORITY_TYPES.map((a) => <option key={a} value={a}>{a.replace(/_/g, " ")}</option>)}
            </select>
          </div>
          <div>
            <label className="gov-label" htmlFor="resp-name">Authority Name (optional)</label>
            <input id="resp-name" className="gov-input" value={authorityName} onChange={(e) => setAuthorityName(e.target.value)} maxLength={150} placeholder="Unit / station name" />
          </div>
        </div>
        <label className="gov-label" htmlFor="resp-notes">Notes (optional)</label>
        <textarea id="resp-notes" className="gov-textarea" value={notes} onChange={(e) => setNotes(e.target.value)} rows={2} placeholder="Dispatch notes…" />
        <div className="gov-form-actions">
          <button className="gov-btn" type="submit" disabled={creating}>{creating ? "Recording…" : "Record Response"}</button>
        </div>
      </form>
    </div>
  );
}

function ResponseRow({ response, busy, setBusy, onChanged }: { response: EmergencyResponse; busy: boolean; setBusy: (b: boolean) => void; onChanged: () => Promise<void> }) {
  const [status, setStatus] = useState(response.status);
  const [notes, setNotes] = useState(response.notes ?? "");
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    setStatus(response.status);
    setNotes(response.notes ?? "");
  }, [response.status, response.notes]);

  async function onSave() {
    if (busy) return;
    setBusy(true);
    setErr(null);
    try {
      await api.patch(`/api/emergency/responses/${response.id}`, { status, notes: notes.trim() === "" ? null : notes.trim() });
      await onChanged();
    } catch (e2) {
      setErr(e2 instanceof ApiError ? e2.message : "Failed to update response");
    } finally {
      setBusy(false);
    }
  }

  return (
    <tr>
      <td>{response.id}</td>
      <td>{(response.authority_type ?? "—").replace(/_/g, " ")}</td>
      <td>{response.authority_name ?? "—"}</td>
      <td><span className="gov-badge" style={{ background: statusColor(response.status), color: "#fff" }}>{response.status}</span></td>
      <td>{fmt(response.notification_time)}</td>
      <td>{fmt(response.acknowledgement_time)}</td>
      <td>{fmt(response.arrival_time)}</td>
      <td style={{ minWidth: 160 }}>
        <textarea className="gov-textarea" value={notes} onChange={(e) => setNotes(e.target.value)} rows={1} style={{ fontSize: 12 }} />
        {err ? <div className="gov-alert gov-alert-error" role="alert" style={{ marginTop: 6, fontSize: 12 }}>{err}</div> : null}
      </td>
      <td style={{ minWidth: 170 }}>
        <select className="gov-select" value={RESPONSE_LIFECYCLE.includes(status) ? status : RESPONSE_LIFECYCLE[0]} onChange={(e) => setStatus(e.target.value)} style={{ fontSize: 12, marginBottom: 6 }} aria-label={`Response ${response.id} status`}>
          {RESPONSE_LIFECYCLE.map((s) => <option key={s} value={s}>{s.replace(/_/g, " ")}</option>)}
        </select>
        <button className="gov-btn gov-btn-secondary" type="button" onClick={() => void onSave()} disabled={busy} style={{ fontSize: 12, padding: "4px 10px" }}>
          {busy ? "Saving…" : "Save"}
        </button>
      </td>
    </tr>
  );
}
