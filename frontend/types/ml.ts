export interface TrainImpactFeatures {
  train_number: number;
  train_name: string;
  station_code: string;
  station_name: string;
  pct_right_time: number;
  pct_slight_delay: number;
  pct_significant_delay: number;
  pct_cancelled_unknown: number;
}

export interface TrainImpactResult {
  predicted_delay_mins: number;
  train_impact_score: number;
  affected_train_count: number;
  impact_level: string;
  model_name?: string;
  model_version: string;
  artifact_filename?: string;
  is_demo?: boolean;
  input_features?: Record<string, unknown>;
  persisted_id?: number | null;
  disclaimer?: string;
}

export type AssetRiskFeatures = Record<string, string | number>;

export interface AssetRiskResult {
  asset_risk_score: number;
  risk_level: string;
  risk_class?: number;
  risk_probability?: number;
  predicted_class?: number;
  model_name?: string;
  model_version: string;
  artifact_filename?: string;
  is_demo?: boolean;
  input_features?: Record<string, unknown>;
  persisted_id?: number | null;
  disclaimer?: string;
}

export interface DurationFeatures {
  maintenance_type: string;
  department?: string;
  asset_type?: string;
  complexity?: string;
  priority: "LOW" | "MEDIUM" | "HIGH" | "CRITICAL";
  workers: number;
  equipment_count: number;
  asset_age_years?: number;
  condition_score?: number;
  previous_duration_min?: number;
}

export interface DurationResult {
  predicted_duration_minutes: number;
  predicted_duration_mins: number;
  model_name?: string;
  model_version: string;
  artifact_filename?: string;
  is_demo: boolean;
  input_features?: Record<string, unknown>;
  persisted_id?: number | null;
  disclaimer?: string;
}

export interface AffectedTrainItem {
  train_number: number;
  train_name: string;
  station_code: string;
  station_name: string;
  section_id: number;
  track_id?: number | null;
  scheduled_entry?: string | null;
  scheduled_exit?: string | null;
  predicted_delay_mins: number;
  impact_level: string;
  impact_reason?: string | null;
}

export interface TrainImpactAssessment {
  affected_train_count: number;
  total_predicted_delay_minutes: number;
  average_predicted_delay_minutes: number;
  maximum_predicted_delay_minutes: number;
  train_impact_score: number;
  impact_level: string;
  individual_predictions: AffectedTrainItem[];
  model_name: string;
  model_version: string;
}

export interface UnifiedPredictionResult {
  status: string;
  prediction_id: number;
  maintenance_request_id: number;
  is_stale: boolean;
  is_demo?: boolean;
  predicted_at: string;
  duration: {
    predicted_duration_minutes: number;
    predicted_duration_mins?: number;
    confidence_interval_lower_mins?: number;
    confidence_interval_upper_mins?: number;
    model_name: string;
    model_version: string;
  };
  duration_prediction?: {
    predicted_duration_minutes: number;
    predicted_duration_mins?: number;
    confidence_interval_lower_mins?: number;
    confidence_interval_upper_mins?: number;
    model_name: string;
    model_version: string;
  };
  risk: {
    risk_class: number;
    risk_probability: number;
    asset_risk_score: number;
    risk_level: string;
    model_name: string;
    model_version: string;
  };
  risk_prediction?: {
    risk_class: number;
    risk_probability: number;
    asset_risk_score: number;
    risk_level: string;
    model_name: string;
    model_version: string;
  };
  train_impact: TrainImpactAssessment;
  disclaimer: string;
}

export interface PredictionRecord {
  id: number;
  maintenance_request_id: number;
  asset_risk_score: number | null;
  risk_level: string | null;
  predicted_duration_mins: number | null;
  train_impact_score: number | null;
  predicted_delay_mins: number | null;
  affected_train_count: number | null;
  model_version: string | null;
  input_features?: Record<string, unknown> | null;
  predicted_at: string | null;
}

export interface PredictionHistoryResponse {
  maintenance_request_id: number;
  is_stale: boolean;
  total_predictions: number;
  latest_prediction?: PredictionRecord | null;
  history: PredictionRecord[];
}

export interface ModelRegistryEntry {
  model_type: string;
  version: string;
  artifact_filename: string;
  is_demo: boolean;
  is_active: boolean;
  notes: string | null;
  features?: string[];
}

export const TRAIN_IMPACT_DEFAULTS: TrainImpactFeatures = {
  train_number: 12601,
  train_name: "MANGALORE EXP",
  station_code: "MAS",
  station_name: "CHENNAI CENTRAL",
  pct_right_time: 80,
  pct_slight_delay: 15,
  pct_significant_delay: 4,
  pct_cancelled_unknown: 1,
};

export const DURATION_DEFAULTS: DurationFeatures = {
  maintenance_type: "Track Inspection",
  department: "Engineering",
  asset_type: "Track",
  complexity: "Medium",
  priority: "MEDIUM",
  workers: 6,
  equipment_count: 2,
  asset_age_years: 7,
  condition_score: 75.0,
  previous_duration_min: 120,
};

export const ASSET_RISK_CATEGORICAL: Record<string, string[]> = {
  region: ["Northern", "Southern", "Eastern", "Western", "Central", "North-Eastern"],
  season: ["Summer", "Monsoon", "Winter"],
  train_type: ["Express", "Freight", "Passenger", "Local"],
  ballast_condition: ["Good", "Average", "Poor"],
  signal_system_status: ["Normal", "Warning", "Failed"],
};

export const ASSET_RISK_NUMERIC_DEFAULTS: Record<string, number> = {
  train_age_years: 8,
  average_speed_kmph: 75,
  distance_travelled_km: 1500,
  track_temperature_c: 32,
  rail_wear_mm: 2.5,
  track_vibration_level: 1.5,
  track_curvature_degree: 1.2,
  ambient_temperature_c: 28,
  humidity_percent: 60,
  rainfall_mm: 0,
  wind_speed_kmph: 12,
  wheel_wear_percent: 25,
  axle_temperature_c: 50,
  brake_pressure_psi: 72,
  brake_pad_wear_percent: 35,
  bearing_temperature_c: 55,
  battery_voltage: 24,
  traction_motor_temp_c: 60,
  power_consumption_kw: 320,
  load_factor_percent: 70,
  daily_trips: 4,
  delay_minutes: 5,
  last_maintenance_days: 20,
  inspection_score: 85,
  sensor_health_index: 90,
  risk_score: 30,
};

export const ASSET_RISK_NUMERIC_FIELDS: string[] = [
  "train_age_years",
  "average_speed_kmph",
  "distance_travelled_km",
  "track_temperature_c",
  "rail_wear_mm",
  "track_vibration_level",
  "track_curvature_degree",
  "ambient_temperature_c",
  "humidity_percent",
  "rainfall_mm",
  "wind_speed_kmph",
  "wheel_wear_percent",
  "axle_temperature_c",
  "brake_pressure_psi",
  "brake_pad_wear_percent",
  "bearing_temperature_c",
  "battery_voltage",
  "traction_motor_temp_c",
  "power_consumption_kw",
  "load_factor_percent",
  "daily_trips",
  "delay_minutes",
  "last_maintenance_days",
  "inspection_score",
  "sensor_health_index",
  "risk_score",
];
