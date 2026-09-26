"use client";

import React, { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import ProtectedRoute from "@/components/ProtectedRoute";
import AppShell from "@/components/AppShell";
import Breadcrumbs from "@/components/Breadcrumbs";
import { api, ApiError } from "@/lib/api-client";
import { useAuth } from "@/lib/auth-context";
import type {
  Allocation,
  AvailabilityResult,
  ExecutionDetail,
  ResourceListResponse,
} from "@/types/execution";
import { executionBadgeKind } from "@/types/execution";

const EXECUTION_ROLES = ["CONTROLLER", "AUTHORIZED_OFFICIAL", "SENIOR_SECTION_ENGINEER"];

export default function ExecutionDetailPage() {
  const params = useParams<{ id: string }>();
  const id = params.id;
  return (
    <ProtectedRoute>
      <AppShell>
        <DetailContent optimizedId={id} />
      </AppShell>
    </ProtectedRoute>
  );
}

function opError(err: unknown): string {
  if (err instanceof ApiError) {
    if (err.status === 403) return "Your role or department is not permitted for this action.";
    if (err.status === 409) return `This block is not eligible for execution. (${err.message})`;
    return err.message;
  }
  return "Unable to connect to the railway service. Please try again.";
}

function DetailContent({ optimizedId }: { optimizedId: string }) {
  const { user } = useAuth();
  const canAct = user ? EXECUTION_ROLES.includes(user.role) : false;

  const [detail, setDetail] = useState<ExecutionDetail | null>(null);
  const [resources, setResources] = useState<ResourceListResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [allocRes, setAllocRes] = useState("");
  const [allocQty, setAllocQty] = useState(1);
  const [allocBusy, setAllocBusy] = useState(false);
  const [allocMsg, setAllocMsg] = useState<string | null>(null);
  const [allocErr, setAllocErr] = useState<string | null>(null);

  const [availRes, setAvailRes] = useState("");
  const [availResult, setAvailResult] = useState<AvailabilityResult | null>(null);
  const [availBusy, setAvailBusy] = useState(false);
  const [availErr, setAvailErr] = useState<string | null>(null);

  const [opBusy, setOpBusy] = useState(false);
  const [opErr, setOpErr] = useState<string | null>(null);
  const [opMsg, setOpMsg] = useState<string | null>(null);
  const [cancelReason, setCancelReason] = useState("");
  const [confirmOp, setConfirmOp] = useState<"start" | "complete" | "cancel" | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const d = await api.get<ExecutionDetail>(`/api/execution/${optimizedId}`);
      setDetail(d);
      try {
        const r = await api.get<ResourceListResponse>(`/api/execution/${optimizedId}/resources`);
        setResources(r);
      } catch {
        setResources(null);
      }
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Unable to connect to the railway service. Please try again.");
    } finally {
      setLoading(false);
    }
  }, [optimizedId]);

  useEffect(() => {
    void load();
  }, [load]);

  async function onAllocate(e: React.FormEvent) {
    e.preventDefault();
    if (allocBusy || allocRes.trim() === "") return;
    setAllocBusy(true);
    setAllocErr(null);
    setAllocMsg(null);
    try {
      const a = await api.post<Allocation>(`/api/execution/${optimizedId}/resources/allocate`, {
        resource_id: Number(allocRes),
        quantity: allocQty,
      });
      setAllocMsg(`Allocated ${a.resource_code ?? a.resource_id} (allocation #${a.id}).`);
      setAllocRes("");
      await load();
    } catch (err) {
      setAllocErr(opError(err));
    } finally {
      setAllocBusy(false);
    }
  }

  async function onRelease(allocationId: number) {
    if (allocBusy) return;
    setAllocBusy(true);
    setAllocErr(null);
    setAllocMsg(null);
    try {
      await api.post(`/api/execution/${optimizedId}/resources/${allocationId}/release`, {});
      setAllocMsg(`Allocation #${allocationId} released.`);
      await load();
    } catch (err) {
      setAllocErr(opError(err));
    } finally {
      setAllocBusy(false);
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
        `/api/execution/${optimizedId}/resources/availability?${params.toString()}`
      );
      setAvailResult(r);
    } catch (err) {
      setAvailErr(err instanceof ApiError ? err.message : "Unable to connect to the railway service. Please try again.");
    } finally {
      setAvailBusy(false);
    }
  }

  async function runOp(op: "start" | "complete" | "cancel") {
    if (opBusy) return;
    if (op === "cancel" && cancelReason.trim().length < 3) {
      setOpErr("A cancellation reason of at least 3 characters is required.");
      return;
    }
    setOpBusy(true);
    setOpErr(null);
    setOpMsg(null);
    try {
      const payload: Record<string, unknown> = {};
      if (op === "cancel") payload.reason = cancelReason.trim().slice(0, 500);
      const r = await api.post<{ status: string }>(`/api/execution/${optimizedId}/${op}`, payload);
      setOpMsg(`Execution ${op} successful — new status: ${r.status}.`);
      setConfirmOp(null);
      setCancelReason("");
      await load();
    } catch (err) {
      setOpErr(opError(err));
    } finally {
      setOpBusy(false);
    }
  }

  if (loading) {
    return (
      <div className="gov-page">
        <Breadcrumbs trail={[{ label: "Dashboard", href: "/dashboard" }, { label: "Execution", href: "/execution" }, { label: `#${optimizedId}` }]} />
        <div className="gov-card"><div className="gov-loading">Loading execution…</div></div>
      </div>
    );
  }

  if (error || !detail) {
    return (
      <div className="gov-page">
        <Breadcrumbs trail={[{ label: "Dashboard", href: "/dashboard" }, { label: "Execution", href: "/execution" }, { label: `#${optimizedId}` }]} />
        <div className="gov-card">
          <div className="gov-alert gov-alert-error" role="alert">{error ?? "Execution record not found."}</div>
        </div>
      </div>
    );
  }

  const canStart = detail.status === "APPROVED";
  const canComplete = detail.status === "ACTIVE";
  const canCancel = detail.status === "APPROVED" || detail.status === "ACTIVE";

  return (
    <div className="gov-page">
      <Breadcrumbs
        trail={[
          { label: "Dashboard", href: "/dashboard" },
          { label: "Execution", href: "/execution" },
          { label: detail.block_code },
        ]}
      />

      <div className="gov-page-header">
        <div>
          <h2 className="gov-title">
            Execution {detail.block_code}{" "}
            <span className={`gov-badge gov-badge-${executionBadgeKind(detail.status)}`}>{detail.status}</span>
          </h2>
          <p className="gov-sub">
            {detail.status === "ACTIVE"
              ? "ACTIVE — execution is in progress (not merely approved)."
              : "Only APPROVED blocks may start execution. Backend approval and safety gates are authoritative."}
          </p>
        </div>
      </div>

      <div className={`gov-alert gov-alert-${detail.is_eligible_for_start ? "success" : "error"}`} role="status">
        <strong>{detail.is_eligible_for_start ? "Eligible to start execution" : "Not eligible to start"}</strong>
        {detail.eligibility_reasons.length > 0 ? (
          <ul className="gov-list" style={{ marginTop: 8 }}>
            {detail.eligibility_reasons.map((r, i) => <li key={i}>{r}</li>)}
          </ul>
        ) : null}
      </div>

      <div className="gov-card">
        <div className="gov-section-header">
          <h3>Execution Details</h3>
        </div>
        <div className="gov-kv-grid">
          <span className="gov-kv-label">Department</span>
          <span className="gov-kv-value">{detail.department_code ?? "—"}</span>
          <span className="gov-kv-label">Section / Track</span>
          <span className="gov-kv-value">{detail.section_id} / {detail.track_id ?? "—"}</span>
          <span className="gov-kv-label">Scheduled Start</span>
          <span className="gov-kv-value">{detail.start_time ? new Date(detail.start_time).toLocaleString() : "—"}</span>
          <span className="gov-kv-label">Scheduled End</span>
          <span className="gov-kv-value">{detail.end_time ? new Date(detail.end_time).toLocaleString() : "—"}</span>
          <span className="gov-kv-label">Safety Status</span>
          <span className="gov-kv-value">
            <span className={`gov-badge gov-badge-${detail.safety_status === "SAFE" ? "green" : detail.safety_status === "UNSAFE" ? "red" : "amber"}`}>
              {detail.safety_status ?? "Not validated"}
            </span>
          </span>
          <span className="gov-kv-label">Optimization Score</span>
          <span className="gov-kv-value">{detail.optimization_score ?? "—"}</span>
          <span className="gov-kv-label">Recommendation</span>
          <span className="gov-kv-value">
            <Link className="gov-link" href={`/recommendations/${detail.optimized_block_id}`}>Open Recommendation</Link>
          </span>
        </div>
      </div>

      <div className="gov-card">
        <div className="gov-section-header">
          <h3>Allocated Resources ({detail.allocated_resources.length})</h3>
        </div>
        {detail.allocated_resources.length === 0 ? (
          <div className="gov-info-box">No resources allocated yet. Allocation is allowed once the block is APPROVED.</div>
        ) : (
          <div className="gov-table-wrap">
            <table className="gov-table">
              <thead><tr><th>ID</th><th>Resource</th><th>Qty</th><th>From → Until</th><th>Status</th><th>Action</th></tr></thead>
              <tbody>
                {detail.allocated_resources.map((a) => (
                  <tr key={a.id}>
                    <td>{a.id}</td>
                    <td>{a.resource_code ?? a.resource_id}</td>
                    <td>{a.quantity_required}</td>
                    <td>{new Date(a.allocated_from).toLocaleString()} → {new Date(a.allocated_until).toLocaleString()}</td>
                    <td><span className={`gov-badge gov-badge-${executionBadgeKind(a.status)}`}>{a.status}</span></td>
                    <td>
                      {a.status === "ALLOCATED" && canAct ? (
                        <button type="button" className="gov-btn gov-btn-sm gov-btn-danger" onClick={() => void onRelease(a.id)}>
                          Release
                        </button>
                      ) : "—"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        {allocMsg ? <div className="gov-alert gov-alert-success" role="status" style={{ marginTop: 8 }}>{allocMsg}</div> : null}
        {allocErr ? <div className="gov-alert gov-alert-error" role="alert" style={{ marginTop: 8 }}>{allocErr}</div> : null}

        {canAct ? (
          <div style={{ marginTop: 16 }}>
            <div className="gov-section-header">
              <h4>Check Availability</h4>
            </div>
            <form onSubmit={onAvailability} style={{ display: "flex", gap: 12, alignItems: "end", flexWrap: "wrap" }}>
              <div style={{ flex: 1, minWidth: 160 }}>
                <label className="gov-label" htmlFor="ex-avail">Resource ID *</label>
                <input id="ex-avail" className="gov-input" inputMode="numeric" value={availRes} onChange={(e) => setAvailRes(e.target.value)} required />
              </div>
              <button className="gov-btn gov-btn-secondary" type="submit" disabled={availBusy}>
                {availBusy ? "Checking…" : "Check"}
              </button>
            </form>
            {availErr ? <div className="gov-alert gov-alert-error" role="alert" style={{ marginTop: 8 }}>{availErr}</div> : null}
            {availResult ? (
              <div className={`gov-alert gov-alert-${availResult.is_available ? "success" : "error"}`} role="status" style={{ marginTop: 8 }}>
                {availResult.resource_code}: {availResult.is_available ? "Available" : "Unavailable"} — {availResult.reason}
              </div>
            ) : null}

            <div className="gov-section-header" style={{ marginTop: 16 }}>
              <h4>Allocate Resource</h4>
            </div>
            <form onSubmit={onAllocate} style={{ display: "flex", gap: 12, alignItems: "end", flexWrap: "wrap" }}>
              <div style={{ flex: 1, minWidth: 160 }}>
                <label className="gov-label" htmlFor="ex-alloc">Resource ID *</label>
                <input id="ex-alloc" className="gov-input" inputMode="numeric" value={allocRes} onChange={(e) => setAllocRes(e.target.value)} required />
              </div>
              <div>
                <label className="gov-label" htmlFor="ex-qty">Quantity (1–100) *</label>
                <input id="ex-qty" className="gov-input" type="number" min={1} max={100} value={allocQty} onChange={(e) => setAllocQty(Number(e.target.value))} required />
              </div>
              <button className="gov-btn" type="submit" disabled={allocBusy}>
                {allocBusy ? "Allocating…" : "Allocate"}
              </button>
            </form>
          </div>
        ) : null}

        {resources && resources.items.length > 0 ? (
          <div style={{ marginTop: 16 }}>
            <div className="gov-section-header">
              <h4>Department Resources ({resources.total})</h4>
            </div>
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
          </div>
        ) : null}
      </div>

      <div className="gov-card gov-card-accent">
        <div className="gov-section-header">
          <h3>Execution Actions</h3>
        </div>
        {!canAct ? (
          <div className="gov-info-box">
            Execution actions require Controller, Authorized Official, or Engineer Reviewer role.
            You are signed in as {user?.role ?? "unknown"}. Backend enforcement remains authoritative.
          </div>
        ) : (
          <>
            <div className="gov-tabs">
              <button
                className={`gov-tab${confirmOp === "start" ? " active" : ""}`}
                disabled={!canStart || confirmOp !== null}
                onClick={() => setConfirmOp("start")}
              >
                Start Execution
              </button>
              <button
                className={`gov-tab${confirmOp === "complete" ? " active" : ""}`}
                disabled={!canComplete || confirmOp !== null}
                onClick={() => setConfirmOp("complete")}
              >
                Complete
              </button>
              <button
                className={`gov-tab${confirmOp === "cancel" ? " active" : ""}`}
                disabled={!canCancel || confirmOp !== null}
                onClick={() => setConfirmOp("cancel")}
              >
                Cancel
              </button>
            </div>
            {!canStart && detail.status !== "ACTIVE" && detail.status !== "COMPLETED" && detail.status !== "CANCELLED" ? (
              <div className="gov-info-box">Start is disabled: block status is {detail.status} (must be APPROVED).</div>
            ) : null}
            {confirmOp ? (
              <div className="gov-alert gov-alert-error" role="alert" style={{ marginTop: 12 }}>
                <p>
                  <strong>Confirm {confirmOp} of {detail.block_code}?</strong>{" "}
                  {confirmOp === "start" ? "Backend re-checks safety, approval, conflicts, and open incidents." : confirmOp === "complete" ? "Completion releases all allocated resources." : "Cancellation releases resources and ends the block."}
                </p>
                {confirmOp === "cancel" ? (
                  <div style={{ marginTop: 8 }}>
                    <label className="gov-label" htmlFor="ex-cancel-reason">Cancellation Reason * (min 3 characters)</label>
                    <textarea id="ex-cancel-reason" className="gov-input" rows={2} value={cancelReason} onChange={(e) => setCancelReason(e.target.value)} maxLength={500} />
                  </div>
                ) : null}
                <div className="gov-btn-group" style={{ marginTop: 8 }}>
                  <button className={`gov-btn${confirmOp === "cancel" ? " gov-btn-danger" : confirmOp === "start" ? " gov-btn-success" : ""}`} onClick={() => void runOp(confirmOp)} disabled={opBusy}>
                    {opBusy ? "Submitting…" : `Confirm ${confirmOp}`}
                  </button>
                  <button className="gov-btn gov-btn-secondary" onClick={() => { setConfirmOp(null); setOpErr(null); }} disabled={opBusy}>
                    Back
                  </button>
                </div>
              </div>
            ) : null}
            {opErr ? <div className="gov-alert gov-alert-error" role="alert" style={{ marginTop: 12 }}>{opErr}</div> : null}
            {opMsg ? <div className="gov-alert gov-alert-success" role="status" style={{ marginTop: 8 }}>{opMsg}</div> : null}
          </>
        )}
      </div>

      {detail.audit_history.length > 0 ? (
        <div className="gov-card">
          <div className="gov-section-header">
            <h3>Execution History ({detail.audit_history.length})</h3>
          </div>
          <div className="gov-table-wrap">
            <table className="gov-table">
              <thead><tr><th>Action</th><th>User</th><th>Description</th><th>At</th></tr></thead>
              <tbody>
                {detail.audit_history.map((h, i) => (
                  <tr key={i}>
                    <td><span className={`gov-badge gov-badge-${h.action === "START" ? "green" : h.action === "CANCEL" ? "red" : "blue"}`}>{h.action}</span></td>
                    <td>{h.user_id != null ? `User #${h.user_id}` : "—"}</td>
                    <td>{h.description ?? "—"}</td>
                    <td>{h.created_at ? new Date(h.created_at).toLocaleString() : "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      ) : null}
    </div>
  );
}
