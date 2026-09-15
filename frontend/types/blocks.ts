export interface BlockRequest {
  id: number;
  block_code: string;
  maintenance_request_id: number;
  section_id: number;
  track_id: number | null;
  requested_start: string;
  requested_end: string;
  duration_mins: number | null;
  block_type: string | null;
  status: string;
  created_at: string | null;
}

export interface BlockRequestListResponse {
  total: number;
  items: BlockRequest[];
  skip: number;
  limit: number;
}

export interface Candidate {
  id: number;
  block_request_id: number;
  section_id: number;
  track_id: number | null;
  candidate_start: string;
  candidate_end: string;
  predicted_duration_mins: number | null;
  predicted_delay_mins: number | null;
  asset_risk_score: number | null;
  safety_status: string;
  safety_rejection_reason: string | null;
  optimization_score: number | null;
  is_selected: boolean;
  created_at: string | null;
}

export interface CandidateGenerateResponse {
  generated: number;
  candidates: Candidate[];
  message: string;
}

export function planningBadgeKind(status: string): "green" | "amber" | "red" | "blue" {
  if (status === "FEASIBLE") return "green";
  if (status === "INFEASIBLE") return "red";
  return "amber";
}
