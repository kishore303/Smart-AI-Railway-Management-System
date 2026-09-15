import type { SafetyCheck } from "./safety";

export interface DigitalTwinSnapshot {
  snapshot_at: string;
  sections: number;
  tracks: number;
  stations: number;
  assets: number;
  maintenance_requests: number;
  block_requests: number;
  block_candidates: number;
  optimized_blocks: number;
  resources: number;
  trains: number;
  incidents: number;
  active_blocks_sample: {
    block_code: string;
    status: string;
    start_time: string;
  }[];
  note: string;
}

export interface ScenarioPoint {
  start_time: string | null;
  end_time: string | null;
  duration: number | null;
  safety: string | null;
  optimization_score: number | null;
  feasibility?: string | null;
}

export interface WhatIfSafety {
  candidate_id: number;
  block_request_id: number;
  overall_status: string;
  is_safe_for_optimization: boolean;
  checks: SafetyCheck[];
  rejection_reasons: string[];
  warnings: string[];
  validated_at: string;
}

export interface WhatIfResult {
  simulation_id: number;
  original_block_id: number;
  scenario: ScenarioPoint;
  baseline: ScenarioPoint;
  safety: WhatIfSafety;
  feasibility: string;
  optimization_score: number | null;
  warnings: string[];
  rejection_reasons: string[];
  is_safe: boolean;
  comparison: {
    baseline_start: string | null;
    scenario_start: string | null;
    baseline_duration: number | null;
    scenario_duration: number | null;
    baseline_safety: string | null;
    scenario_safety: string | null;
  };
  disclaimer: string;
}

export interface SimulationRecord {
  id: number;
  simulation_name: string | null;
  original_block_id: number | null;
  modified_start_time: string | null;
  modified_end_time: string | null;
  additional_department_id: number | null;
  predicted_delay_mins: number | null;
  optimization_score: number | null;
  result_summary: string | null;
  created_at: string | null;
  created_by: number | null;
}

export interface SimulationHistoryResponse {
  total: number;
  items: {
    id: number;
    simulation_name: string | null;
    original_block_id: number | null;
    created_at: string | null;
  }[];
  skip: number;
  limit: number;
}

export function feasibilityBadgeKind(v: string | null): "green" | "amber" | "red" | "blue" {
  if (v === "SAFE" || v === "FEASIBLE" || v === "SUCCESS" || v === "COMPLETED") return "green";
  if (v === "UNSAFE" || v === "INFEASIBLE" || v === "FAILED") return "red";
  return "amber";
}
