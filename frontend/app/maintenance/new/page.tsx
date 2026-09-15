"use client";

import React, { useState } from "react";
import { useRouter } from "next/navigation";
import ProtectedRoute from "@/components/ProtectedRoute";
import AppShell from "@/components/AppShell";
import Breadcrumbs from "@/components/Breadcrumbs";
import { api, ApiError } from "@/lib/api-client";
import type { MaintenancePriority, MaintenanceRequest } from "@/types/maintenance";

function toLocalInput(iso: string): string {
  const d = new Date(iso);
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

export default function NewMaintenancePage() {
  return (
    <ProtectedRoute>
      <AppShell>
        <NewForm />
      </AppShell>
    </ProtectedRoute>
  );
}

function NewForm() {
  const router = useRouter();
  const [assetId, setAssetId] = useState("");
  const [sectionId, setSectionId] = useState("");
  const [trackId, setTrackId] = useState("");
  const [maintenanceType, setMaintenanceType] = useState("");
  const [description, setDescription] = useState("");
  const [priority, setPriority] = useState<MaintenancePriority>("MEDIUM");
  const [start, setStart] = useState("");
  const [end, setEnd] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (loading) return;
    setError(null);
    if (!assetId || !sectionId || !maintenanceType.trim() || !start || !end) {
      setError("Please fill all required fields.");
      return;
    }
    if (new Date(end) <= new Date(start)) {
      setError("Requested end must be after requested start.");
      return;
    }
    setLoading(true);
    try {
      const payload: Record<string, unknown> = {
        asset_id: Number(assetId),
        section_id: Number(sectionId),
        maintenance_type: maintenanceType.trim(),
        priority,
        requested_start: new Date(start).toISOString(),
        requested_end: new Date(end).toISOString(),
      };
      if (trackId.trim() !== "") payload.track_id = Number(trackId);
      if (description.trim() !== "") payload.description = description.trim();
      const res = await api.post<MaintenanceRequest>("/api/maintenance/requests", payload);
      router.replace(`/maintenance/${res.id}`);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Unable to connect to the railway service. Please try again.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="gov-page">
      <Breadcrumbs
        trail={[
          { label: "Dashboard", href: "/dashboard" },
          { label: "Maintenance Requests", href: "/maintenance" },
          { label: "New Request" },
        ]}
      />

      <div className="gov-page-header">
        <div>
          <h2 className="gov-title">New Maintenance Request</h2>
          <p className="gov-sub">Department is derived from your account and asset by the backend.</p>
        </div>
      </div>

      <div className="gov-card">
        <form onSubmit={onSubmit}>
          <div className="gov-form-grid">
            <div>
              <label className="gov-label" htmlFor="asset">
                Asset ID <span className="gov-required">*</span>
              </label>
              <input id="asset" className="gov-input" inputMode="numeric" value={assetId} onChange={(e) => setAssetId(e.target.value)} required />
            </div>
            <div>
              <label className="gov-label" htmlFor="section">
                Section ID <span className="gov-required">*</span>
              </label>
              <input id="section" className="gov-input" inputMode="numeric" value={sectionId} onChange={(e) => setSectionId(e.target.value)} required />
            </div>
            <div>
              <label className="gov-label" htmlFor="track">Track ID (optional)</label>
              <input id="track" className="gov-input" inputMode="numeric" value={trackId} onChange={(e) => setTrackId(e.target.value)} />
            </div>
            <div>
              <label className="gov-label" htmlFor="mtype">
                Maintenance Type <span className="gov-required">*</span>
              </label>
              <input id="mtype" className="gov-input" value={maintenanceType} onChange={(e) => setMaintenanceType(e.target.value)} minLength={2} maxLength={100} required />
            </div>
            <div>
              <label className="gov-label" htmlFor="priority">
                Priority <span className="gov-required">*</span>
              </label>
              <select id="priority" className="gov-select" value={priority} onChange={(e) => setPriority(e.target.value as MaintenancePriority)}>
                <option value="LOW">LOW</option>
                <option value="MEDIUM">MEDIUM</option>
                <option value="HIGH">HIGH</option>
                <option value="CRITICAL">CRITICAL</option>
              </select>
            </div>
            <div>
              <label className="gov-label" htmlFor="start">
                Requested Start <span className="gov-required">*</span>
              </label>
              <input id="start" className="gov-input" type="datetime-local" value={start} onChange={(e) => setStart(e.target.value)} required />
            </div>
            <div>
              <label className="gov-label" htmlFor="end">
                Requested End <span className="gov-required">*</span>
              </label>
              <input id="end" className="gov-input" type="datetime-local" value={end} onChange={(e) => setEnd(e.target.value)} required />
            </div>
            <div className="full-width">
              <label className="gov-label" htmlFor="desc">Description</label>
              <textarea id="desc" className="gov-input" rows={3} maxLength={2000} value={description} onChange={(e) => setDescription(e.target.value)} />
            </div>
          </div>

          {error ? (
            <div className="gov-alert gov-alert-error" role="alert">{error}</div>
          ) : null}

          <div className="gov-form-actions">
            <button className="gov-btn" type="submit" disabled={loading}>
              {loading ? "Submitting…" : "Create Request"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
