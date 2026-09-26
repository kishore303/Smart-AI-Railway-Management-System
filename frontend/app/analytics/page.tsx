"use client";

import React, { useState, useEffect } from "react";
import Link from "next/link";
import {
  AnalyticsOverviewResponse,
  BlockAnalyticsResponse,
  TrainImpactAnalyticsResponse,
  AssetAnalyticsResponse,
  ResourceAnalyticsResponse,
  CoordinationAnalyticsResponse,
  EmergencyAnalyticsResponse,
  OptimizationAnalyticsResponse,
  ModelAnalyticsResponse,
} from "@/types/analytics";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE || "http://localhost:8000";

export default function AnalyticsPage() {
  const [activeTab, setActiveTab] = useState<string>("overview");
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  const [overview, setOverview] = useState<AnalyticsOverviewResponse | null>(null);
  const [blocks, setBlocks] = useState<BlockAnalyticsResponse | null>(null);
  const [trains, setTrains] = useState<TrainImpactAnalyticsResponse | null>(null);
  const [assets, setAssets] = useState<AssetAnalyticsResponse | null>(null);
  const [resources, setResources] = useState<ResourceAnalyticsResponse | null>(null);
  const [coordination, setCoordination] = useState<CoordinationAnalyticsResponse | null>(null);
  const [emergencies, setEmergencies] = useState<EmergencyAnalyticsResponse | null>(null);
  const [optimization, setOptimization] = useState<OptimizationAnalyticsResponse | null>(null);
  const [models, setModels] = useState<ModelAnalyticsResponse | null>(null);

  const token = typeof window !== "undefined" ? localStorage.getItem("token") : null;

  const fetchAnalytics = async () => {
    setLoading(true);
    setError(null);
    try {
      const headers: Record<string, string> = {};
      if (token) {
        headers["Authorization"] = `Bearer ${token}`;
      }

      const [ovRes, blkRes, trnRes, astRes, resRes, crdRes, emgRes, optRes, mdlRes] = await Promise.all([
        fetch(`${API_BASE}/api/analytics/overview`, { headers }),
        fetch(`${API_BASE}/api/analytics/blocks`, { headers }),
        fetch(`${API_BASE}/api/analytics/train-impact`, { headers }),
        fetch(`${API_BASE}/api/analytics/assets`, { headers }),
        fetch(`${API_BASE}/api/analytics/resources`, { headers }),
        fetch(`${API_BASE}/api/analytics/coordination`, { headers }),
        fetch(`${API_BASE}/api/analytics/emergencies`, { headers }),
        fetch(`${API_BASE}/api/analytics/optimization`, { headers }),
        fetch(`${API_BASE}/api/analytics/models`, { headers }),
      ]);

      if (ovRes.ok) setOverview(await ovRes.json());
      if (blkRes.ok) setBlocks(await blkRes.json());
      if (trnRes.ok) setTrains(await trnRes.json());
      if (astRes.ok) setAssets(await astRes.json());
      if (resRes.ok) setResources(await resRes.json());
      if (crdRes.ok) setCoordination(await crdRes.json());
      if (emgRes.ok) setEmergencies(await emgRes.json());
      if (optRes.ok) setOptimization(await optRes.json());
      if (mdlRes.ok) setModels(await mdlRes.json());
    } catch (err: any) {
      setError(err.message || "Failed to load analytics data");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchAnalytics();
  }, []);

  const tabs = [
    { id: "overview", label: "Executive KPIs", icon: "📊" },
    { id: "blocks", label: "Block Lifecycle", icon: "🧱" },
    { id: "trains", label: "Train Impact", icon: "🚆" },
    { id: "assets", label: "Asset Health", icon: "🏗️" },
    { id: "resources", label: "Resource Sharing", icon: "🚜" },
    { id: "coordination", label: "Cross-Dept Coordination", icon: "🤝" },
    { id: "emergencies", label: "Emergency Operations", icon: "🚨" },
    { id: "optimization", label: "OR-Tools Solver", icon: "⚡" },
    { id: "models", label: "ML Traceability", icon: "🧠" },
  ];

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 p-6">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between pb-6 mb-6 border-b border-slate-800 gap-4">
        <div>
          <div className="flex items-center gap-3">
            <span className="text-3xl">📈</span>
            <h1 className="text-2xl font-bold tracking-tight text-white">
              Railway Operational Analytics & Intelligence
            </h1>
          </div>
          <p className="text-slate-400 text-sm mt-1">
            Persisted PostgreSQL metrics, OR-Tools CP-SAT convergence, ML pipeline audits & cross-department KPIs.
          </p>
        </div>
        <div className="flex items-center gap-3">
          <button
            onClick={fetchAnalytics}
            className="px-4 py-2 bg-blue-600 hover:bg-blue-500 rounded-lg text-sm font-medium transition flex items-center gap-2"
          >
            <span>🔄</span> Refresh Telemetry
          </button>
          <Link
            href="/digital-twin"
            className="px-4 py-2 bg-slate-800 hover:bg-slate-700 text-slate-200 rounded-lg text-sm font-medium transition flex items-center gap-2"
          >
            <span>🌐</span> Digital Twin
          </Link>
          <Link
            href="/what-if"
            className="px-4 py-2 bg-indigo-600 hover:bg-indigo-500 text-white rounded-lg text-sm font-medium transition flex items-center gap-2"
          >
            <span>🔮</span> What-If Simulator
          </Link>
        </div>
      </div>

      {error && (
        <div className="bg-red-950/60 border border-red-800 text-red-200 px-4 py-3 rounded-lg mb-6 text-sm">
          ⚠️ {error}
        </div>
      )}

      {/* Tabs */}
      <div className="flex flex-wrap gap-2 mb-6 border-b border-slate-800 pb-4">
        {tabs.map((tab) => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            className={`px-4 py-2 rounded-lg text-sm font-medium transition flex items-center gap-2 ${
              activeTab === tab.id
                ? "bg-blue-600 text-white shadow-lg shadow-blue-600/20"
                : "bg-slate-900 text-slate-400 hover:bg-slate-800 hover:text-slate-200"
            }`}
          >
            <span>{tab.icon}</span>
            {tab.label}
          </button>
        ))}
      </div>

      {loading ? (
        <div className="py-24 text-center">
          <div className="animate-spin text-4xl mb-4">⚙️</div>
          <p className="text-slate-400">Loading live operational analytics...</p>
        </div>
      ) : (
        <div>
          {/* TAB 1: EXECUTIVE KPIS */}
          {activeTab === "overview" && overview && (
            <div className="space-y-6">
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
                <div className="bg-slate-900 border border-slate-800 p-5 rounded-xl">
                  <div className="text-xs text-slate-400 font-semibold uppercase">Total Block Requests</div>
                  <div className="text-3xl font-bold text-blue-400 mt-2">
                    {overview.kpis.total_block_requests}
                  </div>
                  <div className="text-xs text-slate-400 mt-1">
                    {overview.kpis.active_blocks} Active | {overview.kpis.approved_blocks} Approved
                  </div>
                </div>

                <div className="bg-slate-900 border border-slate-800 p-5 rounded-xl">
                  <div className="text-xs text-slate-400 font-semibold uppercase">Total Predicted Delay</div>
                  <div className="text-3xl font-bold text-amber-400 mt-2">
                    {overview.kpis.total_predicted_delay_mins} <span className="text-sm font-normal">mins</span>
                  </div>
                  <div className="text-xs text-slate-400 mt-1">
                    Avg {overview.kpis.avg_predicted_delay_mins} mins / block across corridor
                  </div>
                </div>

                <div className="bg-slate-900 border border-slate-800 p-5 rounded-xl">
                  <div className="text-xs text-slate-400 font-semibold uppercase">Solver Optimization Score</div>
                  <div className="text-3xl font-bold text-emerald-400 mt-2">
                    {overview.kpis.avg_optimization_score} <span className="text-sm font-normal">/ 100</span>
                  </div>
                  <div className="text-xs text-slate-400 mt-1">
                    {overview.kpis.total_optimizations} CP-SAT mathematical solutions
                  </div>
                </div>

                <div className="bg-slate-900 border border-slate-800 p-5 rounded-xl">
                  <div className="text-xs text-slate-400 font-semibold uppercase">Emergency Incidents</div>
                  <div className="text-3xl font-bold text-rose-400 mt-2">
                    {overview.kpis.total_incidents}
                  </div>
                  <div className="text-xs text-slate-400 mt-1">
                    {overview.kpis.open_incidents} currently open/active
                  </div>
                </div>
              </div>

              {/* Secondary Grid */}
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                <div className="bg-slate-900/60 border border-slate-800 p-5 rounded-xl">
                  <h3 className="text-sm font-semibold text-slate-300 mb-3 flex items-center gap-2">
                    <span>🤝</span> Joint Possessions & Savings
                  </h3>
                  <div className="text-2xl font-bold text-indigo-400">
                    {overview.kpis.accepted_coordinations} / {overview.kpis.coordination_requests}
                  </div>
                  <p className="text-xs text-slate-400 mt-2 leading-relaxed">
                    Cross-department joint possession requests accepted, avoiding duplicate corridor closures.
                  </p>
                </div>

                <div className="bg-slate-900/60 border border-slate-800 p-5 rounded-xl">
                  <h3 className="text-sm font-semibold text-slate-300 mb-3 flex items-center gap-2">
                    <span>🏗️</span> Railway Asset Condition
                  </h3>
                  <div className="text-2xl font-bold text-emerald-400">
                    {overview.kpis.avg_asset_condition}%
                  </div>
                  <p className="text-xs text-slate-400 mt-2 leading-relaxed">
                    Average asset health index across track, OHE, signal, and bridge infrastructure.
                  </p>
                </div>

                <div className="bg-slate-900/60 border border-slate-800 p-5 rounded-xl">
                  <h3 className="text-sm font-semibold text-slate-300 mb-3 flex items-center gap-2">
                    <span>🚜</span> Shared Machinery Utilization
                  </h3>
                  <div className="text-2xl font-bold text-purple-400">
                    {overview.kpis.active_resource_allocations} Active
                  </div>
                  <p className="text-xs text-slate-400 mt-2 leading-relaxed">
                    Specialized maintenance equipment (Tamping, OHE wiring, Cranes) currently allocated.
                  </p>
                </div>
              </div>
            </div>
          )}

          {/* TAB 2: BLOCK LIFECYCLE */}
          {activeTab === "blocks" && blocks && (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              <div className="bg-slate-900 border border-slate-800 p-6 rounded-xl">
                <h3 className="text-base font-semibold text-white mb-4">Block Lifecycle Status Breakdown</h3>
                <div className="space-y-3">
                  {Object.entries(blocks.status_distribution).map(([st, cnt]) => (
                    <div key={st} className="flex items-center justify-between text-sm py-2 border-b border-slate-800/60">
                      <span className="font-mono text-slate-300">{st}</span>
                      <span className="px-2.5 py-1 bg-slate-800 rounded text-blue-400 font-semibold">{cnt}</span>
                    </div>
                  ))}
                </div>
              </div>

              <div className="bg-slate-900 border border-slate-800 p-6 rounded-xl">
                <h3 className="text-base font-semibold text-white mb-4">Department Block Workload</h3>
                <div className="space-y-3">
                  {blocks.department_distribution.map((dept) => (
                    <div key={dept.code} className="flex items-center justify-between text-sm py-2 border-b border-slate-800/60">
                      <span className="text-slate-300">{dept.department} ({dept.code})</span>
                      <span className="px-2.5 py-1 bg-slate-800 rounded text-emerald-400 font-semibold">{dept.count}</span>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          )}

          {/* TAB 3: TRAIN IMPACT */}
          {activeTab === "trains" && trains && (
            <div className="bg-slate-900 border border-slate-800 p-6 rounded-xl">
              <h3 className="text-base font-semibold text-white mb-4">Corridor Section Delay & Congestion Hotspots</h3>
              <div className="overflow-x-auto">
                <table className="w-full text-left text-sm text-slate-300">
                  <thead className="bg-slate-800/60 text-xs text-slate-400 uppercase">
                    <tr>
                      <th className="p-3">Section Code</th>
                      <th className="p-3">Section Name</th>
                      <th className="p-3">Blocks Hosted</th>
                      <th className="p-3">Trains Affected</th>
                      <th className="p-3">Total Delay (Mins)</th>
                      <th className="p-3">Avg Delay / Block</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-800">
                    {trains.section_delay_impact.map((sec) => (
                      <tr key={sec.code} className="hover:bg-slate-800/40">
                        <td className="p-3 font-mono text-blue-400">{sec.code}</td>
                        <td className="p-3 text-white font-medium">{sec.section}</td>
                        <td className="p-3">{sec.block_count}</td>
                        <td className="p-3">{sec.affected_trains}</td>
                        <td className="p-3 font-semibold text-amber-400">{sec.total_delay_mins}</td>
                        <td className="p-3">{sec.avg_delay_mins} mins</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* TAB 4: ASSETS */}
          {activeTab === "assets" && assets && (
            <div className="space-y-6">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                <div className="bg-slate-900 border border-slate-800 p-6 rounded-xl">
                  <h3 className="text-base font-semibold text-white mb-4">Asset Health Index Categories</h3>
                  <div className="space-y-3">
                    {Object.entries(assets.health_distribution).map(([cat, cnt]) => (
                      <div key={cat} className="flex items-center justify-between text-sm py-2 border-b border-slate-800/60">
                        <span className="text-slate-300">{cat}</span>
                        <span className="px-2.5 py-1 bg-slate-800 rounded font-semibold text-indigo-400">{cnt}</span>
                      </div>
                    ))}
                  </div>
                </div>

                <div className="bg-slate-900 border border-slate-800 p-6 rounded-xl">
                  <h3 className="text-base font-semibold text-white mb-4">Asset Type Breakdown</h3>
                  <div className="space-y-3">
                    {assets.type_summary.map((t) => (
                      <div key={t.type} className="flex items-center justify-between text-sm py-2 border-b border-slate-800/60">
                        <span className="text-slate-300">{t.type}</span>
                        <div className="flex items-center gap-3">
                          <span className="text-xs text-slate-400">Avg Condition: {t.avg_condition}%</span>
                          <span className="px-2 py-0.5 bg-slate-800 rounded text-slate-200 font-semibold">{t.count}</span>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              </div>

              {/* High risk assets */}
              <div className="bg-slate-900 border border-slate-800 p-6 rounded-xl">
                <h3 className="text-base font-semibold text-white mb-4 flex items-center gap-2">
                  <span className="text-rose-400">⚠️</span> Priority Attention Assets (Condition &lt; 50)
                </h3>
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                  {assets.high_risk_assets.map((a) => (
                    <div key={a.id} className="bg-slate-950 border border-rose-900/40 p-4 rounded-lg">
                      <div className="flex items-center justify-between">
                        <span className="font-mono text-xs text-rose-400">{a.code}</span>
                        <span className="px-2 py-0.5 bg-rose-950 border border-rose-800 text-rose-300 text-xs font-bold rounded">
                          {a.condition_score}% Condition
                        </span>
                      </div>
                      <div className="text-sm font-semibold text-white mt-1">{a.name}</div>
                      <div className="text-xs text-slate-400 mt-1">Section: {a.section} | Type: {a.type}</div>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          )}

          {/* TAB 5: RESOURCES */}
          {activeTab === "resources" && resources && (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              <div className="bg-slate-900 border border-slate-800 p-6 rounded-xl">
                <h3 className="text-base font-semibold text-white mb-4">Equipment & Machinery Inventory</h3>
                <div className="space-y-3">
                  {resources.resource_types.map((r) => (
                    <div key={r.type} className="flex items-center justify-between text-sm py-2 border-b border-slate-800/60">
                      <span className="text-slate-300">{r.type}</span>
                      <span className="text-slate-200 font-semibold">{r.total_units} units ({r.distinct_items} distinct items)</span>
                    </div>
                  ))}
                </div>
              </div>

              <div className="bg-slate-900 border border-slate-800 p-6 rounded-xl">
                <h3 className="text-base font-semibold text-white mb-4">Department Machinery Allocation</h3>
                <div className="space-y-3">
                  {resources.department_resources.map((d) => (
                    <div key={d.department} className="flex items-center justify-between text-sm py-2 border-b border-slate-800/60">
                      <span className="text-slate-300">{d.department}</span>
                      <span className="text-purple-400 font-semibold">{d.units} units</span>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          )}

          {/* TAB 6: COORDINATION */}
          {activeTab === "coordination" && coordination && (
            <div className="bg-slate-900 border border-slate-800 p-6 rounded-xl">
              <h3 className="text-base font-semibold text-white mb-4">Cross-Department Joint Possessions</h3>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                <div>
                  <h4 className="text-xs font-semibold text-slate-400 uppercase mb-3">Status Distribution</h4>
                  <div className="space-y-2">
                    {Object.entries(coordination.integration_status_distribution).map(([st, cnt]) => (
                      <div key={st} className="flex items-center justify-between text-sm py-2 border-b border-slate-800/60">
                        <span className="font-mono text-slate-300">{st}</span>
                        <span className="px-2.5 py-1 bg-slate-800 rounded font-semibold text-indigo-400">{cnt}</span>
                      </div>
                    ))}
                  </div>
                </div>
                <div>
                  <h4 className="text-xs font-semibold text-slate-400 uppercase mb-3">Collaborating Department Pairs</h4>
                  <div className="space-y-2">
                    {coordination.department_coordination_pairs.map((p, idx) => (
                      <div key={idx} className="flex items-center justify-between text-sm py-2 border-b border-slate-800/60">
                        <span className="text-slate-300">{p.requesting} ↔ {p.target}</span>
                        <span className="px-2.5 py-1 bg-slate-800 rounded font-semibold text-emerald-400">{p.count} joint requests</span>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* TAB 7: EMERGENCIES */}
          {activeTab === "emergencies" && emergencies && (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              <div className="bg-slate-900 border border-slate-800 p-6 rounded-xl">
                <h3 className="text-base font-semibold text-white mb-4">Incidents by Severity Level</h3>
                <div className="space-y-3">
                  {Object.entries(emergencies.severity_distribution).map(([sev, cnt]) => (
                    <div key={sev} className="flex items-center justify-between text-sm py-2 border-b border-slate-800/60">
                      <span className={`font-bold ${sev === 'CRITICAL' ? 'text-rose-400' : sev === 'HIGH' ? 'text-amber-400' : 'text-blue-400'}`}>
                        {sev}
                      </span>
                      <span className="px-2.5 py-1 bg-slate-800 rounded text-slate-200 font-semibold">{cnt}</span>
                    </div>
                  ))}
                </div>
              </div>

              <div className="bg-slate-900 border border-slate-800 p-6 rounded-xl">
                <h3 className="text-base font-semibold text-white mb-4">Incident Types</h3>
                <div className="space-y-3">
                  {Object.entries(emergencies.incident_types).map(([typ, cnt]) => (
                    <div key={typ} className="flex items-center justify-between text-sm py-2 border-b border-slate-800/60">
                      <span className="text-slate-300">{typ}</span>
                      <span className="px-2.5 py-1 bg-slate-800 rounded text-slate-200 font-semibold">{cnt}</span>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          )}

          {/* TAB 8: OPTIMIZATION SOLVER */}
          {activeTab === "optimization" && optimization && (
            <div className="space-y-6">
              <div className="bg-slate-900 border border-slate-800 p-6 rounded-xl">
                <div className="flex items-center justify-between mb-4">
                  <h3 className="text-base font-semibold text-white">OR-Tools CP-SAT Solver Performance</h3>
                  <span className="px-3 py-1 bg-emerald-950 border border-emerald-800 text-emerald-400 text-xs font-semibold rounded-full">
                    {optimization.solver_engine}
                  </span>
                </div>
                <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mt-4">
                  <div className="bg-slate-950 p-4 rounded-lg border border-slate-800">
                    <div className="text-xs text-slate-400">Min Optimization Score</div>
                    <div className="text-2xl font-bold text-slate-200 mt-1">{optimization.score_statistics.min_score}</div>
                  </div>
                  <div className="bg-slate-950 p-4 rounded-lg border border-slate-800">
                    <div className="text-xs text-slate-400">Avg Optimization Score</div>
                    <div className="text-2xl font-bold text-emerald-400 mt-1">{optimization.score_statistics.avg_score}</div>
                  </div>
                  <div className="bg-slate-950 p-4 rounded-lg border border-slate-800">
                    <div className="text-xs text-slate-400">Max Optimization Score</div>
                    <div className="text-2xl font-bold text-blue-400 mt-1">{optimization.score_statistics.max_score}</div>
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* TAB 9: ML TRACEABILITY */}
          {activeTab === "models" && models && (
            <div className="space-y-6">
              <div className="bg-slate-900 border border-slate-800 p-6 rounded-xl">
                <h3 className="text-base font-semibold text-white mb-4">Registered AI / ML Model Pipelines & Verification</h3>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  {Object.entries(models.models).map(([key, m]) => (
                    <div key={key} className="bg-slate-950 border border-slate-800 p-4 rounded-lg">
                      <div className="flex items-center justify-between">
                        <span className="font-mono text-sm font-semibold text-blue-400">{key}</span>
                        <span className="px-2 py-0.5 bg-emerald-950 border border-emerald-800 text-emerald-300 text-xs font-bold rounded">
                          {m.status}
                        </span>
                      </div>
                      <div className="text-xs text-slate-400 mt-2 font-mono truncate">MD5: {m.md5 || "Verified Dataset"}</div>
                      <div className="text-xs text-slate-500 mt-1">Size: {(m.size_bytes / 1024).toFixed(1)} KB</div>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
