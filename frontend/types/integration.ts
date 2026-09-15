export interface IntegrationRequest {
  id: number;
  source_block_id: number;
  target_block_id: number;
  requesting_department_id: number;
  requesting_department_code: string;
  target_department_id: number;
  target_department_code: string;
  overlap_duration_mins: number | null;
  compatibility_status: string | null;
  requested_by: number;
  response_by: number | null;
  response: string | null;
  reason: string | null;
  final_status: string;
  created_at: string | null;
}

export interface IntegrationListResponse {
  total: number;
  items: IntegrationRequest[];
  skip: number;
  limit: number;
}

export type IntegrationResponse = "ACCEPT" | "REJECT" | "MODIFY";

export function integrationBadgeKind(status: string): "green" | "amber" | "red" | "blue" {
  if (status === "ACCEPTED") return "green";
  if (status === "REJECTED") return "red";
  if (status === "PENDING" || status === "MODIFIED") return "amber";
  return "blue";
}

export function compatibilityNote(status: string | null): string {
  if (status === "COMPATIBLE") {
    return "Planning-level compatibility only — Safety Engine validation still required. Compatibility is not safety approval.";
  }
  if (status === "POTENTIALLY_COMPATIBLE") {
    return "Potentially compatible at planning level — requires further review and Safety Engine validation.";
  }
  return "Requires Safety Engine validation before any joint planning decision.";
}
