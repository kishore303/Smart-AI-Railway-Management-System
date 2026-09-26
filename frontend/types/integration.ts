export interface IntegrationRequest {
  id: number;
  source_block_id: number;
  target_block_id: number;
  source_block_code?: string | null;
  target_block_code?: string | null;
  requesting_department_id: number;
  requesting_department_code: string;
  target_department_id: number;
  target_department_code: string;
  section_id?: number | null;
  track_id?: number | null;
  overlap_start?: string | null;
  overlap_end?: string | null;
  overlap_duration_mins: number | null;
  coordination_score?: number | null;
  detection_reason?: string | null;
  spatial_status?: string | null;
  compatibility_status: string | null;
  requested_by: number;
  response_by: number | null;
  response: string | null;
  reason: string | null;
  modified_start?: string | null;
  modified_end?: string | null;
  final_status: string;
  created_at: string | null;
  updated_at?: string | null;
}

export interface IntegrationListResponse {
  total: number;
  items: IntegrationRequest[];
  skip: number;
  limit: number;
}

export interface OpportunityDetectResponse {
  detected_count: number;
  opportunities: IntegrationRequest[];
}

export type IntegrationResponse = "ACCEPT" | "REJECT" | "MODIFY";

export function integrationBadgeKind(status: string): "green" | "amber" | "red" | "blue" {
  if (status === "ACCEPTED") return "green";
  if (status === "REJECTED") return "red";
  if (status === "PENDING" || status === "MODIFIED") return "amber";
  return "blue";
}

export function compatibilityNote(status: string | null): string {
  if (status === "COMPATIBLE" || status === "POTENTIAL_COMPATIBLE") {
    return "Planning-level compatibility only — Safety Engine validation still required. Compatibility is not safety approval.";
  }
  if (status === "POTENTIALLY_COMPATIBLE") {
    return "Potentially compatible at planning level — requires further review and Safety Engine validation.";
  }
  if (status === "INSUFFICIENT_DATA") {
    return "Location or asset data is incomplete. Further data required before safety assessment.";
  }
  return "Requires Safety Engine validation before any joint planning decision.";
}

