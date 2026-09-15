"use client";

import React, { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import ProtectedRoute from "@/components/ProtectedRoute";
import AppShell from "@/components/AppShell";
import Breadcrumbs from "@/components/Breadcrumbs";
import SafetyChecksTable from "@/components/SafetyChecksTable";
import { api, ApiError } from "@/lib/api-client";
import type { SafetyValidationResult } from "@/types/safety";
import { safetyBadgeKind } from "@/types/safety";

export default function SafetyDetailPage() {
  const params = useParams<{ id: string }>();
  const id = params.id;
  return (
    <ProtectedRoute>
      <AppShell>
        <DetailContent candidateId={id} />
      </AppShell>
    </ProtectedRoute>
  );
}

function DetailContent({ candidateId }: { candidateId: string }) {
  const [data, setData] = useState<SafetyValidationResult | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [revalLoading, setRevalLoading] = useState(false);
  const [revalError, setRevalError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const r = await api.get<SafetyValidationResult>(`/api/safety/validations/candidate/${candidateId}`);
      setData(r);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Unable to connect to the railway service. Please try again.");
    } finally {
      setLoading(false);
    }
  }, [candidateId]);

  useEffect(() => {
    void load();
  }, [load]);

  async function onRevalidate() {
    if (revalLoading) return;
    setRevalLoading(true);
    setRevalError(null);
    try {
      const r = await api.post<SafetyValidationResult>(`/api/safety/validate/candidate/${candidateId}`, {});
      setData(r);
    } catch (err) {
      setRevalError(
        err instanceof ApiError && err.status === 403
          ? "You are not permitted to perform safety validation with your current role."
          : err instanceof ApiError
            ? err.message
            : "Unable to connect to the railway service. Please try again."
      );
    } finally {
      setRevalLoading(false);
    }
  }

  if (loading) {
    return (
      <div className="gov-page">
        <Breadcrumbs trail={[{ label: "Dashboard", href: "/dashboard" }, { label: "Safety Validation", href: "/safety" }, { label: `Candidate #${candidateId}` }]} />
        <div className="gov-card"><div className="gov-loading">Loading safety validation…</div></div>
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="gov-page">
        <Breadcrumbs trail={[{ label: "Dashboard", href: "/dashboard" }, { label: "Safety Validation", href: "/safety" }, { label: `Candidate #${candidateId}` }]} />
        <div className="gov-card">
          <div className="gov-alert gov-alert-error" role="alert">{error ?? "Safety validation not found."}</div>
          <div className="gov-info-box">
            If no validation exists yet, run it from the <Link className="gov-link" href="/safety">Safety Validation</Link> page.
          </div>
        </div>
      </div>
    );
  }

  const isSafe = data.overall_status === "SAFE";

  return (
    <div className="gov-page">
      <Breadcrumbs
        trail={[
          { label: "Dashboard", href: "/dashboard" },
          { label: "Safety Validation", href: "/safety" },
          { label: `Candidate #${data.candidate_id}` },
        ]}
      />

      <div className="gov-page-header">
        <div>
          <h2 className="gov-title">
            Safety Validation — Candidate #{data.candidate_id}{" "}
            <span className={`gov-badge gov-badge-${isSafe ? "green" : "red"}`}>{data.overall_status}</span>
          </h2>
          <p className="gov-sub">
            {isSafe
              ? "SAFE — Safety validation passed. This is not an approval."
              : "UNSAFE — Safety validation failed. This candidate must not proceed to optimization or approval."}
          </p>
        </div>
        <button className="gov-btn gov-btn-secondary" onClick={() => void onRevalidate()} disabled={revalLoading}>
          {revalLoading ? "Re-validating…" : "Re-run Safety Validation"}
        </button>
      </div>

      <div className={isSafe ? "gov-card gov-card-success" : "gov-card gov-card-danger"}>
        <div className="gov-section-header">
          <h3 className="gov-section-title">Validation Summary</h3>
        </div>
        <div className="gov-kv-grid">
          <div className="gov-kv-label">Overall Status</div>
          <div className="gov-kv-value"><span className={`gov-badge gov-badge-${isSafe ? "green" : "red"}`}>{data.overall_status}</span></div>
          <div className="gov-kv-label">Safe for Optimization</div>
          <div className="gov-kv-value">{data.is_safe_for_optimization ? "Yes" : "No"}</div>
          <div className="gov-kv-label">Block Request</div>
          <div className="gov-kv-value"><Link className="gov-link" href={`/blocks/${data.block_request_id}`}>{data.block_request_id}</Link></div>
          <div className="gov-kv-label">Planning Status</div>
          <div className="gov-kv-value">{data.planning_safety_status ?? "—"}</div>
          <div className="gov-kv-label">Validated By (user ID)</div>
          <div className="gov-kv-value">{data.validated_by ?? "—"}</div>
          <div className="gov-kv-label">Validated At</div>
          <div className="gov-kv-value">{data.validated_at ? new Date(data.validated_at).toLocaleString() : "—"}</div>
        </div>
        {data.disclaimer ? (
          <div className="gov-info-box">{data.disclaimer}</div>
        ) : null}
        {revalError ? <div className="gov-alert gov-alert-error" role="alert">{revalError}</div> : null}
      </div>

      {data.rejection_reasons.length > 0 ? (
        <div className="gov-card gov-card-danger">
          <div className="gov-section-header">
            <h3 className="gov-section-title">Failure Reasons</h3>
          </div>
          <ul className="gov-list">
            {data.rejection_reasons.map((r, i) => <li key={i}>{r}</li>)}
          </ul>
        </div>
      ) : null}

      {data.warnings.length > 0 ? (
        <div className="gov-card gov-card-warning">
          <div className="gov-section-header">
            <h3 className="gov-section-title">Warnings</h3>
          </div>
          <ul className="gov-list">
            {data.warnings.map((w, i) => <li key={i}>{w}</li>)}
          </ul>
        </div>
      ) : null}

      <div className="gov-card">
        <div className="gov-section-header">
          <h3 className="gov-section-title">All Safety Checks ({data.checks.length})</h3>
        </div>
        <SafetyChecksTable checks={data.checks} />
      </div>
    </div>
  );
}
