"use client";

import React, { useState } from "react";
import Link from "next/link";
import ProtectedRoute from "@/components/ProtectedRoute";
import AppShell from "@/components/AppShell";
import Breadcrumbs from "@/components/Breadcrumbs";

export default function ExecutionPage() {
  return (
    <ProtectedRoute>
      <AppShell>
        <ExecLanding />
      </AppShell>
    </ProtectedRoute>
  );
}

function ExecLanding() {
  const [obId, setObId] = useState("");

  return (
    <div className="gov-page">
      <Breadcrumbs trail={[{ label: "Dashboard", href: "/dashboard" }, { label: "Execution" }]} />

      <div className="gov-page-header">
        <div>
          <h2 className="gov-title">Block Execution</h2>
          <p className="gov-sub">
            Execution follows official approval: APPROVED → ACTIVE → COMPLETED (or CANCELLED).
            Only APPROVED optimized blocks may start. Open execution by optimized block ID.
          </p>
        </div>
      </div>

      <div className="gov-card">
        <div className="gov-section-header">
          <h3>Open Execution</h3>
        </div>
        <form
          onSubmit={(e) => e.preventDefault()}
          style={{ display: "flex", gap: 12, alignItems: "end", flexWrap: "wrap" }}
        >
          <div style={{ flex: 1, minWidth: 200 }}>
            <label className="gov-label" htmlFor="exec-ob">Optimized Block ID *</label>
            <input
              id="exec-ob"
              className="gov-input"
              inputMode="numeric"
              value={obId}
              onChange={(e) => setObId(e.target.value)}
              placeholder="e.g. 5"
            />
          </div>
          {obId.trim() !== "" ? (
            <Link className="gov-btn" style={{ textDecoration: "none", textAlign: "center" }} href={`/execution/${obId.trim()}`}>
              Open Execution
            </Link>
          ) : (
            <button className="gov-btn" type="submit" disabled>
              Open Execution
            </button>
          )}
        </form>
        <div className="gov-info-box" style={{ marginTop: 12 }}>
          Tip: find the optimized block ID on the <Link className="gov-link" href="/recommendations">Recommendations</Link> page
          or the <Link className="gov-link" href="/resources">Resources</Link> page.
        </div>
      </div>
    </div>
  );
}
