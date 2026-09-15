"use client";

import React from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useAuth } from "@/lib/auth-context";
import { useNotifications } from "@/lib/notifications-context";

interface NavItem {
  label: string;
  href: string;
  icon: string;
}

interface NavSection {
  title: string;
  items: NavItem[];
}

const SECTIONS: NavSection[] = [
  {
    title: "Overview",
    items: [{ label: "Dashboard", href: "/dashboard", icon: "📊" }],
  },
  {
    title: "Maintenance",
    items: [
      { label: "Maintenance Requests", href: "/maintenance", icon: "🔧" },
      { label: "Review & Verification", href: "/review", icon: "📋" },
    ],
  },
  {
    title: "Decision Support",
    items: [
      { label: "ML Predictions", href: "/ml", icon: "🤖" },
      { label: "Safety", href: "/safety", icon: "🛡" },
      { label: "Recommendations", href: "/recommendations", icon: "✅" },
    ],
  },
  {
    title: "Block Planning",
    items: [
      { label: "Block Planning", href: "/blocks", icon: "🏗" },
      { label: "Cross-Department Integration", href: "/integration", icon: "🔗" },
      { label: "Block Execution", href: "/execution", icon: "⚡" },
      { label: "Resources", href: "/resources", icon: "📦" },
    ],
  },
  {
    title: "Monitoring",
    items: [
      { label: "Notifications", href: "/notifications", icon: "🔔" },
      { label: "Railway Map", href: "/map", icon: "🗺" },
    ],
  },
  {
    title: "Simulation",
    items: [
      { label: "Digital Twin", href: "/digital-twin", icon: "🔮" },
      { label: "What-If Simulation", href: "/what-if", icon: "🧪" },
    ],
  },
  {
    title: "Emergency",
    items: [
      { label: "Emergency Dashboard", href: "/emergency", icon: "🚨" },
      { label: "Emergency Incidents", href: "/emergency/incidents", icon: "⚠" },
    ],
  },
  {
    title: "Account",
    items: [
      { label: "Profile", href: "/profile", icon: "👤" },
    ],
  },
];

// Demo/development visibility: the sidebar lists EVERY implemented module.
// Each role's authorized subset below drives only the subtle lock indicator —
// navigation itself is never blocked here. The backend remains authoritative
// and rejects any operation the role may not perform.
export const ROLE_VISIBLE: Record<string, string[]> = {
  MAINTENANCE_STAFF: ["Dashboard", "Maintenance Requests", "Railway Map", "Notifications", "Profile"],
  ENGINEER_REVIEWER: ["Dashboard", "Maintenance Requests", "Review & Verification", "ML Predictions", "Safety", "Block Execution", "Resources", "Digital Twin", "What-If Simulation", "Notifications", "Profile"],
  OPERATOR: ["Dashboard", "Block Planning", "ML Predictions", "Block Execution", "Resources", "Digital Twin", "What-If Simulation", "Notifications", "Profile"],
  CONTROLLER: ["Dashboard", "Block Planning", "ML Predictions", "Block Execution", "Resources", "Cross-Department Integration", "Digital Twin", "What-If Simulation", "Notifications", "Profile"],
  AUTHORIZED_OFFICIAL: ["Dashboard", "Recommendations", "ML Predictions", "Safety", "Block Execution", "Resources", "Digital Twin", "What-If Simulation", "Notifications", "Profile"],
  EMERGENCY_OPERATOR: ["Dashboard", "Emergency Dashboard", "Emergency Incidents", "Railway Map", "Notifications", "Profile"],
};

export default function Sidebar({ open, onClose }: { open: boolean; onClose: () => void }) {
  const pathname = usePathname();
  const { user } = useAuth();
  const allowed = user ? ROLE_VISIBLE[user.role] : undefined;
  const { unread } = useNotifications();

  return (
    <>
      <aside className={`gov-sidebar${open ? " open" : ""}`} aria-label="Primary navigation">
        {SECTIONS.map((s) => (
          <div key={s.title} className={`gov-side-section${s.title === "Account" ? " gov-side-section-account" : ""}`}>
            <div className="gov-side-section-title">{s.title}</div>
            <ul>
              {s.items.map((i) => {
                const isActive = pathname === i.href || pathname.startsWith(i.href + "/");
                // Demo mode: every module stays visible. Items outside the
                // role's authorized set carry a subtle lock marker only —
                // the backend still enforces the real permission.
                const locked = allowed ? !allowed.includes(i.label) : false;
                return (
                  <li key={i.href}>
                    <Link
                      href={i.href}
                      onClick={onClose}
                      className={`${isActive ? "active" : ""}${locked ? " restricted" : ""}`}
                      aria-current={isActive ? "page" : undefined}
                      aria-label={locked ? `${i.label} (restricted for your role)` : i.label}
                    >
                      <span className="gov-side-icon" aria-hidden="true">{i.icon}</span>
                      {i.label}
                      {locked ? (
                        <span className="gov-side-lock" aria-hidden="true" title="Restricted for your role">🔒</span>
                      ) : null}
                      {i.label === "Notifications" && unread != null && unread > 0 ? (
                        <span className="badge badge-red" style={{ marginLeft: locked ? 0 : "auto", fontSize: "10px", padding: "1px 7px" }}>
                          {unread}
                        </span>
                      ) : null}
                    </Link>
                  </li>
                );
              })}
            </ul>
          </div>
        ))}
        <p className="gov-side-note">Demo mode: all modules visible. Access control enforced by backend.</p>
      </aside>
      {open ? <button className="gov-scrim" aria-label="Close menu" onClick={onClose} /> : null}
    </>
  );
}
