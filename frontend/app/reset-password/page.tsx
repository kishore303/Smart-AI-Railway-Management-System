"use client";

import React, { Suspense, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import GovHeader from "@/components/GovHeader";
import Breadcrumbs from "@/components/Breadcrumbs";
import { api, ApiError } from "@/lib/api-client";

function ResetForm() {
  const params = useSearchParams();
  const initialToken = params.get("token") ?? "";
  const [token, setToken] = useState(initialToken);
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (loading) return;
    setError(null);
    setSuccess(null);
    if (password.length < 8 || password.length > 64) {
      setError("Password must be between 8 and 64 characters.");
      return;
    }
    if (password !== confirm) {
      setError("Passwords do not match.");
      return;
    }
    if (!token.trim()) {
      setError("Reset token is missing.");
      return;
    }
    setLoading(true);
    try {
      const res = await api.post<{ message: string }>("/api/auth/reset-password", {
        token: token.trim(),
        new_password: password,
      });
      setSuccess(res.message || "Password has been reset successfully.");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Unable to connect to the railway service. Please try again.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="gov-card">
      <h2 style={{ margin: 0, fontSize: 18 }}>Reset Password</h2>
      <form onSubmit={onSubmit}>
        <label className="gov-label" htmlFor="token">Reset Token</label>
        <input id="token" className="gov-input" value={token} onChange={(e) => setToken(e.target.value)} required />
        <label className="gov-label" htmlFor="new-password">New Password</label>
        <input
          id="new-password"
          className="gov-input"
          type="password"
          autoComplete="new-password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          required
        />
        <label className="gov-label" htmlFor="confirm-password">Confirm Password</label>
        <input
          id="confirm-password"
          className="gov-input"
          type="password"
          autoComplete="new-password"
          value={confirm}
          onChange={(e) => setConfirm(e.target.value)}
          required
        />
        {error ? <div className="gov-alert gov-alert-error" role="alert">{error}</div> : null}
        {success ? <div className="gov-alert gov-alert-success" role="status">{success}</div> : null}
        <button className="gov-btn" type="submit" disabled={loading}>
          {loading ? "Submitting…" : "Reset Password"}
        </button>
      </form>
      <p style={{ marginTop: 12 }}>
        <Link className="gov-link" href="/login">Back to login</Link>
      </p>
    </div>
  );
}

export default function ResetPasswordPage() {
  return (
    <>
      <GovHeader />
      <main className="gov-wrap">
        <Breadcrumbs trail={[{ label: "Home", href: "/" }, { label: "Login", href: "/login" }, { label: "Reset Password" }]} />
        <Suspense fallback={<div className="gov-card">Loading…</div>}>
          <ResetForm />
        </Suspense>
      </main>
    </>
  );
}
