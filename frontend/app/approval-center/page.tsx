"use client";

import React, { useEffect, useState, useMemo } from "react";
import Link from "next/link";
import ProtectedRoute from "@/components/ProtectedRoute";
import AppShell from "@/components/AppShell";
import Breadcrumbs from "@/components/Breadcrumbs";
import { api, ApiError } from "@/lib/api-client";
import { useAuth } from "@/lib/auth-context";
import type { PendingApprovalItem } from "@/types/approval";

export default function ApprovalCenterPage() {
  return (
    <ProtectedRoute>
      <AppShell>
        <ApprovalCenterContent />
      </AppShell>
    </ProtectedRoute>
  );
}

function ApprovalCenterContent() {
  const { user } = useAuth();
  const isOfficial = user?.role === "AUTHORIZED_OFFICIAL";

  const [pendingList, setPendingList] = useState<PendingApprovalItem[]>([]);
  const [scheduledList, setScheduledList] = useState<any[]>([]);
  const [activeList, setActiveList] = useState<any[]>([]);
  const [historyList, setHistoryList] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [activeTab, setActiveTab] = useState<"pending" | "scheduled" | "active" | "history">("pending");
  const [deptFilter, setDeptFilter] = useState<string>("ALL");
  const [searchQuery, setSearchQuery] = useState<string>("");

  useEffect(() => {
    async function loadData() {
      setLoading(true);
      setError(null);
      try {
        const [pendingRes, schedRes, actRes, histRes] = await Promise.all([
          api.get<PendingApprovalItem[]>("/api/approval/pending").catch(() => []),
          api.get<any[]>("/api/blocks/scheduled").catch(() => []),
          api.get<any[]>("/api/blocks/active").catch(() => []),
          api.get<any[]>("/api/approval/history").catch(() => []),
        ]);
        setPendingList(pendingRes);
        setScheduledList(schedRes);
        setActiveList(actRes);
        setHistoryList(histRes);
      } catch (err) {
        setError(err instanceof ApiError ? err.message : "Failed to load approval center data.");
      } finally {
        setLoading(false);
      }
    }
    void loadData();
  }, []);

  const filteredPending = useMemo(() => {
    return pendingList.filter((item) => {
      const matchDept = deptFilter === "ALL" || item.ownership.primary_department === deptFilter;
      const matchQuery =
        !searchQuery ||
        item.block_code.toLowerCase().includes(searchQuery.toLowerCase()) ||
        item.maintenance_request.request_code.toLowerCase().includes(searchQuery.toLowerCase()) ||
        item.map_context.section_code.toLowerCase().includes(searchQuery.toLowerCase());
      return matchDept && matchQuery;
    });
  }, [pendingList, deptFilter, searchQuery]);

  return (
    <div className="gov-page">
      <Breadcrumbs
        trail={[
          { label: "Dashboard", href: "/dashboard" },
          { label: "Approval Center" },
        ]}
      />

      <div className="gov-page-header">
        <div>
          <h2 className="gov-title">Railway Official Approval Center</h2>
          <p className="gov-sub">
            Authoritative human-in-the-loop decision center. Review AI predictions, safety validations, and OR-Tools optimization recommendations before authorizing railway blocks.
          </p>
        </div>
        {isOfficial && (
          <div className="gov-badge gov-badge-info" style={{ padding: "8px 16px", fontSize: "0.9rem" }}>
            🛡 Authorized Decision Maker
          </div>
        )}
      </div>

      {/* KPI Metrics */}
      <div className="gov-grid gov-grid-4" style={{ marginBottom: "24px" }}>
        <div className="gov-stat-card">
          <span className="gov-stat-num" style={{ color: "#d97706" }}>{pendingList.length}</span>
          <span className="gov-stat-label">Pending Decisions</span>
        </div>
        <div className="gov-stat-card">
          <span className="gov-stat-num" style={{ color: "#2563eb" }}>{scheduledList.length}</span>
          <span className="gov-stat-label">Scheduled Blocks</span>
        </div>
        <div className="gov-stat-card">
          <span className="gov-stat-num" style={{ color: "#059669" }}>{activeList.length}</span>
          <span className="gov-stat-label">Active / Maintenance</span>
        </div>
        <div className="gov-stat-card">
          <span className="gov-stat-num" style={{ color: "#6366f1" }}>{historyList.length}</span>
          <span className="gov-stat-label">Decision Audit Trail</span>
        </div>
      </div>

      {/* Navigation Tabs */}
      <div style={{ display: "flex", gap: "8px", borderBottom: "2px solid #e2e8f0", marginBottom: "20px" }}>
        <button
          onClick={() => setActiveTab("pending")}
          className={`gov-tab ${activeTab === "pending" ? "gov-tab-active" : ""}`}
          style={{ padding: "10px 20px", fontWeight: 600, border: "none", background: "none", cursor: "pointer", borderBottom: activeTab === "pending" ? "3px solid #1e3a8a" : "none", color: activeTab === "pending" ? "#1e3a8a" : "#64748b" }}
        >
          Pending Decisions ({pendingList.length})
        </button>
        <button
          onClick={() => setActiveTab("scheduled")}
          className={`gov-tab ${activeTab === "scheduled" ? "gov-tab-active" : ""}`}
          style={{ padding: "10px 20px", fontWeight: 600, border: "none", background: "none", cursor: "pointer", borderBottom: activeTab === "scheduled" ? "3px solid #1e3a8a" : "none", color: activeTab === "scheduled" ? "#1e3a8a" : "#64748b" }}
        >
          Scheduled Blocks ({scheduledList.length})
        </button>
        <button
          onClick={() => setActiveTab("active")}
          className={`gov-tab ${activeTab === "active" ? "gov-tab-active" : ""}`}
          style={{ padding: "10px 20px", fontWeight: 600, border: "none", background: "none", cursor: "pointer", borderBottom: activeTab === "active" ? "3px solid #1e3a8a" : "none", color: activeTab === "active" ? "#1e3a8a" : "#64748b" }}
        >
          Active Execution ({activeList.length})
        </button>
        <button
          onClick={() => setActiveTab("history")}
          className={`gov-tab ${activeTab === "history" ? "gov-tab-active" : ""}`}
          style={{ padding: "10px 20px", fontWeight: 600, border: "none", background: "none", cursor: "pointer", borderBottom: activeTab === "history" ? "3px solid #1e3a8a" : "none", color: activeTab === "history" ? "#1e3a8a" : "#64748b" }}
        >
          Decision Audit History ({historyList.length})
        </button>
      </div>

      {loading && <p style={{ color: "#64748b" }}>Loading approval center data...</p>}
      {error && <div className="gov-alert gov-alert-danger">{error}</div>}

      {/* Tab 1: Pending Decisions */}
      {!loading && activeTab === "pending" && (
        <div>
          <div style={{ display: "flex", gap: "16px", marginBottom: "16px", alignItems: "center" }}>
            <input
              type="text"
              placeholder="Search by Block, MR Code, Section..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="gov-input"
              style={{ maxWidth: "320px" }}
            />
            <select
              value={deptFilter}
              onChange={(e) => setDeptFilter(e.target.value)}
              className="gov-select"
              style={{ maxWidth: "200px" }}
            >
              <option value="ALL">All Departments</option>
              <option value="ENG">Engineering</option>
              <option value="ELEC">Electrical / OHE</option>
              <option value="SNT">S&T</option>
            </select>
          </div>

          {filteredPending.length === 0 ? (
            <div className="gov-card" style={{ textAlign: "center", padding: "40px", color: "#64748b" }}>
              <p style={{ fontSize: "1.1rem", fontWeight: 500 }}>No pending block recommendations awaiting review.</p>
              <p style={{ fontSize: "0.9rem" }}>When OR-Tools generates optimal block proposals from verified maintenance requests, they will appear here for authoritative review.</p>
            </div>
          ) : (
            <div style={{ display: "flex", flexDirection: "column", gap: "16px" }}>
              {filteredPending.map((item) => (
                <div key={item.optimized_block_id} className="gov-card" style={{ borderLeft: "5px solid #2563eb", padding: "20px" }}>
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
                    <div>
                      <div style={{ display: "flex", alignItems: "center", gap: "10px", marginBottom: "6px" }}>
                        <span style={{ fontSize: "1.2rem", fontWeight: 700, color: "#1e293b" }}>{item.block_code}</span>
                        <span className="gov-badge gov-badge-info">{item.maintenance_request.department}</span>
                        {item.ownership.is_integrated && (
                          <span className="gov-badge gov-badge-success">
                            🔗 Coordinated ({item.ownership.participating_departments.join(" + ")})
                          </span>
                        )}
                        <span className="gov-badge gov-badge-warning">{item.status}</span>
                      </div>
                      <p style={{ color: "#475569", margin: "4px 0", fontSize: "0.95rem" }}>
                        <strong>Request:</strong> {item.maintenance_request.request_code} — {item.maintenance_request.description || item.maintenance_request.maintenance_type}
                      </p>
                      <p style={{ color: "#64748b", margin: "4px 0", fontSize: "0.9rem" }}>
                        <strong>Location:</strong> Section {item.map_context.section_code} | Track: {item.map_context.track_code}
                      </p>
                    </div>

                    <div style={{ textAlign: "right" }}>
                      <Link
                        href={`/approval-center/${item.optimized_block_id}`}
                        className="gov-btn gov-btn-primary"
                        style={{ padding: "8px 20px", display: "inline-block" }}
                      >
                        Inspect & Decide →
                      </Link>
                    </div>
                  </div>

                  <div style={{ display: "grid", gridTemplateColumns: "repeat(6, 1fr)", gap: "12px", marginTop: "16px", background: "#f8fafc", padding: "12px", borderRadius: "6px" }}>
                    <div>
                      <span style={{ fontSize: "0.75rem", color: "#64748b", textTransform: "uppercase", display: "block" }}>Recommended Window</span>
                      <strong style={{ color: "#1e293b" }}>{item.optimization.recommended_window}</strong>
                    </div>
                    <div>
                      <span style={{ fontSize: "0.75rem", color: "#64748b", textTransform: "uppercase", display: "block" }}>Duration</span>
                      <strong style={{ color: "#1e293b" }}>{item.optimization.duration_mins} mins</strong>
                    </div>
                    <div>
                      <span style={{ fontSize: "0.75rem", color: "#64748b", textTransform: "uppercase", display: "block" }}>Risk Classification</span>
                      <strong style={{ color: item.ai_predictions.operational_risk === "HIGH" ? "#dc2626" : "#2563eb" }}>
                        {item.ai_predictions.operational_risk} ({Math.round(item.ai_predictions.risk_probability * 100)}%)
                      </strong>
                    </div>
                    <div>
                      <span style={{ fontSize: "0.75rem", color: "#64748b", textTransform: "uppercase", display: "block" }}>Affected Trains</span>
                      <strong style={{ color: "#1e293b" }}>{item.ai_predictions.affected_train_count} Trains</strong>
                    </div>
                    <div>
                      <span style={{ fontSize: "0.75rem", color: "#64748b", textTransform: "uppercase", display: "block" }}>Predicted Delay</span>
                      <strong style={{ color: "#1e293b" }}>{item.ai_predictions.total_predicted_delay_mins} mins</strong>
                    </div>
                    <div>
                      <span style={{ fontSize: "0.75rem", color: "#64748b", textTransform: "uppercase", display: "block" }}>Safety Status</span>
                      <strong style={{ color: item.safety_validation.overall_status === "SAFE" ? "#16a34a" : "#dc2626" }}>
                        {item.safety_validation.overall_status}
                      </strong>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Tab 2: Scheduled Blocks */}
      {!loading && activeTab === "scheduled" && (
        <div className="gov-card">
          <h3 style={{ fontSize: "1.1rem", fontWeight: 600, marginBottom: "16px" }}>Scheduled Railway Blocks</h3>
          {scheduledList.length === 0 ? (
            <p style={{ color: "#64748b" }}>No officially scheduled blocks found.</p>
          ) : (
            <table className="gov-table" style={{ width: "100%" }}>
              <thead>
                <tr>
                  <th>Block Code</th>
                  <th>Section</th>
                  <th>Track</th>
                  <th>Start Time</th>
                  <th>End Time</th>
                  <th>Duration</th>
                  <th>Status</th>
                  <th>Action</th>
                </tr>
              </thead>
              <tbody>
                {scheduledList.map((b) => (
                  <tr key={b.optimized_block_id}>
                    <td><strong>{b.block_code}</strong></td>
                    <td>{b.section_id}</td>
                    <td>{b.track_id || "All"}</td>
                    <td>{b.start_time ? new Date(b.start_time).toLocaleString() : "N/A"}</td>
                    <td>{b.end_time ? new Date(b.end_time).toLocaleString() : "N/A"}</td>
                    <td>{b.duration_mins} mins</td>
                    <td><span className="gov-badge gov-badge-info">{b.status}</span></td>
                    <td>
                      <Link href={`/approval-center/${b.optimized_block_id}`} className="gov-btn gov-btn-secondary" style={{ padding: "4px 10px", fontSize: "0.85rem" }}>
                        View Details
                      </Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      )}

      {/* Tab 3: Active Blocks */}
      {!loading && activeTab === "active" && (
        <div className="gov-card">
          <h3 style={{ fontSize: "1.1rem", fontWeight: 600, marginBottom: "16px" }}>Active Execution & Maintenance</h3>
          {activeList.length === 0 ? (
            <p style={{ color: "#64748b" }}>No active blocks currently underway.</p>
          ) : (
            <table className="gov-table" style={{ width: "100%" }}>
              <thead>
                <tr>
                  <th>Block Code</th>
                  <th>Section</th>
                  <th>Window</th>
                  <th>Status</th>
                  <th>Action</th>
                </tr>
              </thead>
              <tbody>
                {activeList.map((b) => (
                  <tr key={b.optimized_block_id}>
                    <td><strong>{b.block_code}</strong></td>
                    <td>{b.section_id}</td>
                    <td>{b.start_time ? new Date(b.start_time).toLocaleTimeString() : "N/A"} - {b.end_time ? new Date(b.end_time).toLocaleTimeString() : "N/A"}</td>
                    <td><span className="gov-badge gov-badge-success">{b.status}</span></td>
                    <td>
                      <Link href={`/approval-center/${b.optimized_block_id}`} className="gov-btn gov-btn-secondary" style={{ padding: "4px 10px", fontSize: "0.85rem" }}>
                        Monitor
                      </Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      )}

      {/* Tab 4: History */}
      {!loading && activeTab === "history" && (
        <div className="gov-card">
          <h3 style={{ fontSize: "1.1rem", fontWeight: 600, marginBottom: "16px" }}>Decision Audit Log</h3>
          {historyList.length === 0 ? (
            <p style={{ color: "#64748b" }}>No approval audit events recorded yet.</p>
          ) : (
            <table className="gov-table" style={{ width: "100%" }}>
              <thead>
                <tr>
                  <th>Timestamp</th>
                  <th>Block</th>
                  <th>Action</th>
                  <th>Decided By</th>
                  <th>Reason / Details</th>
                </tr>
              </thead>
              <tbody>
                {historyList.map((h) => (
                  <tr key={h.id}>
                    <td>{h.created_at ? new Date(h.created_at).toLocaleString() : "N/A"}</td>
                    <td><strong>{h.block_code}</strong></td>
                    <td>
                      <span className={`gov-badge ${h.action.includes("APPROVE") ? "gov-badge-success" : h.action.includes("REJECT") ? "gov-badge-danger" : "gov-badge-info"}`}>
                        {h.action}
                      </span>
                    </td>
                    <td>{h.user_name}</td>
                    <td style={{ maxWidth: "300px" }}>{h.description}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      )}
    </div>
  );
}
