"use client";

import React, { Suspense, useState } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useAuth } from "@/lib/auth-context";
import { ApiError } from "@/lib/api-client";

// All 13 SIH Demo Accounts for Jury Access
const DEMO_ACCOUNTS_DATA = [
  {
    category: "1. Engineering Department",
    deptCode: "ENG",
    accounts: [
      { roleName: "Maintenance Staff", username: "eng_staff", desc: "Create track work orders & view requests" },
      { roleName: "Junior Engineer (JE)", username: "eng_je", desc: "Initial technical verification & conflict check" },
      { roleName: "Senior Section Engineer (SSE)", username: "eng_sse", desc: "Senior verification & forward to AI planning" },
    ],
  },
  {
    category: "2. Electrical / OHE Department",
    deptCode: "ELEC",
    accounts: [
      { roleName: "Maintenance Staff", username: "elec_staff", desc: "Create OHE/power maintenance requests" },
      { roleName: "Junior Engineer (JE)", username: "elec_je", desc: "Verify electrical assets & isolation requirements" },
      { roleName: "Senior Section Engineer (SSE)", username: "elec_sse", desc: "Validate OHE blocks & cross-dept integration" },
    ],
  },
  {
    category: "3. S&T (Signal & Telecom)",
    deptCode: "SNT",
    accounts: [
      { roleName: "Maintenance Staff", username: "snt_staff", desc: "Create signaling & interlocking requests" },
      { roleName: "Junior Engineer (JE)", username: "snt_je", desc: "Technical review of point/signal assets" },
      { roleName: "Senior Section Engineer (SSE)", username: "snt_sse", desc: "Senior validation & joint-block coordination" },
    ],
  },
  {
    category: "4. Operations / Traffic",
    deptCode: "OPS",
    accounts: [
      { roleName: "Traffic Operator", username: "operations", desc: "Monitor timetables, train delays & ripple impact" },
    ],
  },
  {
    category: "5. Railway Control",
    deptCode: "CONTROL",
    accounts: [
      { roleName: "Section Controller", username: "control", desc: "Live train control, block grant & active track ops" },
    ],
  },
  {
    category: "6. Railway Authorized Official (Final Authority)",
    deptCode: "RAILWAY",
    accounts: [
      { roleName: "Authorized Official (DRM/Sr.DOM)", username: "railway_official", desc: "Final decision: Approve, Modify, or Reject blocks" },
    ],
  },
  {
    category: "7. Emergency Response",
    deptCode: "EMERGENCY",
    accounts: [
      { roleName: "Emergency Operator", username: "emergency", desc: "Trigger incidents, safety corridors & emergency replanning" },
    ],
  },
];

function LoginForm() {
  const { login } = useAuth();
  const router = useRouter();
  const searchParams = useSearchParams();
  const redirectTo = searchParams.get("redirect") || "/dashboard";
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<string>("all");

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (loading) return;
    setError(null);
    setLoading(true);
    try {
      await login(username.trim(), password);
      router.replace(redirectTo);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Invalid username or password.");
    } finally {
      setLoading(false);
    }
  }

  function handleQuickFill(u: string) {
    setUsername(u);
    setPassword("");
    setError(null);
  }

  const isDemoMode = process.env.NEXT_PUBLIC_DEMO_MODE !== "false";

  return (
    <div className="login-shell" style={{ maxWidth: isDemoMode ? 1200 : 480, margin: "24px auto", padding: "0 16px" }}>
      {/* Brand Header */}
      <div className="login-brand" style={{ borderRadius: 10, padding: 24, marginBottom: 20 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 16 }}>
          <div className="gov-header-emblem" aria-hidden="true" style={{ width: 48, height: 48, fontSize: 20, display: "flex", alignItems: "center", justifyContent: "center", borderRadius: "50%", background: "#0b2545", color: "#fff", fontWeight: "bold" }}>
            IR
          </div>
          <div>
            <h1 style={{ margin: 0, fontSize: 22, color: "var(--navy, #0b2545)" }}>SIH26027 — Indian Railways Block Planning System</h1>
            <p className="brand-sub" style={{ margin: "4px 0 0", color: "#555", fontSize: 14 }}>
              Decision-Support Platform: ML Predicts → Safety Validates → OR-Tools Optimizes → Authorized Official Decides
            </p>
          </div>
        </div>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: isDemoMode ? "380px 1fr" : "1fr", gap: 24, alignItems: "start" }}>
        {/* Left: Common Login Form */}
        <main className="login-panel">
          <div className="login-card" style={{ background: "#ffffff", border: "1px solid #d0d7de", borderRadius: 10, padding: 24, boxShadow: "0 4px 12px rgba(0,0,0,0.06)" }}>
            <h2 style={{ fontSize: 18, margin: "0 0 4px", color: "#0b2545" }}>Single Common Login</h2>
            <p className="login-lead" style={{ fontSize: 13, color: "#666", margin: "0 0 20px" }}>
              Sign in with your department credentials to access your designated role workspace.
            </p>

            <form onSubmit={onSubmit}>
              <div style={{ marginBottom: 16 }}>
                <label className="gov-label" htmlFor="username" style={{ display: "block", fontSize: 13, fontWeight: 600, marginBottom: 6 }}>
                  Username or Email <span className="gov-required" style={{ color: "#d9383a" }}>*</span>
                </label>
                <input
                  id="username"
                  className="gov-input"
                  autoComplete="username"
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  placeholder="e.g. eng_staff, railway_official"
                  required
                  style={{ width: "100%", padding: "9px 12px", borderRadius: 6, border: "1px solid #ccc" }}
                />
              </div>

              <div style={{ marginBottom: 12 }}>
                <label className="gov-label" htmlFor="password" style={{ display: "block", fontSize: 13, fontWeight: 600, marginBottom: 6 }}>
                  Password <span className="gov-required" style={{ color: "#d9383a" }}>*</span>
                </label>
                <input
                  id="password"
                  className="gov-input"
                  type={showPassword ? "text" : "password"}
                  autoComplete="current-password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="Enter your password"
                  required
                  style={{ width: "100%", padding: "9px 12px", borderRadius: 6, border: "1px solid #ccc" }}
                />
              </div>

              <label style={{ fontSize: 13, display: "flex", gap: 8, marginTop: 8, alignItems: "center", color: "#555", cursor: "pointer" }}>
                <input
                  type="checkbox"
                  checked={showPassword}
                  onChange={(e) => setShowPassword(e.target.checked)}
                  style={{ accentColor: "#0b2545" }}
                />
                Show password
              </label>

              {error ? (
                <div className="gov-alert gov-alert-error" role="alert" style={{ marginTop: 16, padding: "10px 14px", background: "#fdf2f2", borderLeft: "4px solid #d9383a", borderRadius: 4, color: "#991b1b", fontSize: 13 }}>
                  {error}
                </div>
              ) : null}

              <button
                className="gov-btn"
                type="submit"
                disabled={loading}
                style={{ width: "100%", marginTop: 20, padding: "11px 20px", background: "#0b2545", color: "#fff", border: "none", borderRadius: 6, fontWeight: 600, cursor: "pointer" }}
              >
                {loading ? "Verifying Credentials…" : "Sign In to Portal"}
              </button>
            </form>

            <div style={{ marginTop: 16, textAlign: "center" }}>
              <Link className="gov-link" href="/forgot-password" style={{ fontSize: 13, color: "#0969da", textDecoration: "none" }}>
                Forgot password?
              </Link>
            </div>

            <div style={{ marginTop: 20, paddingTop: 16, borderTop: "1px solid #eee", fontSize: 12, color: "#777", textAlign: "center" }}>
              <span>🔒 Role-Based Access Control (RBAC) Enforced</span>
            </div>
          </div>
        </main>

        {/* Right: SIH DEMO ACCOUNTS — JURY ACCESS PANEL */}
        {isDemoMode ? (
          <section style={{ background: "#f8fafc", border: "1px solid #cbd5e1", borderRadius: 10, padding: 20, boxShadow: "0 4px 12px rgba(0,0,0,0.04)" }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 14, flexWrap: "wrap", gap: 8 }}>
              <div>
                <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                  <span style={{ background: "#dbeafe", color: "#1e40af", padding: "2px 8px", borderRadius: 4, fontSize: 11, fontWeight: 700, letterSpacing: "0.5px" }}>
                    SIH 2026 DEMO MODE
                  </span>
                  <h3 style={{ margin: 0, fontSize: 16, color: "#0f172a" }}>SIH DEMO ACCOUNTS — JURY ACCESS</h3>
                </div>
                <p style={{ margin: "4px 0 0", fontSize: 12, color: "#64748b" }}>
                  Select a role to populate its username, then enter the locally configured password.
                </p>
              </div>
            </div>

            {/* Department Group Cards */}
            <div style={{ display: "flex", flexDirection: "column", gap: 14, maxHeight: "560px", overflowY: "auto", paddingRight: 4 }}>
              {DEMO_ACCOUNTS_DATA.map((group) => (
                <div key={group.category} style={{ background: "#ffffff", border: "1px solid #e2e8f0", borderRadius: 8, padding: "12px 14px" }}>
                  <div style={{ fontSize: 13, fontWeight: 700, color: "#1e293b", marginBottom: 8, display: "flex", alignItems: "center", gap: 6 }}>
                    <span>{group.category}</span>
                  </div>
                  <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(210px, 1fr))", gap: 8 }}>
                    {group.accounts.map((acc) => (
                      <div
                        key={acc.username}
                        style={{
                          border: "1px solid #e2e8f0",
                          borderRadius: 6,
                          padding: "8px 10px",
                          background: "#fafafa",
                          display: "flex",
                          flexDirection: "column",
                          justifyContent: "space-between",
                        }}
                      >
                        <div>
                          <div style={{ fontWeight: 600, fontSize: 12, color: "#0b2545" }}>{acc.roleName}</div>
                          <div style={{ fontSize: 11, color: "#64748b", margin: "2px 0 6px" }}>{acc.desc}</div>
                          <div style={{ fontSize: 11, fontFamily: "monospace", background: "#f1f5f9", padding: "4px 6px", borderRadius: 4, marginBottom: 6 }}>
                            <div><strong>User:</strong> {acc.username}</div>
                          </div>
                        </div>
                        <button
                          type="button"
                          onClick={() => handleQuickFill(acc.username)}
                          style={{
                            background: "#0284c7",
                            color: "#fff",
                            border: "none",
                            borderRadius: 4,
                            padding: "4px 8px",
                            fontSize: 11,
                            fontWeight: 600,
                            cursor: "pointer",
                            textAlign: "center",
                            marginTop: 4,
                          }}
                        >
                          Use Username ➔
                        </button>
                      </div>
                    ))}
                  </div>
                </div>
              ))}
            </div>

            <div style={{ marginTop: 14, fontSize: 11, color: "#64748b", textAlign: "center", borderTop: "1px solid #e2e8f0", paddingTop: 10 }}>
              * Demo account passwords are configured locally and are not displayed here.
            </div>
          </section>
        ) : null}
      </div>
    </div>
  );
}

export default function LoginPage() {
  return (
    <Suspense fallback={<div className="gov-loading" style={{ padding: 40, textAlign: "center" }}>Loading Portal…</div>}>
      <LoginForm />
    </Suspense>
  );
}
