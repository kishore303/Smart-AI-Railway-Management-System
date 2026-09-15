"use client";

import React, { useState } from "react";
import ProtectedRoute from "@/components/ProtectedRoute";
import AppShell from "@/components/AppShell";
import Breadcrumbs from "@/components/Breadcrumbs";
import { useAuth } from "@/lib/auth-context";
import { api, ApiError } from "@/lib/api-client";

export default function ProfilePage() {
  return (
    <ProtectedRoute>
      <AppShell>
        <ProfileContent />
      </AppShell>
    </ProtectedRoute>
  );
}

function ProfileContent() {
  const { user, logout, refresh } = useAuth();
  const [name, setName] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [oldPassword, setOldPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [pwdLoading, setPwdLoading] = useState(false);
  const [pwdMessage, setPwdMessage] = useState<string | null>(null);
  const [pwdError, setPwdError] = useState<string | null>(null);

  async function onSaveProfile(e: React.FormEvent) {
    e.preventDefault();
    if (saving || name === null) return;
    setSaving(true);
    setMessage(null);
    setError(null);
    try {
      await api.put("/api/users/me", { name });
      await refresh();
      setMessage("Profile updated successfully.");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Unable to update profile.");
    } finally {
      setSaving(false);
    }
  }

  async function onChangePassword(e: React.FormEvent) {
    e.preventDefault();
    if (pwdLoading) return;
    setPwdMessage(null);
    setPwdError(null);
    if (newPassword.length < 8 || newPassword.length > 64) {
      setPwdError("New password must be between 8 and 64 characters.");
      return;
    }
    if (newPassword !== confirmPassword) {
      setPwdError("New password and confirmation do not match.");
      return;
    }
    setPwdLoading(true);
    try {
      const res = await api.post<{ message: string }>("/api/users/me/change-password", {
        old_password: oldPassword,
        new_password: newPassword,
      });
      setPwdMessage(res.message || "Password updated successfully. Please sign in with your new password.");
      setOldPassword("");
      setNewPassword("");
      setConfirmPassword("");
    } catch (err) {
      setPwdError(err instanceof ApiError ? err.message : "Unable to change password.");
    } finally {
      setPwdLoading(false);
    }
  }

  function handleSignOut() {
    logout();
  }

  return (
    <div className="gov-page">
      <Breadcrumbs trail={[{ label: "Dashboard", href: "/dashboard" }, { label: "Profile" }]} />

      <div className="gov-page-header">
        <div>
          <h1 className="gov-title">User Profile</h1>
          <p className="gov-sub">Manage your account settings</p>
        </div>
      </div>

      <div className="gov-card">
        <div className="gov-section-header">
          <h2>Account Information</h2>
        </div>
        <div className="gov-kv-grid">
          <span className="gov-kv-label">Name</span>
          <span className="gov-kv-value">{user?.name}</span>
          <span className="gov-kv-label">Email</span>
          <span className="gov-kv-value">{user?.email}</span>
          <span className="gov-kv-label">Department</span>
          <span className="gov-kv-value">{user?.department}</span>
          <span className="gov-kv-label">Role</span>
          <span className="gov-kv-value">
            <span className={`gov-badge gov-badge-${user?.role === "AUTHORIZED_OFFICIAL" ? "navy" : user?.role === "ENGINEER_REVIEWER" ? "blue" : user?.role === "CONTROLLER" ? "amber" : "muted"}`}>
              {user?.role}
            </span>
          </span>
        </div>
      </div>

      <div className="gov-card">
        <div className="gov-section-header">
          <h2>Update Name</h2>
        </div>
        <form onSubmit={onSaveProfile}>
          <label className="gov-label" htmlFor="profile-name">
            Display Name <span className="gov-required">*</span>
          </label>
          <input
            id="profile-name"
            className="gov-input"
            defaultValue={user?.name ?? ""}
            onChange={(e) => setName(e.target.value)}
            minLength={2}
            maxLength={150}
          />
          {message ? <div className="gov-alert gov-alert-success" role="status" style={{ marginTop: 12 }}>{message}</div> : null}
          {error ? <div className="gov-alert gov-alert-error" role="alert" style={{ marginTop: 12 }}>{error}</div> : null}
          <div className="gov-btn-group">
            <button className="gov-btn" type="submit" disabled={saving || name === null}>
              {saving ? "Saving…" : "Save Profile"}
            </button>
          </div>
        </form>
      </div>

      <div className="gov-card">
        <div className="gov-section-header">
          <h2>Change Password</h2>
        </div>
        <div className="gov-info-box">
          After changing your password you will need to sign in again with the new password.
        </div>
        <form onSubmit={onChangePassword}>
          <div className="gov-form-grid">
            <div>
              <label className="gov-label" htmlFor="old-password">
                Current Password <span className="gov-required">*</span>
              </label>
              <input
                id="old-password"
                className="gov-input"
                type="password"
                autoComplete="current-password"
                value={oldPassword}
                onChange={(e) => setOldPassword(e.target.value)}
                required
              />
            </div>
            <div />
            <div>
              <label className="gov-label" htmlFor="new-password">
                New Password <span className="gov-required">*</span>
              </label>
              <input
                id="new-password"
                className="gov-input"
                type="password"
                autoComplete="new-password"
                value={newPassword}
                onChange={(e) => setNewPassword(e.target.value)}
                required
              />
              <span className="gov-hint">8 to 64 characters</span>
            </div>
            <div>
              <label className="gov-label" htmlFor="confirm-password">
                Confirm New Password <span className="gov-required">*</span>
              </label>
              <input
                id="confirm-password"
                className="gov-input"
                type="password"
                autoComplete="new-password"
                value={confirmPassword}
                onChange={(e) => setConfirmPassword(e.target.value)}
                required
              />
            </div>
          </div>
          {pwdMessage ? <div className="gov-alert gov-alert-success" role="status" style={{ marginTop: 12 }}>{pwdMessage}</div> : null}
          {pwdError ? <div className="gov-alert gov-alert-error" role="alert" style={{ marginTop: 12 }}>{pwdError}</div> : null}
          <div className="gov-btn-group">
            <button className="gov-btn" type="submit" disabled={pwdLoading}>
              {pwdLoading ? "Updating…" : "Change Password"}
            </button>
          </div>
        </form>
      </div>

      <div className="gov-card">
        <div className="gov-section-header">
          <h2>Session</h2>
        </div>
        <div className="gov-btn-group">
          <button className="gov-btn gov-btn-danger" type="button" onClick={handleSignOut}>
            Sign Out
          </button>
        </div>
      </div>
    </div>
  );
}
