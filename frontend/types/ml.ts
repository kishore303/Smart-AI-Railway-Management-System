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
  model_version: string;
  artifact_filename: string;
  is_demo: boolean;
  input_features: Record<string, unknown>;
  persisted_id?: number | null;
  disclaimer?: string;
}

export type AssetRiskFeatures = Record<string, string | number>;

export interface AssetRiskResult {
  asset_risk_score: number;
  risk_level: string;
  predicted_class: number;
  model_version: string;
  artifact_filename: string;
  is_demo: boolean;
  input_features: Record<string, unknown>;
  persisted_id?: number | null;
  disclaimer?: string;
}

export interface DurationFeatures {
  maintenance_type: string;
  priority: "LOW" | "MEDIUM" | "HIGH" | "CRITICAL";
  workers: number;
  equipment_count: number;
}

export interface DurationResult {
  predicted_duration_mins: number;
  model_version: string;
  artifact_filename: string;
  is_demo: boolean;
  demo_label?: string;
  input_features: Record<string, unknown>;
  dataset_rows?: number | null;
  dataset_columns?: string[] | null;
  persisted_id?: number | null;
  disclaimer?: string;
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
  input_features: Record<string, unknown> | null;
  predicted_at: string | null;
}

export interface ModelRegistryEntry {
  model_type: string;
  version: string;
  artifact_filename: string;
  is_demo: boolean;
  is_active: boolean;
  notes: string | null;
}

export const TRAIN_IMPACT_DEFAULTS: TrainImpactFeatures = {
  train_number: 12345,
  train_name: "Test Express",
  station_code: "NDLS",
  station_name: "New Delhi",
  pct_right_time: 70,
  pct_slight_delay: 15,
  pct_significant_delay: 10,
  pct_cancelled_unknown: 5,
};

export const ASSET_RISK_CATEGORICAL: Record<string, string[]> = {
  region: ["North", "South", "East", "West", "Central", "North-East"],
  season: ["Summer", "Monsoon", "Winter"],
  train_type: ["Express", "Freight", "Passenger", "Local"],
  ballast_condition: ["Good", "Average", "Poor"],
  signal_system_status: ["Normal", "Warning", "Failed"],
};

export const ASSET_RISK_NUMERIC_DEFAULTS: Record<string, number> = {
  train_age_years: 10,
  average_speed_kmph: 80,
  distance_travelled_km: 10000,
  track_temperature_c: 30,
  rail_wear_mm: 5,
  track_vibration_level: 2.5,
  track_curvature_degree: 3,
  ambient_temperature_c: 25,
  humidity_percent: 60,
  rainfall_mm: 10,
  wind_speed_kmph: 15,
  wheel_wear_percent: 20,
  axle_temperature_c: 50,
  brake_pressure_psi: 90,
  brake_pad_wear_percent: 30,
  bearing_temperature_c: 60,
  battery_voltage: 110,
  traction_motor_temp_c: 70,
  power_consumption_kw: 500,
  load_factor_percent: 70,
  daily_trips: 3,
  delay_minutes: 10,
  last_maintenance_days: 45,
  inspection_score: 75,
  sensor_health_index: 85,
  risk_score: 0.5,
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
