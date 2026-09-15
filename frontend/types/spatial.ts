export interface GeoJsonFeature {
  type: "Feature";
  geometry: {
    type: string;
    coordinates: number[] | number[][] | number[][][];
  } | null;
  properties: Record<string, unknown>;
}

export interface GeoJsonCollection {
  type: "FeatureCollection";
  features: GeoJsonFeature[];
  count: number;
  layers: string[];
}

export interface StationFeature {
  layer: "station";
  id: number;
  name: string;
  code: string;
  zone: string | null;
  latitude: number | null;
  longitude: number | null;
}

export interface SectionFeature {
  layer: "section";
  id: number;
  code: string;
  name: string;
  distance_km: number | null;
  tracks: number;
  start_station: string;
  end_station: string;
}

export interface TrackFeature {
  layer: "track";
  id: number;
  code: string;
  name: string;
  direction: string;
  status: string;
  section_id: number;
}

export interface AssetFeature {
  layer: "asset";
  id: number;
  code: string;
  name: string;
  type: string;
  status: string;
  condition_score: number | null;
  section_id: number;
  department_id: number;
}

export interface ResourceFeature {
  layer: "resource";
  id: number;
  code: string;
  name: string;
  type: string;
  quantity: number;
  available: boolean;
  department: string;
}

export interface IncidentFeature {
  layer: "incident";
  id: number;
  code: string;
  type: string;
  severity: string;
  status: string;
  latitude: number | null;
  longitude: number | null;
}

export type FeatureProperties =
  | StationFeature
  | SectionFeature
  | TrackFeature
  | AssetFeature
  | ResourceFeature
  | IncidentFeature;

export const LAYER_COLORS: Record<string, string> = {
  station: "#0f265c",
  section: "#1e40af",
  track: "#059669",
  asset: "#d97706",
  resource: "#7c3aed",
  incident: "#dc2626",
};

export const LAYER_LABELS: Record<string, string> = {
  station: "Stations",
  section: "Railway Sections",
  track: "Tracks",
  asset: "Assets",
  resource: "Resources",
  incident: "Incidents",
};
