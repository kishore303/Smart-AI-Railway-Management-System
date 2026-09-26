"use client";

import React, { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import ProtectedRoute from "@/components/ProtectedRoute";
import AppShell from "@/components/AppShell";
import Breadcrumbs from "@/components/Breadcrumbs";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE || "http://localhost:8000";

export default function DigitalTwinPage() {
  return (
    <ProtectedRoute>
      <AppShell>
        <TwinContent />
      </AppShell>
    </ProtectedRoute>
  );
}

function TwinContent() {
  const [twinState, setTwinState] = useState<any | null>(null);
  const [timeline, setTimeline] = useState<any | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const token = typeof window !== "undefined" ? localStorage.getItem("token") : null;

  const loadData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const headers: Record<string, string> = {};
      if (token) headers["Authorization"] = `Bearer ${token}`;

      const [stateRes, timelineRes] = await Promise.all([
        fetch(`${API_BASE}/api/simulation/digital-twin/state`, { headers }),
        fetch(`${API_BASE}/api/simulation/digital-twin/timeline`, { headers }),
      ]);

      if (stateRes.ok) setTwinState(await stateRes.json());
      if (timelineRes.ok) setTimeline(await timelineRes.json());
    } catch (err: any) {
      setError(err.message || "Unable to connect to Digital Twin service.");
    } finally {
      setLoading(false);
    }
  }, [token]);

  useEffect(() => {
    void loadData();
    const interval = setInterval(loadData, 30000); // 30s auto-refresh
    return () => clearInterval(interval);
  }, [loadData]);

  return (
    <div className="gov-page">
      <Breadcrumbs trail={[{ label: "Dashboard", href: "/dashboard" }, { label: "Digital Twin Telemetry" }]} />

      <div className="gov-page-header flex flex-col md:flex-row justify-between items-start md:items-center gap-4">
        <div>
          <div className="flex items-center gap-3">
            <span className="text-2xl">🌐</span>
            <h2 className="gov-title">Corridor Digital Twin &amp; Live Telemetry</h2>
          </div>
          <p className="gov-sub">
            Real-time synchronization of physical track assets, section speed restrictions, scheduled maintenance blocks, and timetable train occupancy.
          </p>
        </div>
        <div className="flex items-center gap-3">
          <span className="flex items-center gap-2 px-3 py-1.5 bg-emerald-950 border border-emerald-800 text-emerald-400 text-xs font-bold rounded-full">
            <span className="w-2 h-2 rounded-full bg-emerald-400 animate-ping"></span>
            ONLINE SYNCED
          </span>
          <button className="gov-btn gov-btn-secondary text-xs" onClick={() => void loadData()}>
            🔄 Refresh
          </button>
        </div>
      </div>

      {loading && !twinState ? (
        <div className="gov-card"><div className="gov-loading">Loading Digital Twin graph state…</div></div>
      ) : error ? (
        <div className="gov-alert gov-alert-error">{error}</div>
      ) : (
        <div className="space-y-6">
          {/* Key Infrastructure Metrics */}
          <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-3">
            <div className="bg-slate-900 border border-slate-800 p-4 rounded-xl text-center">
              <div className="text-xs text-slate-400 font-semibold uppercase">Sections</div>
              <div className="text-2xl font-bold text-white mt-1">{twinState?.counts?.sections ?? 0}</div>
            </div>
            <div className="bg-slate-900 border border-slate-800 p-4 rounded-xl text-center">
              <div className="text-xs text-slate-400 font-semibold uppercase">Tracks</div>
              <div className="text-2xl font-bold text-white mt-1">{twinState?.counts?.tracks ?? 0}</div>
            </div>
            <div className="bg-slate-900 border border-slate-800 p-4 rounded-xl text-center">
              <div className="text-xs text-slate-400 font-semibold uppercase">Stations</div>
              <div className="text-2xl font-bold text-white mt-1">{twinState?.counts?.stations ?? 0}</div>
            </div>
            <div className="bg-slate-900 border border-slate-800 p-4 rounded-xl text-center">
              <div className="text-xs text-slate-400 font-semibold uppercase">Track Assets</div>
              <div className="text-2xl font-bold text-emerald-400 mt-1">{twinState?.counts?.assets ?? 0}</div>
            </div>
            <div className="bg-slate-900 border border-slate-800 p-4 rounded-xl text-center">
              <div className="text-xs text-slate-400 font-semibold uppercase">Active Blocks</div>
              <div className="text-2xl font-bold text-blue-400 mt-1">{twinState?.counts?.optimized_blocks ?? 0}</div>
            </div>
            <div className="bg-slate-900 border border-slate-800 p-4 rounded-xl text-center">
              <div className="text-xs text-slate-400 font-semibold uppercase">Timetable Trains</div>
              <div className="text-2xl font-bold text-amber-400 mt-1">{twinState?.counts?.trains ?? 0}</div>
            </div>
          </div>

          {/* 24-Hour Corridor Timeline */}
          <div className="gov-card">
            <div className="gov-section-header flex justify-between items-center">
              <h3>24-Hour Corridor Occupancy &amp; Block Windows</h3>
              <span className="text-xs text-slate-400">{timeline?.total_events ?? 0} events scheduled</span>
            </div>

            {timeline?.events?.length === 0 ? (
              <div className="gov-info-box">No maintenance windows scheduled on the corridor in the next 24 hours.</div>
            ) : (
              <div className="space-y-3 mt-4">
                {timeline?.events?.map((ev: any) => (
                  <div key={ev.id} className="bg-slate-950 border border-slate-800 p-4 rounded-lg flex flex-col md:flex-row md:items-center justify-between gap-3">
                    <div className="flex items-center gap-3">
                      <span className="text-lg">🧱</span>
                      <div>
                        <div className="font-semibold text-white text-sm">{ev.title}</div>
                        <div className="text-xs text-slate-400">Section: {ev.section_code} | Status: <span className="text-blue-400">{ev.status}</span></div>
                      </div>
                    </div>

                    <div className="flex items-center gap-3">
                      <span className="text-xs font-mono text-slate-300 bg-slate-900 px-3 py-1 rounded border border-slate-800">
                        {ev.start ? new Date(ev.start).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }) : "—"} →{" "}
                        {ev.end ? new Date(ev.end).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }) : "—"}
                      </span>
                      <span className={`gov-badge ${ev.status === "ACTIVE" ? "gov-badge-green" : "gov-badge-blue"}`}>
                        {ev.status}
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Monitored Sections Status */}
          <div className="gov-card">
            <div className="gov-section-header">
              <h3>Monitored Railway Sections</h3>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 mt-3">
              {twinState?.monitored_sections?.map((sec: any) => (
                <div key={sec.id} className="bg-slate-950 border border-slate-800 p-4 rounded-lg">
                  <div className="flex justify-between items-center">
                    <span className="font-mono text-xs font-bold text-blue-400">{sec.section_code}</span>
                    <span className="text-xs px-2 py-0.5 bg-emerald-950 text-emerald-400 border border-emerald-800 rounded">
                      {sec.health_status}
                    </span>
                  </div>
                  <div className="text-sm font-semibold text-white mt-1">{sec.section_name}</div>
                  <div className="text-xs text-slate-400 mt-2 flex justify-between">
                    <span>Speed Limit: {sec.speed_limit_kmph} km/h</span>
                    <span>Length: {sec.length_km} km</span>
                  </div>
                </div>
              ))}
            </div>
            <div className="gov-info-box mt-4 text-xs">
              {twinState?.disclaimer}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
