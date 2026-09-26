"use client";

import React, { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import ProtectedRoute from "@/components/ProtectedRoute";
import AppShell from "@/components/AppShell";
import Breadcrumbs from "@/components/Breadcrumbs";
import { api, ApiError } from "@/lib/api-client";
import type { IntegrationListResponse, IntegrationRequest, OpportunityDetectResponse } from "@/types/integration";
import { compatibilityNote, integrationBadgeKind } from "@/types/integration";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE || "http://localhost:8000";
const STATUSES = ["", "PENDING", "ACCEPTED", "REJECTED", "MODIFIED"];

export default function IntegrationListPage() {
  return (
    <ProtectedRoute>
      <AppShell>
        <ListContent />
      </AppShell>
    </ProtectedRoute>
  );
}

function ListContent() {
  const [activeTab, setActiveTab] = useState<"opportunities" | "marketplace" | "resources">("marketplace");
  const [data, setData] = useState<IntegrationListResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [status, setStatus] = useState("");
  const [sectionFilter, setSectionFilter] = useState("");

  const [srcBlock, setSrcBlock] = useState("");
  const [tgtBlock, setTgtBlock] = useState("");
  const [reason, setReason] = useState("");
  const [creating, setCreating] = useState(false);
  const [createError, setCreateError] = useState<string | null>(null);
  const [detecting, setDetecting] = useState(false);
  const [detectMsg, setDetectMsg] = useState<string | null>(null);

  // Marketplace states
  const [marketplaceBlocks, setMarketplaceBlocks] = useState<any[]>([]);
  const [marketplaceLoading, setMarketplaceLoading] = useState(false);
  const [joinModalBlock, setJoinModalBlock] = useState<any | null>(null);
  const [joinDept, setJoinDept] = useState("2");
  const [joinWorkType, setJoinWorkType] = useState("OHE Inspection & Catenary Maintenance");
  const [joinSubmitting, setJoinSubmitting] = useState(false);
  const [joinSuccess, setJoinSuccess] = useState<string | null>(null);

  // Resources Timeline states
  const [resourceTimeline, setResourceTimeline] = useState<any[]>([]);
  const [resourcesLoading, setResourcesLoading] = useState(false);

  const token = typeof window !== "undefined" ? localStorage.getItem("token") : null;

  const loadOpportunities = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const params = new URLSearchParams({ skip: "0", limit: "50" });
      if (status) params.set("status", status);
      if (sectionFilter) params.set("section_id", sectionFilter);
      const res = await api.get<IntegrationListResponse>(`/api/integration/opportunities?${params.toString()}`);
      setData(res);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Unable to load coordination opportunities.");
    } finally {
      setLoading(false);
    }
  }, [status, sectionFilter]);

  const loadMarketplace = useCallback(async () => {
    setMarketplaceLoading(true);
    try {
      const res = await fetch(`${API_BASE}/api/marketplace/blocks`, {
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      });
      if (res.ok) {
        const json = await res.json();
        setMarketplaceBlocks(json.marketplace_blocks || []);
      }
    } catch (err) {
      console.error(err);
    } finally {
      setMarketplaceLoading(false);
    }
  }, [token]);

  const loadResourceTimeline = useCallback(async () => {
    setResourcesLoading(true);
    try {
      const res = await fetch(`${API_BASE}/api/marketplace/resources/timeline`, {
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      });
      if (res.ok) {
        const json = await res.json();
        setResourceTimeline(json.timeline || []);
      }
    } catch (err) {
      console.error(err);
    } finally {
      setResourcesLoading(false);
    }
  }, [token]);

  useEffect(() => {
    if (activeTab === "opportunities") {
      void loadOpportunities();
    } else if (activeTab === "marketplace") {
      void loadMarketplace();
    } else if (activeTab === "resources") {
      void loadResourceTimeline();
    }
  }, [activeTab, loadOpportunities, loadMarketplace, loadResourceTimeline]);

  async function onDetect() {
    if (detecting) return;
    setDetecting(true);
    setDetectMsg(null);
    try {
      const payload: Record<string, unknown> = {};
      if (sectionFilter) payload.section_id = Number(sectionFilter);
      const res = await api.post<OpportunityDetectResponse>("/api/integration/detect", payload);
      setDetectMsg(`Auto-scan complete: ${res.detected_count} potential opportunities identified.`);
      await loadOpportunities();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Opportunity detection failed.");
    } finally {
      setDetecting(false);
    }
  }

  async function onCreate(e: React.FormEvent) {
    e.preventDefault();
    if (creating) return;
    setCreateError(null);
    if (!srcBlock || !tgtBlock) {
      setCreateError("Source and target block IDs are required.");
      return;
    }
    if (srcBlock === tgtBlock) {
      setCreateError("Source and target blocks must differ.");
      return;
    }
    setCreating(true);
    try {
      const payload: Record<string, unknown> = {
        source_block_id: Number(srcBlock),
        target_block_id: Number(tgtBlock),
      };
      if (reason.trim() !== "") payload.reason = reason.trim().slice(0, 1000);
      await api.post<IntegrationRequest>("/api/integration/requests", payload);
      setSrcBlock("");
      setTgtBlock("");
      setReason("");
      await loadOpportunities();
    } catch (err) {
      setCreateError(err instanceof ApiError ? err.message : "Unable to submit coordination.");
    } finally {
      setCreating(false);
    }
  }

  async function onJoinBlockSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!joinModalBlock || joinSubmitting) return;
    setJoinSubmitting(true);
    setJoinSuccess(null);
    try {
      const res = await fetch(`${API_BASE}/api/marketplace/join`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: JSON.stringify({
          target_block_id: joinModalBlock.id,
          requesting_department_id: Number(joinDept),
          work_type: joinWorkType,
          remarks: "Joined via Block Marketplace",
          estimated_duration_mins: 60,
        }),
      });

      if (!res.ok) {
        const errJson = await res.json();
        throw new Error(errJson.detail || "Failed to join block");
      }

      const resJson = await res.json();
      setJoinSuccess(`Request submitted successfully for ${joinModalBlock.block_code}! Integration ID: #${resJson.integration_request_id}`);
      setTimeout(() => {
        setJoinModalBlock(null);
        setJoinSuccess(null);
        loadMarketplace();
      }, 2000);
    } catch (err: any) {
      alert(`Error joining block: ${err.message}`);
    } finally {
      setJoinSubmitting(false);
    }
  }

  return (
    <div className="gov-page">
      <Breadcrumbs trail={[{ label: "Dashboard", href: "/dashboard" }, { label: "Cross-Department Coordination & Marketplace" }]} />

      <div className="gov-page-header">
        <div>
          <h2 className="gov-title">Cross-Department Coordination &amp; Block Marketplace</h2>
          <p className="gov-sub">
            Maximize corridor utility through joint possession windows, multi-department co-utilization, and shared machinery scheduling across Engineering, Electrical/OHE, and S&amp;T.
          </p>
        </div>
      </div>

      {/* Tabs */}
      <div className="flex gap-2 border-b border-slate-700 pb-3 mb-6">
        <button
          onClick={() => setActiveTab("marketplace")}
          className={`px-4 py-2 rounded-lg text-sm font-semibold transition ${
            activeTab === "marketplace" ? "bg-blue-600 text-white shadow" : "bg-slate-800 text-slate-300 hover:bg-slate-700"
          }`}
        >
          🏪 Block Marketplace ({marketplaceBlocks.length})
        </button>
        <button
          onClick={() => setActiveTab("resources")}
          className={`px-4 py-2 rounded-lg text-sm font-semibold transition ${
            activeTab === "resources" ? "bg-blue-600 text-white shadow" : "bg-slate-800 text-slate-300 hover:bg-slate-700"
          }`}
        >
          🚜 Machinery &amp; Equipment Timeline
        </button>
        <button
          onClick={() => setActiveTab("opportunities")}
          className={`px-4 py-2 rounded-lg text-sm font-semibold transition ${
            activeTab === "opportunities" ? "bg-blue-600 text-white shadow" : "bg-slate-800 text-slate-300 hover:bg-slate-700"
          }`}
        >
          🤝 Coordination Detector &amp; Requests ({data?.total || 0})
        </button>
      </div>

      {/* TAB 1: BLOCK MARKETPLACE */}
      {activeTab === "marketplace" && (
        <div className="space-y-6">
          <div className="gov-card">
            <div className="gov-section-header">
              <h3>Corridor Windows Open for Co-Utilization</h3>
            </div>
            <p className="text-sm text-slate-400 mb-4">
              Approved and scheduled maintenance blocks with spare track possession capacity. Departments can request joint execution to carry out parallel OHE/Signal/Track work without requesting extra corridor closures.
            </p>

            {marketplaceLoading ? (
              <div className="gov-loading">Loading marketplace blocks…</div>
            ) : marketplaceBlocks.length === 0 ? (
              <div className="gov-empty">
                <div className="gov-empty-icon">🏪</div>
                <p>No open blocks in marketplace at this moment.</p>
              </div>
            ) : (
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                {marketplaceBlocks.map((b) => (
                  <div key={b.id} className="bg-slate-900 border border-slate-800 p-5 rounded-xl flex flex-col justify-between">
                    <div>
                      <div className="flex items-center justify-between">
                        <span className="font-mono text-xs font-bold text-blue-400">{b.block_code}</span>
                        <span className="px-2 py-0.5 bg-emerald-950 border border-emerald-800 text-emerald-300 text-xs font-bold rounded">
                          {b.available_slots} Slots Available
                        </span>
                      </div>
                      <div className="text-sm font-semibold text-white mt-2">
                        {b.section_name} ({b.section_code})
                      </div>
                      <div className="text-xs text-slate-400 mt-1">
                        Track: {b.track_code} | Primary Dept: <span className="text-blue-300 font-semibold">{b.primary_department_name}</span>
                      </div>
                      <div className="bg-slate-950 p-3 rounded-lg border border-slate-800/80 mt-3 text-xs text-slate-300 space-y-1">
                        <div>
                          ⏰ {b.start_time ? new Date(b.start_time).toLocaleString([], { dateStyle: "short", timeStyle: "short" }) : "—"}
                        </div>
                        <div>⏱️ Duration: {b.duration_mins} mins</div>
                        <div className="text-emerald-400 font-semibold">
                          ⭐ Solver Optimization Score: {b.optimization_score ?? 90}
                        </div>
                      </div>
                    </div>

                    <div className="mt-4 pt-4 border-t border-slate-800 flex items-center justify-between">
                      <span className="text-xs text-slate-400">{b.participating_departments_count} Depts Active</span>
                      <button
                        onClick={() => setJoinModalBlock(b)}
                        className="px-3 py-1.5 bg-blue-600 hover:bg-blue-500 text-white rounded text-xs font-semibold transition"
                      >
                        ➕ Request to Join Block
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Join Modal */}
          {joinModalBlock && (
            <div className="fixed inset-0 bg-black/70 backdrop-blur-sm flex items-center justify-center p-4 z-50">
              <div className="bg-slate-900 border border-slate-700 rounded-xl p-6 max-w-lg w-full">
                <div className="flex items-center justify-between pb-3 border-b border-slate-800">
                  <h3 className="text-base font-bold text-white">Join Block Window: {joinModalBlock.block_code}</h3>
                  <button onClick={() => setJoinModalBlock(null)} className="text-slate-400 hover:text-white">✕</button>
                </div>

                <form onSubmit={onJoinBlockSubmit} className="space-y-4 mt-4">
                  <div>
                    <label className="gov-label">Your Department</label>
                    <select
                      className="gov-input"
                      value={joinDept}
                      onChange={(e) => setJoinDept(e.target.value)}
                    >
                      <option value="2">Electrical / Traction Power (ELEC)</option>
                      <option value="3">Signal &amp; Telecommunication (SNT)</option>
                      <option value="1">Engineering / Permanent Way (ENG)</option>
                    </select>
                  </div>

                  <div>
                    <label className="gov-label">Proposed Maintenance Work</label>
                    <input
                      className="gov-input"
                      value={joinWorkType}
                      onChange={(e) => setJoinWorkType(e.target.value)}
                      placeholder="e.g. OHE neutral section inspection"
                      required
                    />
                  </div>

                  {joinSuccess && (
                    <div className="gov-alert gov-alert-success">{joinSuccess}</div>
                  )}

                  <div className="flex justify-end gap-2 pt-3 border-t border-slate-800">
                    <button
                      type="button"
                      onClick={() => setJoinModalBlock(null)}
                      className="gov-btn gov-btn-secondary"
                    >
                      Cancel
                    </button>
                    <button
                      type="submit"
                      disabled={joinSubmitting}
                      className="gov-btn gov-btn-primary"
                    >
                      {joinSubmitting ? "Submitting…" : "Confirm Joint Request"}
                    </button>
                  </div>
                </form>
              </div>
            </div>
          )}
        </div>
      )}

      {/* TAB 2: MACHINERY & EQUIPMENT TIMELINE */}
      {activeTab === "resources" && (
        <div className="space-y-6">
          <div className="gov-card">
            <div className="gov-section-header">
              <h3>Specialized Railway Machinery &amp; Resource Availability Timeline</h3>
            </div>
            <p className="text-sm text-slate-400 mb-4">
              Monitor real-time schedules and allocated intervals of high-capacity machines (CSM Track Tampers, OHE Wiring Trains, 140T Breakdown Cranes, Rail Grinders).
            </p>

            {resourcesLoading ? (
              <div className="gov-loading">Loading resource timeline…</div>
            ) : resourceTimeline.length === 0 ? (
              <div className="gov-empty">
                <div className="gov-empty-icon">🚜</div>
                <p>No resource records found.</p>
              </div>
            ) : (
              <div className="space-y-4">
                {resourceTimeline.map((r) => (
                  <div key={r.resource_id} className="bg-slate-900 border border-slate-800 p-4 rounded-xl">
                    <div className="flex flex-col md:flex-row md:items-center justify-between gap-2">
                      <div>
                        <div className="flex items-center gap-2">
                          <span className="font-bold text-white text-sm">{r.resource_name}</span>
                          <span className="font-mono text-xs text-blue-400">({r.resource_code})</span>
                          <span className="px-2 py-0.5 bg-slate-800 text-slate-300 text-xs rounded">
                            {r.resource_type}
                          </span>
                        </div>
                        <div className="text-xs text-slate-400 mt-1">
                          Dept: <span className="text-slate-200">{r.department_name}</span> | Quantity: <span className="text-slate-200">{r.quantity}</span>
                        </div>
                      </div>

                      <span className={`px-3 py-1 rounded-full text-xs font-bold ${r.is_available ? "bg-emerald-950 text-emerald-300 border border-emerald-800" : "bg-amber-950 text-amber-300 border border-amber-800"}`}>
                        {r.is_available ? "AVAILABLE FOR SHARING" : "ALLOCATED"}
                      </span>
                    </div>

                    {/* Timeline Schedule */}
                    <div className="mt-3 pt-3 border-t border-slate-800/80">
                      <div className="text-xs text-slate-400 font-semibold mb-2">Booked Possession Schedule:</div>
                      {r.allocations.length === 0 ? (
                        <div className="text-xs text-emerald-400">🟢 100% Free capacity across corridor windows</div>
                      ) : (
                        <div className="flex flex-wrap gap-2">
                          {r.allocations.map((a: any) => (
                            <span key={a.allocation_id} className="px-2.5 py-1 bg-slate-950 border border-slate-800 text-amber-400 text-xs rounded font-mono">
                              🔒 {a.start ? new Date(a.start).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }) : "—"} -{" "}
                              {a.end ? new Date(a.end).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }) : "—"} (Qty: {a.quantity})
                            </span>
                          ))}
                        </div>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      )}

      {/* TAB 3: COORDINATION DETECTOR & REQUESTS */}
      {activeTab === "opportunities" && (
        <div className="space-y-6">
          <div className="gov-card">
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: 12 }}>
              <div>
                <h3 style={{ margin: 0, fontSize: 16, fontWeight: 600 }}>Automated Opportunity Detector</h3>
                <p className="gov-muted" style={{ margin: "4px 0 0 0", fontSize: 13 }}>
                  Automatically scan verified requests across departments for time &amp; track overlap.
                </p>
              </div>
              <button className="gov-btn gov-btn-primary" type="button" onClick={onDetect} disabled={detecting}>
                {detecting ? "Scanning Corridors…" : "⚡ Run Coordination Detector"}
              </button>
            </div>
            {detectMsg ? <div className="gov-alert gov-alert-success" role="status" style={{ marginTop: 12 }}>{detectMsg}</div> : null}
          </div>

          <div className="gov-card">
            <div className="gov-section-header">
              <h3>Active Pairwise Coordination Requests</h3>
            </div>
            {loading ? <div className="gov-loading">Loading coordination opportunities…</div> : null}
            {error && !loading ? <div className="gov-alert gov-alert-error" role="alert">{error}</div> : null}
            {!loading && !error && data && data.items.length === 0 ? (
              <div className="gov-empty">
                <div className="gov-empty-icon">📋</div>
                <p>No coordination requests found.</p>
              </div>
            ) : null}

            {!loading && !error && data && data.items.length > 0 ? (
              <div className="gov-table-wrap">
                <table className="gov-table">
                  <thead>
                    <tr>
                      <th>ID</th>
                      <th>Source ↔ Target</th>
                      <th>Departments</th>
                      <th>Section / Track</th>
                      <th>Overlap</th>
                      <th>Score</th>
                      <th>Compatibility</th>
                      <th>Status</th>
                      <th>Action</th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.items.map((r) => (
                      <tr key={r.id}>
                        <td>#{r.id}</td>
                        <td>
                          <span style={{ fontWeight: 600 }}>{r.source_block_code || `Block #${r.source_block_id}`}</span>
                          {" ↔ "}
                          <span style={{ fontWeight: 600 }}>{r.target_block_code || `Block #${r.target_block_id}`}</span>
                        </td>
                        <td>
                          <span className="gov-badge gov-badge-blue">{r.requesting_department_code}</span>
                          {" → "}
                          <span className="gov-badge gov-badge-blue">{r.target_department_code}</span>
                        </td>
                        <td>
                          {r.section_id ? `Sec ${r.section_id}` : "—"}
                          {r.track_id ? ` / Trk ${r.track_id}` : ""}
                        </td>
                        <td>{r.overlap_duration_mins != null ? `${r.overlap_duration_mins} mins` : "—"}</td>
                        <td>{r.coordination_score != null ? `${r.coordination_score}%` : "—"}</td>
                        <td title={compatibilityNote(r.compatibility_status)}>
                          {r.compatibility_status ? (
                            <span className={`gov-badge gov-badge-${r.compatibility_status === "COMPATIBLE" ? "green" : r.compatibility_status === "POTENTIAL_INCOMPATIBLE" ? "red" : "amber"}`}>
                              {r.compatibility_status}
                            </span>
                          ) : "—"}
                        </td>
                        <td><span className={`gov-badge gov-badge-${integrationBadgeKind(r.final_status)}`}>{r.final_status}</span></td>
                        <td><Link className="gov-link" href={`/integration/${r.id}`}>Review</Link></td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : null}
          </div>
        </div>
      )}
    </div>
  );
}
