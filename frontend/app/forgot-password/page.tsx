"use client";

import React, { useState } from "react";
import Link from "next/link";
import GovHeader from "@/components/GovHeader";
import Breadcrumbs from "@/components/Breadcrumbs";
import { api, ApiError } from "@/lib/api-client";
import type { ForgotPasswordResponse } from "@/types/auth";

export default function ForgotPasswordPage() {
  const [email, setEmail] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (loading) return;
    setError(null);
    setSuccess(null);
    setLoading(true);
    try {
      const res = await api.post<ForgotPasswordResponse>("/api/auth/forgot-password", { email: email.trim() });
      setSuccess(res.message || "If the email exists, a reset link has been sent.");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Unable to connect to the railway service. Please try again.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <>
      <GovHeader />
      <main className="gov-wrap">
        <Breadcrumbs trail={[{ label: "Home", href: "/" }, { label: "Login", href: "/login" }, { label: "Forgot Password" }]} />
        <div className="gov-card">
          <h2 style={{ margin: 0, fontSize: 18 }}>Forgot Password</h2>
          <p style={{ fontSize: 13, color: "#64748b" }}>Enter your registered email. Password reset remains handled by the backend.</p>
          <form onSubmit={onSubmit}>
            <label className="gov-label" htmlFor="email">Registered Email</label>
            <input
              id="email"
              className="gov-input"
              type="email"
              autoComplete="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
            />
            {error ? <div className="gov-alert gov-alert-error" role="alert">{error}</div> : null}
            {success ? <div className="gov-alert gov-alert-success" role="status">{success}</div> : null}
            <button className="gov-btn" type="submit" disabled={loading}>
              {loading ? "Submitting…" : "Submit"}
            </button>
          </form>
          <p style={{ marginTop: 12 }}>
            <Link className="gov-link" href="/login">Back to login</Link>
          </p>
        </div>
      </main>
    </>
  );
}
