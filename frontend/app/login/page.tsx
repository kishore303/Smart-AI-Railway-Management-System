"use client";

import React, { Suspense, useState } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useAuth } from "@/lib/auth-context";
import { ApiError } from "@/lib/api-client";

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

  return (
    <>
      <div className="login-shell">
        <div className="login-brand">
          <div className="gov-header-emblem" aria-hidden="true">IR</div>
          <div>
            <h1>Indian Railways — Block Planning Portal</h1>
            <p className="brand-sub">AI-Powered Maintenance Decision Support System</p>
          </div>
          <ul aria-label="Portal capabilities">
            <li>Maintenance demand &amp; block planning workflow</li>
            <li>Safety-validated, officially approved decisions</li>
            <li>Cross-department coordination &amp; audit trail</li>
          </ul>
        </div>
        <main className="login-panel">
          <div className="login-card">
            <h2>Railway Official Login</h2>
            <p className="login-lead">Sign in to the Block Planning Portal</p>

            <form onSubmit={onSubmit}>
              <label className="gov-label" htmlFor="username">
                Username or Email <span className="gov-required">*</span>
              </label>
              <input
                id="username"
                className="gov-input"
                autoComplete="username"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                placeholder="Enter your username or email"
                required
              />
              <label className="gov-label" htmlFor="password">
                Password <span className="gov-required">*</span>
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
              />
              <label style={{ fontSize: 13, display: "flex", gap: 8, marginTop: 10, alignItems: "center", color: "var(--text-secondary)", cursor: "pointer" }}>
                <input
                  type="checkbox"
                  checked={showPassword}
                  onChange={(e) => setShowPassword(e.target.checked)}
                  style={{ accentColor: "var(--navy)" }}
                />
                Show password
              </label>
              {error ? (
                <div className="gov-alert gov-alert-error" role="alert" style={{ marginTop: 16 }}>
                  {error}
                </div>
              ) : null}
              <button
                className="gov-btn"
                type="submit"
                disabled={loading}
                style={{ width: "100%", marginTop: 20, padding: "11px 20px" }}
              >
                {loading ? "Signing in…" : "Sign In"}
              </button>
            </form>

            <div style={{ marginTop: 16, textAlign: "center" }}>
              <Link className="gov-link" href="/forgot-password" style={{ fontSize: 13 }}>
                Forgot password?
              </Link>
            </div>

            <p className="login-disclaimer">
              Authorized personnel only. All access is logged and audited.
              Session credentials must not be shared.
            </p>
          </div>
        </main>
      </div>
    </>
  );
}

export default function LoginPage() {
  return (
    <Suspense fallback={<div className="gov-loading">Loading…</div>}>
      <LoginForm />
    </Suspense>
  );
}
