import type { MaintenanceRequest } from "@/types/maintenance";

export type ReviewActionValue = "VERIFY" | "REJECT" | "REVISION_REQUIRED";

export interface ReviewActionPayload {
  action: ReviewActionValue;
  reason?: string | null;
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

export interface ReviewQueueResponse {
  total: number;
  items: MaintenanceRequest[];
  skip: number;
  limit: number;
}
