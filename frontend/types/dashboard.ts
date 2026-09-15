export interface DashboardOverview {
  generated_at: string;
  user: { id: number; role: string; department_id: number };
  maintenance_requests: { total: number; pending_review: number; verified: number };
  block_planning: { block_requests: number; candidates: number; optimized_blocks: number; approved: number; active: number };
  safety: { total_validations: number; safe: number };
  integration: { total: number; pending: number };
  resources: { total: number; allocated: number };
  notifications: { unread: number };
  audit: { total: number; recent: Array<{ action: string; entity_type: string | null; created_at: string }> };
  simulation: { total: number };
  principle: string;
}

export interface DashboardHealth {
  status: string;
  checks: Record<string, string>;
  timestamp: string;
}
