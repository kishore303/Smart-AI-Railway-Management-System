export type IncidentType =
  | 'ACCIDENT'
  | 'DERAILMENT_RELATED'
  | 'TRACK_FAILURE'
  | 'SIGNAL_FAILURE'
  | 'OHE_FAILURE'
  | 'OBSTRUCTION'
  | 'PERSON_ON_TRACK'
  | 'SUSPECTED_SUICIDE'
  | 'RAIL_FRACTURE'
  | 'SIGNAL_BLANKING'
  | 'OHE_BREAKDOWN'
  | 'BOULDER_FALL'
  | 'LEVEL_CROSSING_GATE_FAILURE'
  | 'TRACK_OBSTRUCTION'
  | 'EQUIPMENT_MALFUNCTION'
  | 'OTHER_EMERGENCY';

export type IncidentSeverity = 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL';

export type IncidentStatus =
  | 'REPORTED'
  | 'ACKNOWLEDGED'
  | 'ASSESSED'
  | 'EMERGENCY_PLANNING'
  | 'AWAITING_OFFICIAL_DECISION'
  | 'APPROVED'
  | 'RESPONSE_DISPATCHED'
  | 'ON_SITE'
  | 'WORK_IN_PROGRESS'
  | 'CLEARANCE_PENDING'
  | 'CLEARED'
  | 'RELEASED'
  | 'INCIDENT_CLOSED'
  | 'REJECTED';

export type ResponseStatus = 'OPEN' | 'IN_PROGRESS' | 'CLEARED' | 'CLOSED';

export interface EmergencyResponseRecord {
  id: number;
  authority_type: string;
  authority_name?: string;
  team_name?: string;
  notification_time?: string;
  acknowledgement_time?: string;
  arrival_time?: string;
  work_start_time?: string;
  completion_time?: string;
  clearance_time?: string;
  status: string;
  notes?: string;
  assigned_resources?: string;
}

export interface IncidentRecord {
  id: number;
  incident_code: string;
  incident_type: IncidentType | string;
  severity: IncidentSeverity;
  description?: string;
  section_id?: number;
  section_name?: string;
  track_id?: number;
  track_number?: string;
  asset_id?: number;
  latitude?: number;
  longitude?: number;
  status: IncidentStatus;
  response_status: ResponseStatus;
  reported_at: string;
  reported_by?: number;
  reporter_name?: string;
  railway_alert_status?: string;
  police_alert_status?: string;
  acknowledged_at?: string;
  acknowledged_by?: number;
  assessed_at?: string;
  assessed_by?: number;
  assessment_notes?: string;
  block_request_id?: number;
  block_code?: string;
  selected_optimized_block_id?: number;
  clearance_time?: string;
  cleared_at?: string;
  cleared_by?: number;
  clearance_notes?: string;
  closed_at?: string;
  closed_by?: number;
  is_simulated: boolean;
  responses: EmergencyResponseRecord[];
}

export interface AffectedTrainImpact {
  affected_train_count: number;
  total_predicted_delay_minutes: number;
  average_predicted_delay_minutes: number;
  maximum_predicted_delay_minutes: number;
  train_impact_score: number;
  impact_level: string;
  individual_predictions: Array<{
    train_number: string;
    train_name: string;
    station_code: string;
    station_name: string;
    predicted_delay_mins: number;
    impact_level: string;
    scheduled_entry?: string;
  }>;
}

export interface ConflictingBlock {
  block_request_id: number;
  block_code: string;
  status: string;
  track_id?: number;
  direct_track_conflict: boolean;
  start_time: string;
  end_time: string;
  recommendation: string;
  reason: string;
}

export interface EmergencyResource {
  resource_id: string;
  resource_type: string;
  name: string;
  depot_location: string;
  eta_minutes: number;
  status: string;
  contact: string;
}

export interface EmergencyCandidate {
  candidate_id: number;
  label: string;
  start: string;
  end: string;
  duration_mins: number;
  predicted_delay_mins: number;
  affected_train_count: number;
  safety_status: 'SAFE' | 'UNSAFE' | 'FEASIBLE';
  is_safe_for_optimization: boolean;
  rejection_reasons?: string[];
  warnings?: string[];
}

export interface EmergencyKPIs {
  total_incidents: number;
  active_incidents: number;
  in_planning: number;
  awaiting_official_decision: number;
  approved: number;
  work_in_progress: number;
  cleared_or_released: number;
  closed: number;
}
