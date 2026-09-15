"use client";

import React, { useState } from "react";
import { useRouter } from "next/navigation";
import GovHeader from "@/components/GovHeader";
import Sidebar from "@/components/Sidebar";
import { useAuth } from "@/lib/auth-context";

export default function AppShell({ children }: { children: React.ReactNode }) {
  const { user, logout } = useAuth();
  const router = useRouter();
  const [open, setOpen] = useState(false);

  function onLogout() {
    logout();
    router.replace("/login");
  }

  const roleLabel = user?.role?.replace(/_/g, " ") ?? "";
  const deptLabel = user?.department ?? "";

  return (
    <>
      <GovHeader
        userLine={user ? `${user.name}` : undefined}
      />
      <div className="gov-subbar">
        <button className="gov-menu-btn" type="button" onClick={() => setOpen((v) => !v)} aria-label="Toggle navigation">
          ☰ Menu
        </button>
        <span className="gov-subbar-user">
          {user ? (
            <>
              {user.name}
              <span style={{ fontWeight: 400, color: "var(--muted)", marginLeft: 8, fontSize: 12 }}>
                {roleLabel} — {deptLabel}
              </span>
            </>
          ) : ""}
        </span>
        <span className="gov-subbar-actions">
          <button className="gov-link-btn" type="button" onClick={() => router.push("/profile")}>
            Profile
          </button>
          <button className="gov-link-btn" type="button" onClick={onLogout} style={{ color: "var(--red)" }}>
            Logout
          </button>
        </span>
      </div>
      <div className="gov-layout">
        <Sidebar open={open} onClose={() => setOpen(false)} />
        <main className="gov-main">{children}</main>
      </div>
    </>
  );
}
