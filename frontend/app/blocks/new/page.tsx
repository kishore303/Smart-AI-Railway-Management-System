"use client";

import React, { useState } from "react";
import { useRouter } from "next/navigation";
import ProtectedRoute from "@/components/ProtectedRoute";
import AppShell from "@/components/AppShell";
import Breadcrumbs from "@/components/Breadcrumbs";
import { api, ApiError } from "@/lib/api-client";
import type { BlockRequest } from "@/types/blocks";

export default function NewBlockPage() {
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
  const [maintenanceId, setMaintenanceId] = useState("");
  const [start, setStart] = useState("");
  const [end, setEnd] = useState("");
  const [blockType, setBlockType] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (loading) return;
    setError(null);
    if (!maintenanceId || !start || !end) {
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
        maintenance_request_id: Number(maintenanceId),
        requested_start: new Date(start).toISOString(),
        requested_end: new Date(end).toISOString(),
      };
      if (blockType.trim() !== "") payload.block_type = blockType.trim().slice(0, 50);
      const res = await api.post<BlockRequest>("/api/blocks/requests", payload);
      router.replace(`/blocks/${res.id}`);
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
          { label: "Block Planning", href: "/blocks" },
          { label: "New Block Request" },
        ]}
      />
      <div className="gov-page-header">
        <div>
          <h2 className="gov-title">New Block Request</h2>
          <p className="gov-sub">Section and track are derived from the maintenance request by the backend. The request must be VERIFIED, BLOCK_PLANNING or AI_RECOMMENDATION.</p>
        </div>
      </div>
      <div className="gov-card">
        <form onSubmit={onSubmit}>
          <div className="gov-form-grid">
            <div>
              <label className="gov-label" htmlFor="maint-id">Maintenance Request ID <span className="gov-required">*</span></label>
              <input id="maint-id" className="gov-input" inputMode="numeric" value={maintenanceId} onChange={(e) => setMaintenanceId(e.target.value)} required />
            </div>
            <div>
              <label className="gov-label" htmlFor="b-type">Block Type (optional)</label>
              <input id="b-type" className="gov-input" value={blockType} onChange={(e) => setBlockType(e.target.value)} maxLength={50} placeholder="e.g. TRAFFIC, POWER, SIGNAL" />
            </div>
            <div>
              <label className="gov-label" htmlFor="b-start">Requested Start <span className="gov-required">*</span></label>
              <input id="b-start" className="gov-input" type="datetime-local" value={start} onChange={(e) => setStart(e.target.value)} required />
            </div>
            <div>
              <label className="gov-label" htmlFor="b-end">Requested End <span className="gov-required">*</span></label>
              <input id="b-end" className="gov-input" type="datetime-local" value={end} onChange={(e) => setEnd(e.target.value)} required />
            </div>
          </div>
          {error ? <div className="gov-alert gov-alert-error" role="alert">{error}</div> : null}
          <div className="gov-form-actions">
            <button className="gov-btn" type="submit" disabled={loading}>
              {loading ? "Submitting…" : "Create Block Request"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
