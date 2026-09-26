export interface AnalyticsOverviewKPIs {
  total_maintenance_requests: number;
  total_block_requests: number;
  active_blocks: number;
  approved_blocks: number;
  completed_blocks: number;
  avg_block_duration_mins: number;
  total_affected_trains: number;
  total_predicted_delay_mins: number;
  avg_predicted_delay_mins: number;
  total_assets: number;
  high_risk_assets: number;
  avg_asset_condition: number;
  total_resources: number;
  active_resource_allocations: number;
  coordination_requests: number;
  accepted_coordinations: number;
  total_incidents: number;
  open_incidents: number;
  total_optimizations: number;
  avg_optimization_score: number;
}

export interface AnalyticsOverviewResponse {
  timestamp: string;
  kpis: AnalyticsOverviewKPIs;
}

export interface BlockAnalyticsResponse {
  status_distribution: Record<string, number>;
  department_distribution: Array<{ department: string; code: string; count: number }>;
  duration_distribution: Record<string, number>;
}

export interface TrainImpactAnalyticsResponse {
  section_delay_impact: Array<{
    section: string;
    code: string;
    block_count: number;
    affected_trains: number;
    total_delay_mins: number;
    avg_delay_mins: number;
  }>;
  train_fleet_composition: Record<string, number>;
}

export interface AssetAnalyticsResponse {
  health_distribution: Record<string, number>;
  type_summary: Array<{ type: string; count: number; avg_condition: number | null }>;
  high_risk_assets: Array<{
    id: number;
    code: string;
    name: string;
    type: string;
    condition_score: number;
    section: string;
  }>;
}

export interface ResourceAnalyticsResponse {
  resource_types: Array<{ type: string; distinct_items: number; total_units: number }>;
  allocations_by_status: Record<string, number>;
  department_resources: Array<{ department: string; items: number; units: number }>;
}

export interface CoordinationAnalyticsResponse {
  integration_status_distribution: Record<string, number>;
  department_coordination_pairs: Array<{ requesting: string; target: string; count: number }>;
}

export interface EmergencyAnalyticsResponse {
  incident_types: Record<string, number>;
  severity_distribution: Record<string, number>;
  workflow_status_distribution: Record<string, number>;
}

export interface OptimizationAnalyticsResponse {
  candidate_safety_gate_distribution: Record<string, number>;
  score_statistics: {
    min_score: number;
    max_score: number;
    avg_score: number;
  };
  solver_engine: string;
}

export interface ModelAnalyticsResponse {
  models: Record<string, {
    model_key: string;
    verified: boolean;
    md5: string;
    size_bytes: number;
    status: string;
  }>;
  evaluation_metrics: Record<string, any>;
  notice: string;
}
