export interface RequestSummary {
  maintenance_request_id: number | null;
  request_code: string | null;
  department_code: string | null;
  asset_id: number | null;
  asset_code: string | null;
  section_id: number | null;
  section_code: string | null;
  track_id: number | null;
  track_code: string | null;
  maintenance_type: string | null;
  priority: string | null;
  requested_start: string | null;
  requested_end: string | null;
  requested_duration_mins: number | null;
}

export interface RecommendationSafetySummary {
  candidate_id: number | null;
  overall_status: string | null;
  is_safe_for_optimization: boolean | null;
  checks: import("./safety").SafetyCheck[] | null;
  rejection_reasons: string[] | null;
  warnings: string[] | null;
  validated_at: string | null;
  validated_by: number | null;
  planning_safety_status: string | null;
}

export interface OptimizationSummary {
  optimization_score: number | null;
  objective_value: number | null;
  objective_summary: Record<string, unknown> | null;
  explanation: string | null;
  solver_status: string | null;
  total_considered: number | null;
  eligible: number | null;
}

export interface AlternativeCandidate {
  candidate_id: number;
  candidate_start: string | null;
  candidate_end: string | null;
  duration_mins: number | null;
  safety_status: string | null;
  safety_overall: string | null;
  is_safe: boolean | null;
  optimization_eligible: boolean;
  predicted_delay: number | null;
  asset_risk: number | null;
  reason_not_selected: string;
}

export interface IntegrationSummary {
  integration_id: number | null;
  source_block: string | null;
  target_block: string | null;
  requesting_dept: string | null;
  target_dept: string | null;
  compatibility_status: string | null;
  overlap_mins: number | null;
  final_status: string | null;
}

export interface DecisionHistoryEntry {
  action: string;
  user_id: number | null;
  description: string | null;
  created_at: string | null;
}

export interface Recommendation {
  optimized_block_id: number;
  block_code: string;
  status: string;
  is_eligible_for_approval: boolean;
  eligibility_reasons: string[];
  request_summary: RequestSummary;
  safety_summary: RecommendationSafetySummary;
  optimization_summary: OptimizationSummary;
  selected_recommendation: {
    candidate_id: number | null;
    candidate_start: string | null;
    candidate_end: string | null;
    predicted_duration_mins: number | null;
    predicted_delay_mins: number | null;
    asset_risk_score: number | null;
    optimization_score: number | null;
    is_selected: boolean | null;
  } | null;
  alternatives: AlternativeCandidate[];
  integration_summary: IntegrationSummary[];
  warnings: string[];
  decision_status: string;
  decision_history: DecisionHistoryEntry[];
}

export interface OptimizeRunResult {
  block_request_id?: number;
  optimized_block_id?: number | null;
  optimized_block_code?: string | null;
  status: string;
  reason?: string | null;
  selected_candidate_id?: number | null;
  optimization_score?: number | null;
  objective_value?: number | null;
  objective_summary?: Record<string, unknown> | null;
  total_considered?: number | null;
  eligible?: number | null;
  unsafe_excluded?: number | null;
  excluded_details?: { candidate_id: number; reason: string }[];
  explanation?: string | null;
  disclaimer?: string;
}

export interface LatestOptimization {
  optimized_block_id: number;
  block_code: string;
  section_id: number;
  track_id: number | null;
  start_time: string | null;
  end_time: string | null;
  optimization_score: number | null;
  status: string;
  combined_departments: string[] | null;
  recommendation_reason: string | null;
  created_at: string | null;
}

export interface OptimizationHistoryResponse {
  block_request_id: number;
  total: number;
  history: {
    optimized_block_id: number;
    block_code: string;
    optimization_score: number | null;
    status: string;
    created_at: string | null;
  }[];
}

export interface OfficialDecisionResponse {
  optimized_block_id: number;
  new_status: string;
  decision: string;
  reason: string | null;
  decided_by: number;
  decided_at: string;
  requires_revalidation: boolean;
  requires_reoptimization: boolean;
}

export function decisionBadgeKind(status: string): "green" | "amber" | "red" | "blue" {
  if (status === "APPROVED" || status === "SAFE") return "green";
  if (status === "REJECTED" || status === "UNSAFE" || status === "FAILED") return "red";
  return "amber";
}
