export interface SafetyCheck {
  check: string;
  status: string;
  reason: string;
  severity: string;
  warning?: string;
}

export interface SafetyValidationResult {
  candidate_id: number;
  block_request_id: number;
  overall_status: string;
  is_safe_for_optimization: boolean;
  checks: SafetyCheck[];
  rejection_reasons: string[];
  warnings: string[];
  validated_by: number | null;
  validated_at: string | null;
  planning_safety_status?: string | null;
  disclaimer?: string;
}

export interface SafetyValidationSummary {
  id: number;
  candidate_id: number;
  block_request_id: number;
  overall_status: string;
  is_safe_for_optimization: boolean;
  validated_by: number | null;
  validated_at: string | null;
}

export interface BlockCandidateValidation {
  candidate_id: number;
  candidate_start: string;
  candidate_end: string;
  planning_safety_status: string;
  safety_validation: {
    overall_status: string | null;
    is_safe_for_optimization: boolean | null;
    checks: SafetyCheck[] | null;
    rejection_reasons: string[] | null;
  } | null;
  validated: boolean;
  is_selected: boolean;
  optimization_score: number | null;
}

export interface BlockValidationsResponse {
  block_id: number;
  total: number;
  validations: BlockCandidateValidation[];
}

export const SAFETY_CHECK_ORDER: string[] = [
  "TIMING",
  "TRACK_CONFLICT",
  "SECTION_CONFLICT",
  "TRAIN_CONFLICT",
  "ADJACENT_FOULING",
  "RESOURCE_CONFLICT",
  "MAINTENANCE_COMPATIBILITY",
  "PROTECTION_REQUIREMENT",
  "OPERATIONAL_RESTRICTION",
  "EMERGENCY_RESTRICTION",
];

export function safetyBadgeKind(status: string | null): "green" | "amber" | "red" | "blue" {
  if (status === "SAFE") return "green";
  if (status === "UNSAFE") return "red";
  return "amber";
}

export function checkBadgeKind(status: string): "green" | "amber" | "red" | "blue" {
  if (status === "PASS") return "green";
  if (status === "FAIL") return "red";
  return "amber";
}
