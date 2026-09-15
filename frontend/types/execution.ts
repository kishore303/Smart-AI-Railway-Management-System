export interface Allocation {
  id: number;
  block_id: number;
  resource_id: number;
  resource_code?: string;
  quantity_required: number;
  allocated_from: string;
  allocated_until: string;
  status: string;
}

export interface ExecutionDetail {
  optimized_block_id: number;
  block_code: string;
  status: string;
  section_id: number;
  track_id: number | null;
  start_time: string | null;
  end_time: string | null;
  department_code: string | null;
  is_eligible_for_start: boolean;
  eligibility_reasons: string[];
  safety_status: string | null;
  optimization_score: number | null;
  allocated_resources: Allocation[];
  audit_history: {
    action: string;
    user_id: number | null;
    description: string | null;
    created_at: string | null;
  }[];
}

export interface ResourceItem {
  id: number;
  resource_code: string;
  name: string | null;
  department_code: string | null;
  resource_type: string | null;
  quantity: number;
  is_available: boolean;
}

export interface ResourceListResponse {
  total: number;
  items: ResourceItem[];
}

export interface AvailabilityResult {
  resource_id: number;
  resource_code: string;
  is_available: boolean;
  conflicting_allocation: number | null;
  reason: string;
}

export interface ExecutionHistoryResponse {
  optimized_block_id: number;
  block_code: string;
  status: string;
  history: {
    action: string;
    user_id: number | null;
    description: string | null;
    created_at: string | null;
  }[];
  allocations: {
    id: number;
    resource_id: number;
    status: string;
    allocated_from: string;
    allocated_until: string;
  }[];
}

export function executionBadgeKind(status: string): "green" | "amber" | "red" | "blue" {
  if (status === "APPROVED" || status === "ACTIVE" || status === "COMPLETED" || status === "ACCEPTED" || status === "ALLOCATED" || status === "AVAILABLE") return "green";
  if (status === "REJECTED" || status === "CANCELLED" || status === "FAILED") return "red";
  return "amber";
}
