export type MaintenancePriority = "LOW" | "MEDIUM" | "HIGH" | "CRITICAL";

export interface MaintenanceRequest {
  id: number;
  request_code: string;
  asset_id: number;
  department_id: number;
  department_code: string;
  requested_by: number;
  section_id: number;
  track_id: number | null;
  maintenance_type: string;
  description: string | null;
  priority: string;
  requested_start: string;
  requested_end: string;
  requested_duration_mins: number | null;
  status: string;
  reviewed_by: number | null;
  reviewed_at: string | null;
  rejection_reason: string | null;
  revision_notes: string | null;
  created_at: string | null;
  updated_at: string | null;
}

export interface MaintenanceListResponse {
  total: number;
  items: MaintenanceRequest[];
  skip: number;
  limit: number;
}

export interface MaintenanceCreatePayload {
  asset_id: number;
  section_id: number;
  track_id?: number | null;
  maintenance_type: string;
  description?: string | null;
  priority: MaintenancePriority;
  requested_start: string;
  requested_end: string;
}

export interface ReviewHistoryItem {
  id: number;
  action: string;
  user_id: number | null;
  user_name: string | null;
  user_role: string | null;
  old_status: string | null;
  new_status: string | null;
  description: string | null;
  created_at: string | null;
}

export function statusBadgeKind(status: string): "green" | "amber" | "red" | "blue" {
  if (["VERIFIED", "APPROVED", "COMPLETED"].includes(status)) return "green";
  if (["REJECTED", "REVISION_REQUIRED", "CANCELLED"].includes(status)) return "red";
  if (["DRAFT"].includes(status)) return "blue";
  return "amber";
}

export interface MaintenanceAreaOut {
  id: number;
  maintenance_request_id: number;
  section_id: number;
  track_id: number;
  start_km: number;
  end_km: number;
  length_km: number;
  defined_by: number;
  defined_by_name: string | null;
  created_at: string;
  updated_at: string;
}

export interface MaintenanceAreaCreate {
  section_id: number;
  track_id: number;
  start_km: number;
  end_km: number;
}

export interface MaintenanceAreaUpdate {
  start_km?: number;
  end_km?: number;
}
