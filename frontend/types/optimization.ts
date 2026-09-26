export interface OptimizationConfig {
  max_delay_minutes: number;
  priority_weight: number;
  solver_timeout_seconds: number;
}

export interface OptimizedSlot {
  block_candidate_id: number;
  start_time: string;
  end_time: string;
  score: number;
}
