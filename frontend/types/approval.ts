export interface PendingApprovalItem {
  optimized_block_id: number;
  block_code: string;
  status: string;
  created_at: string | null;
  is_eligible_for_approval: boolean;
  eligibility_reasons: string[];
  maintenance_request: {
    id: number | null;
    request_code: string;
    department: string;
    requester_id: number | null;
    requester_name: string;
    maintenance_type: string;
    priority: string;
    description: string;
    requested_start: string | null;
    requested_end: string | null;
    requested_duration_mins: number;
    workflow_status: string;
  };
  ownership: {
    primary_department: string;
    participating_departments: string[];
    is_integrated: boolean;
  };
  asset: {
    id: number | null;
    asset_code: string;
    asset_type: string;
    name: string;
    health_score: number;
    criticality: string;
  };
  ai_predictions: {
    operational_risk: string;
    risk_probability: number;
    predicted_duration_mins: number;
    affected_train_count: number;
    total_predicted_delay_mins: number;
    avg_predicted_delay_mins: number;
    max_predicted_delay_mins: number;
    model_metadata: {
      train_delay_model: string;
      asset_risk_model: string;
      duration_model: string;
      version: string;
      prediction_status: string;
      predicted_at: string | null;
    };
  };
  affected_trains: Array<{
    train_id: number;
    train_number: string;
    train_name: string;
    section_code: string;
    scheduled_time: string;
    predicted_delay_mins: number;
    impact_status: string;
    alternative_route_available: boolean;
  }>;
  safety_validation: {
    overall_status: string;
    is_safe_for_optimization: boolean;
    checks: Record<string, string>;
    rejection_reasons: string[];
    warnings: string[];
    validated_at: string | null;
  };
  candidate_comparison: {
    recommended_candidate_id: number | null;
    safe_alternatives: Array<{
      candidate_id: number;
      window: string;
      duration_mins: number;
      affected_train_count: number;
      predicted_delay_mins: number;
      safety_status: string;
      optimization_score: number | null;
      is_selected: boolean;
      rejection_reason?: string;
    }>;
    rejected_candidates: Array<{
      candidate_id: number;
      window: string;
      duration_mins: number;
      affected_train_count: number;
      predicted_delay_mins: number;
      safety_status: string;
      optimization_score: number | null;
      is_selected: boolean;
      rejection_reason: string;
    }>;
  };
  optimization: {
    recommended_window: string;
    start_time: string | null;
    end_time: string | null;
    duration_mins: number;
    solver_status: string;
    optimization_score: number;
    objective_breakdown: {
      train_delay_penalty: number;
      affected_trains_penalty: number;
      duration_penalty: number;
      maintenance_priority_benefit: number;
      coordination_bonus: number;
      resource_synergy_bonus: number;
    };
    explanation: string;
    config_version: string;
  };
  cross_department: {
    is_coordinated: boolean;
    participating_departments: string[];
    integrations: Array<{
      integration_id: number;
      source_department: string;
      target_department: string;
      compatibility_status: string;
      overlap_duration_mins: number;
      final_status: string;
    }>;
  };
  resources: {
    allocations: Array<{
      allocation_id: number;
      resource_id: number;
      resource_name: string;
      resource_type: string;
      quantity: number;
      status: string;
      is_available: boolean;
    }>;
    has_conflicts: boolean;
  };
  map_context: {
    section_id: number;
    section_code: string;
    section_name: string;
    track_id: number | null;
    track_code: string;
    start_km: number;
    end_km: number;
    geojson: unknown;
  };
  decision: {
    current_status: string;
    approved_by: number | null;
    approved_at: string | null;
    modified_by: number | null;
    modified_at: string | null;
    rejected_by: number | null;
    rejected_at: string | null;
    rejection_reason: string | null;
    history: Array<{
      action: string;
      user_id: number;
      old_status: string | null;
      new_status: string | null;
      description: string | null;
      created_at: string | null;
    }>;
  };
}

export interface OfficialDecisionPayload {
  reason?: string;
  new_candidate_id?: number;
  new_start_time?: string;
  new_end_time?: string;
  proposed_changes?: string;
}

export interface DecisionResult {
  optimized_block_id: number;
  block_code: string;
  decision: "APPROVED" | "MODIFIED" | "REJECTED";
  previous_status: string;
  new_status: string;
  reason?: string;
  decided_by: number;
  decided_at: string;
  requires_revalidation: boolean;
  requires_reoptimization: boolean;
}
