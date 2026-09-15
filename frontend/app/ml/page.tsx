"use client";

import React, { useEffect, useState } from "react";
import ProtectedRoute from "@/components/ProtectedRoute";
import AppShell from "@/components/AppShell";
import Breadcrumbs from "@/components/Breadcrumbs";
import { api, ApiError } from "@/lib/api-client";
import type {
  AssetRiskResult,
  DurationResult,
  ModelRegistryEntry,
  PredictionRecord,
  TrainImpactFeatures,
  TrainImpactResult,
} from "@/types/ml";
import {
  ASSET_RISK_CATEGORICAL,
  ASSET_RISK_NUMERIC_DEFAULTS,
  ASSET_RISK_NUMERIC_FIELDS,
  TRAIN_IMPACT_DEFAULTS,
} from "@/types/ml";

type Tab = "train" | "asset" | "duration" | "history";

const TAB_LABELS: Record<Tab, string> = {
  train: "Train Impact",
  asset: "Asset Risk",
  duration: "Duration (Demo)",
  history: "History",
};

export default function MlPage() {
  return (
    <ProtectedRoute>
      <AppShell>
        <MlContent />
      </AppShell>
    </ProtectedRoute>
  );
}

function MlContent() {
  const [tab, setTab] = useState<Tab>("train");
  const [models, setModels] = useState<ModelRegistryEntry[] | null>(null);

  useEffect(() => {
    api.get<ModelRegistryEntry[]>("/api/ml/models").then(setModels).catch(() => setModels(null));
  }, []);

  return (
    <div className="gov-page">
      <Breadcrumbs trail={[{ label: "Dashboard", href: "/dashboard" }, { label: "ML Predictions" }]} />

      <div className="gov-page-header">
        <div>
          <h2 className="gov-title">ML Predictions — Decision Support Only</h2>
          <p className="gov-sub">
            AI/ML predictions support planning decisions. A prediction is never an approval, safety clearance, or authorization to execute.
          </p>
        </div>
      </div>

      {models ? (
        <div className="gov-card">
          <div className="gov-section-header">
            <h3 className="gov-section-title">Registered Models</h3>
          </div>
          <div className="gov-table-wrap">
            <table className="gov-table">
              <thead>
                <tr>
                  <th>Type</th>
                  <th>Version</th>
                  <th>Artifact</th>
                  <th>Mode</th>
                </tr>
              </thead>
              <tbody>
                {models.map((m) => (
                  <tr key={m.model_type}>
                    <td style={{ fontWeight: 600 }}>{m.model_type}</td>
                    <td>{m.version}</td>
                    <td style={{ fontFamily: "var(--font-mono)", fontSize: "0.82rem" }}>{m.artifact_filename}</td>
                    <td>
                      {m.is_demo ? (
                        <span className="gov-badge gov-badge-amber">Demo/Synthetic</span>
                      ) : (
                        <span className="gov-badge gov-badge-green">Production</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      ) : null}

      <div className="gov-card">
        <div className="gov-tabs">
          {(["train", "asset", "duration", "history"] as Tab[]).map((t) => (
            <button
              key={t}
              type="button"
              className={`gov-tab ${tab === t ? "active" : ""}`}
              onClick={() => setTab(t)}
            >
              {TAB_LABELS[t]}
            </button>
          ))}
        </div>
      </div>

      {tab === "train" ? <TrainForm /> : null}
      {tab === "asset" ? <AssetForm /> : null}
      {tab === "duration" ? <DurationForm /> : null}
      {tab === "history" ? <HistoryView /> : null}
    </div>
  );
}

function RequestIdInput({ value, onChange }: { value: string; onChange: (v: string) => void }) {
  return (
    <div>
      <label className="gov-label" htmlFor="ml-req">Maintenance Request ID (optional — links &amp; persists prediction)</label>
      <input id="ml-req" className="gov-input" inputMode="numeric" value={value} onChange={(e) => onChange(e.target.value)} placeholder="e.g. 12" />
    </div>
  );
}

function ResultBox({ title, children, variant }: { title: string; children: React.ReactNode; variant?: "accent" | "success" | "warning" | "danger" }) {
  const cardClass = variant ? `gov-card gov-card-${variant}` : "gov-card";
  return (
    <div className={cardClass} style={{ marginTop: 12 }}>
      <div className="gov-section-header">
        <h3 className="gov-section-title">{title}</h3>
      </div>
      {children}
    </div>
  );
}

function TrainForm() {
  const [f, setF] = useState<TrainImpactFeatures>({ ...TRAIN_IMPACT_DEFAULTS });
  const [reqId, setReqId] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [res, setRes] = useState<TrainImpactResult | null>(null);

  function set<K extends keyof TrainImpactFeatures>(k: K, v: TrainImpactFeatures[K]) {
    setF((p) => ({ ...p, [k]: v }));
  }

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (loading) return;
    setError(null);
    setRes(null);
    setLoading(true);
    try {
      const payload: Record<string, unknown> = { ...f };
      if (reqId.trim() !== "") payload.maintenance_request_id = Number(reqId);
      const r = await api.post<TrainImpactResult>("/api/ml/predict/train-impact", payload);
      setRes(r);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Unable to connect to the railway service. Please try again.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="gov-card">
      <div className="gov-section-header">
        <h3 className="gov-section-title">Train Impact Prediction</h3>
      </div>
      <form onSubmit={onSubmit}>
        <div className="gov-form-grid">
          <div>
            <label className="gov-label" htmlFor="ti-num">Train Number <span className="gov-required">*</span></label>
            <input id="ti-num" className="gov-input" type="number" min={1} value={f.train_number} onChange={(e) => set("train_number", Number(e.target.value))} required />
          </div>
          <div>
            <label className="gov-label" htmlFor="ti-name">Train Name <span className="gov-required">*</span></label>
            <input id="ti-name" className="gov-input" value={f.train_name} onChange={(e) => set("train_name", e.target.value)} required />
          </div>
          <div>
            <label className="gov-label" htmlFor="ti-code">Station Code <span className="gov-required">*</span></label>
            <input id="ti-code" className="gov-input" value={f.station_code} onChange={(e) => set("station_code", e.target.value)} required />
          </div>
          <div>
            <label className="gov-label" htmlFor="ti-stn">Station Name <span className="gov-required">*</span></label>
            <input id="ti-stn" className="gov-input" value={f.station_name} onChange={(e) => set("station_name", e.target.value)} required />
          </div>
          {(["pct_right_time", "pct_slight_delay", "pct_significant_delay", "pct_cancelled_unknown"] as const).map((k) => (
            <div key={k}>
              <label className="gov-label" htmlFor={`ti-${k}`}>{k} (0–100) <span className="gov-required">*</span></label>
              <input
                id={`ti-${k}`}
                className="gov-input"
                type="number"
                min={0}
                max={100}
                step="any"
                value={f[k]}
                onChange={(e) => set(k, Number(e.target.value))}
                required
              />
            </div>
          ))}
        </div>
        <div className="gov-info-box">Percentage fields must sum to approximately 100.</div>
        <RequestIdInput value={reqId} onChange={setReqId} />
        {error ? <div className="gov-alert gov-alert-error" role="alert">{error}</div> : null}
        <div className="gov-form-actions">
          <button className="gov-btn" type="submit" disabled={loading}>{loading ? "Predicting…" : "Run Train Impact Prediction"}</button>
        </div>
      </form>
      {res ? (
        <ResultBox title="Train Impact Prediction Result" variant="accent">
          <div className="gov-kv-grid">
            <div className="gov-kv-label">Predicted Delay (mins)</div>
            <div className="gov-kv-value">{res.predicted_delay_mins}</div>
            <div className="gov-kv-label">Train Impact Score</div>
            <div className="gov-kv-value">{res.train_impact_score}</div>
            <div className="gov-kv-label">Affected Train Count</div>
            <div className="gov-kv-value">{res.affected_train_count}</div>
            <div className="gov-kv-label">Impact Level</div>
            <div className="gov-kv-value">{res.impact_level}</div>
            <div className="gov-kv-label">Model Version</div>
            <div className="gov-kv-value">{res.model_version}</div>
            <div className="gov-kv-label">Artifact</div>
            <div className="gov-kv-value" style={{ fontFamily: "var(--font-mono)", fontSize: "0.82rem" }}>{res.artifact_filename}</div>
          </div>
          {res.disclaimer ? <div className="gov-info-box">{res.disclaimer}</div> : null}
        </ResultBox>
      ) : null}
    </div>
  );
}

function AssetForm() {
  const [cat, setCat] = useState<Record<string, string>>({
    region: "North",
    season: "Winter",
    train_type: "Express",
    ballast_condition: "Good",
    signal_system_status: "Normal",
  });
  const [num, setNum] = useState<Record<string, number>>({ ...ASSET_RISK_NUMERIC_DEFAULTS });
  const [reqId, setReqId] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [res, setRes] = useState<AssetRiskResult | null>(null);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (loading) return;
    setError(null);
    setRes(null);
    setLoading(true);
    try {
      const payload: Record<string, unknown> = { ...cat };
      for (const k of ASSET_RISK_NUMERIC_FIELDS) payload[k] = num[k];
      if (reqId.trim() !== "") payload.maintenance_request_id = Number(reqId);
      const r = await api.post<AssetRiskResult>("/api/ml/predict/asset-risk", payload);
      setRes(r);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Unable to connect to the railway service. Please try again.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="gov-card">
      <div className="gov-section-header">
        <h3 className="gov-section-title">Asset Risk Prediction</h3>
      </div>
      <form onSubmit={onSubmit}>
        <div className="gov-form-grid">
          {Object.entries(ASSET_RISK_CATEGORICAL).map(([k, opts]) => (
            <div key={k}>
              <label className="gov-label" htmlFor={`ar-${k}`}>{k} <span className="gov-required">*</span></label>
              <select id={`ar-${k}`} className="gov-select" value={cat[k]} onChange={(e) => setCat((p) => ({ ...p, [k]: e.target.value }))}>
                {opts.map((o) => <option key={o} value={o}>{o}</option>)}
              </select>
            </div>
          ))}
          {ASSET_RISK_NUMERIC_FIELDS.map((k) => (
            <div key={k}>
              <label className="gov-label" htmlFor={`ar-n-${k}`}>{k} <span className="gov-required">*</span></label>
              <input
                id={`ar-n-${k}`}
                className="gov-input"
                type="number"
                step="any"
                value={num[k]}
                onChange={(e) => setNum((p) => ({ ...p, [k]: Number(e.target.value) }))}
                required
              />
            </div>
          ))}
        </div>
        <RequestIdInput value={reqId} onChange={setReqId} />
        {error ? <div className="gov-alert gov-alert-error" role="alert">{error}</div> : null}
        <div className="gov-form-actions">
          <button className="gov-btn" type="submit" disabled={loading}>{loading ? "Predicting…" : "Run Asset Risk Prediction"}</button>
        </div>
      </form>
      {res ? (
        <ResultBox title="Asset Risk Prediction Result" variant="accent">
          <div className="gov-kv-grid">
            <div className="gov-kv-label">Asset Risk Score</div>
            <div className="gov-kv-value">{res.asset_risk_score}</div>
            <div className="gov-kv-label">Risk Level</div>
            <div className="gov-kv-value">{res.risk_level}</div>
            <div className="gov-kv-label">Predicted Class</div>
            <div className="gov-kv-value">{res.predicted_class}</div>
            <div className="gov-kv-label">Model Version</div>
            <div className="gov-kv-value">{res.model_version}</div>
            <div className="gov-kv-label">Artifact</div>
            <div className="gov-kv-value" style={{ fontFamily: "var(--font-mono)", fontSize: "0.82rem" }}>{res.artifact_filename}</div>
          </div>
          {res.disclaimer ? <div className="gov-info-box">{res.disclaimer}</div> : null}
        </ResultBox>
      ) : null}
    </div>
  );
}

function DurationForm() {
  const [mtype, setMtype] = useState("Track Tamping");
  const [priority, setPriority] = useState("HIGH");
  const [workers, setWorkers] = useState(5);
  const [equipment, setEquipment] = useState(2);
  const [reqId, setReqId] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [res, setRes] = useState<DurationResult | null>(null);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (loading) return;
    setError(null);
    setRes(null);
    setLoading(true);
    try {
      const payload: Record<string, unknown> = {
        maintenance_type: mtype,
        priority,
        workers,
        equipment_count: equipment,
      };
      if (reqId.trim() !== "") payload.maintenance_request_id = Number(reqId);
      const r = await api.post<DurationResult>("/api/ml/predict/maintenance-duration", payload);
      setRes(r);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Unable to connect to the railway service. Please try again.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="gov-card gov-card-warning">
      <div className="gov-section-header">
        <h3 className="gov-section-title">Maintenance Duration Prediction</h3>
        <span className="gov-badge gov-badge-amber">Demo/Synthetic Model</span>
      </div>
      <div className="gov-alert gov-alert-warning" role="status">
        This duration model uses a demo adapter with synthetic data. It is <strong>NOT</strong> a production-trained model and must not be used for operational decisions.
      </div>
      <form onSubmit={onSubmit}>
        <div className="gov-form-grid">
          <div>
            <label className="gov-label" htmlFor="md-type">Maintenance Type <span className="gov-required">*</span></label>
            <input id="md-type" className="gov-input" value={mtype} onChange={(e) => setMtype(e.target.value)} required />
          </div>
          <div>
            <label className="gov-label" htmlFor="md-prio">Priority <span className="gov-required">*</span></label>
            <select id="md-prio" className="gov-select" value={priority} onChange={(e) => setPriority(e.target.value)}>
              <option value="LOW">LOW</option>
              <option value="MEDIUM">MEDIUM</option>
              <option value="HIGH">HIGH</option>
              <option value="CRITICAL">CRITICAL</option>
            </select>
          </div>
          <div>
            <label className="gov-label" htmlFor="md-workers">Workers (1–100) <span className="gov-required">*</span></label>
            <input id="md-workers" className="gov-input" type="number" min={1} max={100} value={workers} onChange={(e) => setWorkers(Number(e.target.value))} required />
          </div>
          <div>
            <label className="gov-label" htmlFor="md-eq">Equipment Count (0–50) <span className="gov-required">*</span></label>
            <input id="md-eq" className="gov-input" type="number" min={0} max={50} value={equipment} onChange={(e) => setEquipment(Number(e.target.value))} required />
          </div>
        </div>
        <RequestIdInput value={reqId} onChange={setReqId} />
        {error ? <div className="gov-alert gov-alert-error" role="alert">{error}</div> : null}
        <div className="gov-form-actions">
          <button className="gov-btn" type="submit" disabled={loading}>{loading ? "Predicting…" : "Run Duration Prediction"}</button>
        </div>
      </form>
      {res ? (
        <ResultBox title="Duration Prediction Result" variant="warning">
          <div className="gov-alert gov-alert-warning" role="status" style={{ marginBottom: 12 }}>
            <strong>Demo/Synthetic Output</strong> — This result is produced by a non-production adapter and is for demonstration purposes only.
          </div>
          <div className="gov-kv-grid">
            <div className="gov-kv-label">Predicted Duration (mins)</div>
            <div className="gov-kv-value">{res.predicted_duration_mins}</div>
            <div className="gov-kv-label">Model Version</div>
            <div className="gov-kv-value">{res.model_version}</div>
            <div className="gov-kv-label">Artifact</div>
            <div className="gov-kv-value" style={{ fontFamily: "var(--font-mono)", fontSize: "0.82rem" }}>{res.artifact_filename}</div>
          </div>
          {res.demo_label ? (
            <div className="gov-alert gov-alert-warning" role="status">{res.demo_label}</div>
          ) : null}
          {res.disclaimer ? <div className="gov-info-box">{res.disclaimer}</div> : null}
        </ResultBox>
      ) : null}
    </div>
  );
}

function HistoryView() {
  const [reqId, setReqId] = useState("");
  const [rows, setRows] = useState<PredictionRecord[] | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function onLoad(e: React.FormEvent) {
    e.preventDefault();
    if (loading) return;
    const v = reqId.trim();
    if (v === "") return;
    // Backend contract: GET /api/ml/predictions/{request_id} takes the
    // numeric MaintenanceRequest.id only. Request codes (REQ-…) are not
    // valid path values (FastAPI rejects non-int with 422), so catch that
    // here with a specific message instead of firing a doomed request.
    if (!/^\d+$/.test(v)) {
      setRows(null);
      setError("Enter the numeric maintenance request ID (for example 1289) — request codes such as REQ-… are not accepted by this lookup. The numeric ID appears in the request details page URL.");
      return;
    }
    setError(null);
    setLoading(true);
    try {
      const r = await api.get<PredictionRecord[]>(`/api/ml/predictions/${v}`);
      setRows(r);
    } catch (err) {
      setRows(null);
      setError(err instanceof ApiError ? err.message : "Unable to connect to the railway service. Please try again.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="gov-card">
      <div className="gov-section-header">
        <h3 className="gov-section-title">Prediction History by Maintenance Request</h3>
      </div>
      <form onSubmit={onLoad}>
        <div className="gov-filter-bar">
          <div style={{ flex: 1, minWidth: 200 }}>
            <label className="gov-label" htmlFor="hist-req">Maintenance Request ID <span className="gov-required">*</span></label>
            <input id="hist-req" className="gov-input" inputMode="numeric" value={reqId} onChange={(e) => setReqId(e.target.value)} required />
            <span className="gov-hint">Numeric database ID only (e.g. 1289) — see the ID in the request details page URL. Request codes are not accepted here.</span>
          </div>
          <button className="gov-btn gov-btn-sm" type="submit" disabled={loading}>
            {loading ? "Loading…" : "Load History"}
          </button>
        </div>
      </form>
      {error ? <div className="gov-alert gov-alert-error" role="alert">{error}</div> : null}
      {rows && rows.length === 0 ? (
        <div className="gov-empty">
          <p className="gov-muted">No predictions recorded for this request.</p>
        </div>
      ) : null}
      {rows && rows.length > 0 ? (
        <div className="gov-table-wrap" style={{ marginTop: 12 }}>
          <table className="gov-table">
            <thead>
              <tr>
                <th>ID</th>
                <th>Model</th>
                <th>Delay</th>
                <th>Duration</th>
                <th>Risk</th>
                <th>At</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => (
                <tr key={r.id}>
                  <td>{r.id}</td>
                  <td>{r.model_version ?? "—"}</td>
                  <td>{r.predicted_delay_mins ?? "—"}</td>
                  <td>{r.predicted_duration_mins ?? "—"}</td>
                  <td>{r.asset_risk_score ?? r.risk_level ?? "—"}</td>
                  <td>{r.predicted_at ? new Date(r.predicted_at).toLocaleString() : "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : null}
    </div>
  );
}
