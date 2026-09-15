"use client";

import React, { useEffect, useRef, useState, useCallback } from "react";
import { api, ApiError } from "@/lib/api-client";
import type { GeoJsonCollection, FeatureProperties } from "@/types/spatial";
import { LAYER_COLORS, LAYER_LABELS } from "@/types/spatial";

interface RailwayMapProps {
  layers?: string[];
  height?: number;
  center?: [number, number];
  zoom?: number;
  onSelect?: (feature: FeatureProperties) => void;
  selectedId?: number | null;
  className?: string;
}

// Module-scope defaults: stable identities across renders. Inline array
// literals here would create a new reference on every render, which would
// invalidate the effect dependencies below and cause infinite fetch/map
// recreation loops.
const DEFAULT_LAYERS = ["stations", "sections", "tracks", "assets", "resources", "incidents"];
const DEFAULT_CENTER: [number, number] = [78.9629, 22.5937];
const DEFAULT_ZOOM = 5;

const PLURAL_TO_SINGULAR: Record<string, string> = {
  stations: "station",
  sections: "section",
  tracks: "track",
  assets: "asset",
  resources: "resource",
  incidents: "incident",
};

export default function RailwayMap({
  layers = DEFAULT_LAYERS,
  height = 500,
  center = DEFAULT_CENTER,
  zoom = DEFAULT_ZOOM,
  onSelect,
  selectedId,
  className = "",
}: RailwayMapProps) {
  const mapContainer = useRef<HTMLDivElement>(null);
  const mapRef = useRef<unknown>(null);
  const [data, setData] = useState<GeoJsonCollection | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [activeLayer, setActiveLayer] = useState<string>("all");
  // Destructure to primitives so effect dependencies compare by value.
  // Depending on the `center` array itself would refire on every render
  // because each render creates a new array identity.
  const [centerLng, centerLat] = center;

  const loadGeoJson = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const layerParam = activeLayer === "all" ? "all" : activeLayer;
      const result = await api.get<GeoJsonCollection>(`/api/spatial/geojson?layer=${encodeURIComponent(layerParam)}`);
      setData(result);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Unable to load geographic data.");
    } finally {
      setLoading(false);
    }
    // NOTE: `layers` is intentionally NOT a dependency — it is only used for
    // rendering the layer buttons, never for fetching. Including it caused an
    // infinite fetch loop (new array identity every render → new callback →
    // effect refires → setState → rerender).
  }, [activeLayer]);

  useEffect(() => {
    void loadGeoJson();
  }, [loadGeoJson]);

  useEffect(() => {
    if (!mapContainer.current || !data) return;

    let mapInstance: unknown = null;

    import("maplibre-gl").then((maplibregl) => {
      if (!mapContainer.current) return;

      const map = new maplibregl.Map({
        container: mapContainer.current,
        style: {
          version: 8,
          sources: {
            osm: {
              type: "raster",
              tiles: ["https://tile.openstreetmap.org/{z}/{x}/{y}.png"],
              tileSize: 256,
              attribution: "&copy; OpenStreetMap contributors",
            },
          },
          layers: [{ id: "osm-tiles", type: "raster", source: "osm", minzoom: 0, maxzoom: 19 }],
        },
        center,
        zoom,
      });

      map.addControl(new maplibregl.NavigationControl(), "top-right");
      map.addControl(new maplibregl.ScaleControl(), "bottom-right");

      map.on("load", () => {
        map.addSource("railway-data", {
          type: "geojson",
          data: data as unknown as GeoJSON.FeatureCollection,
        });

        const layersWithData = new Set(data.features.map((f) => f.properties.layer));

        for (const [layerName, color] of Object.entries(LAYER_COLORS)) {
          if (!layersWithData.has(layerName)) continue;

          if (layerName === "section" || layerName === "track") {
            map.addLayer({
              id: `layer-${layerName}`,
              type: "line",
              source: "railway-data",
              filter: ["==", ["get", "layer"], layerName],
              layout: { "line-join": "round", "line-cap": "round" },
              paint: { "line-color": color, "line-width": layerName === "section" ? 3 : 2, "line-opacity": 0.8 },
            });
          } else {
            map.addLayer({
              id: `layer-${layerName}-bg`,
              type: "circle",
              source: "railway-data",
              filter: ["==", ["get", "layer"], layerName],
              paint: {
                "circle-radius": layerName === "incident" ? 10 : 7,
                "circle-color": color,
                "circle-stroke-color": "#fff",
                "circle-stroke-width": 2,
                "circle-opacity": 0.9,
              },
            });
          }

          map.on("click", `layer-${layerName}-bg`, (e: unknown) => {
            const ev = e as { features?: Array<{ properties: Record<string, unknown>; geometry: { coordinates: number[] } }> };
            if (ev.features && ev.features.length > 0) {
              const props = ev.features[0].properties as unknown as FeatureProperties;
              if (onSelect) onSelect(props);

              const coords = ev.features[0].geometry.coordinates;
              new maplibregl.Popup({ offset: 15 })
                .setLngLat([coords[0], coords[1]])
                .setHTML(buildPopupHtml(props))
                .addTo(map);
            }
          });

          if (layerName === "section" || layerName === "track") {
            map.on("click", `layer-${layerName}`, (e: unknown) => {
              const ev = e as { features?: Array<{ properties: Record<string, unknown>; geometry: { coordinates: number[][] } }> };
              if (ev.features && ev.features.length > 0) {
                const props = ev.features[0].properties as unknown as FeatureProperties;
                if (onSelect) onSelect(props);

                const coords = ev.features[0].geometry.coordinates;
                const midIdx = Math.floor(coords.length / 2);
                new maplibregl.Popup({ offset: 15 })
                  .setLngLat([coords[midIdx][0], coords[midIdx][1]])
                  .setHTML(buildPopupHtml(props))
                  .addTo(map);
              }
            });
          }

          map.on("mouseenter", `layer-${layerName}-bg`, () => {
            map.getCanvas().style.cursor = "pointer";
          });
          map.on("mouseleave", `layer-${layerName}-bg`, () => {
            map.getCanvas().style.cursor = "";
          });
        }
      });

      mapInstance = map;
      mapRef.current = map;
    });

    return () => {
      if (mapInstance && typeof (mapInstance as { remove?: () => void }).remove === "function") {
        (mapInstance as { remove: () => void }).remove();
      }
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [data, centerLng, centerLat, zoom, onSelect]);

  useEffect(() => {
    if (selectedId == null || !data || !mapRef.current) return;
    const feature = data.features.find((f) => {
      const p = f.properties;
      return "id" in p && (p as unknown as { id: number }).id === selectedId;
    });
    if (feature && feature.geometry && "coordinates" in feature.geometry) {
      const coords = feature.geometry.coordinates as number[];
      if (coords.length >= 2) {
        (mapRef.current as { flyTo: (opts: { center: number[]; zoom: number }) => void }).flyTo({
          center: [coords[0], coords[1]],
          zoom: 10,
        });
      }
    }
  }, [selectedId, data]);

  const layerCounts: Record<string, number> = {};
  for (const f of data?.features ?? []) {
    const layer = f.properties.layer as string;
    layerCounts[layer] = (layerCounts[layer] || 0) + 1;
  }

  const countForButton = (plural: string): number | undefined => {
    const singular = PLURAL_TO_SINGULAR[plural] ?? plural;
    return layerCounts[singular];
  };

  return (
    <div className={className}>
      <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 8, flexWrap: "wrap" }}>
        <button
          className={`gov-btn ${activeLayer === "all" ? "" : "gov-btn-secondary"}`}
          type="button"
          style={{ padding: "6px 12px", fontSize: 13 }}
          onClick={() => setActiveLayer("all")}
        >
          All Layers
        </button>
        {layers.map((l) => (
          <button
            key={l}
            className={`gov-btn ${activeLayer === l ? "" : "gov-btn-secondary"}`}
            type="button"
            style={{ padding: "6px 12px", fontSize: 13 }}
            onClick={() => setActiveLayer(l)}
          >
            <span style={{ display: "inline-block", width: 10, height: 10, borderRadius: "50%", background: LAYER_COLORS[PLURAL_TO_SINGULAR[l] ?? l], marginRight: 6 }} />
            {LAYER_LABELS[PLURAL_TO_SINGULAR[l] ?? l] || LAYER_LABELS[l] || l}
            {countForButton(l) != null ? ` (${countForButton(l)})` : ""}
          </button>
        ))}
      </div>

      {loading ? (
        <div className="gov-loading" style={{ height }}>Loading geographic data…</div>
      ) : error ? (
        <div className="gov-error" style={{ height }}>{error}</div>
      ) : data && data.features.length === 0 ? (
        <div className="gov-empty" style={{ height }}>
          <div className="gov-empty-icon">🗺</div>
          <p>No geographic data available in the database.</p>
          <p style={{ fontSize: 13, color: "var(--muted)", marginTop: 4 }}>
            Stations, sections, tracks, assets, resources, or incidents with PostGIS coordinates will appear here.
          </p>
        </div>
      ) : null}

      <div
        ref={mapContainer}
        style={{ width: "100%", height, borderRadius: 8, border: "1px solid var(--border)", display: loading || error || (data && data.features.length === 0) ? "none" : "block" }}
      />
    </div>
  );
}

function buildPopupHtml(props: FeatureProperties): string {
  const layer = props.layer;
  let html = `<div style="font-family:Inter,system-ui,sans-serif;font-size:13px;min-width:160px;">`;
  html += `<div style="font-weight:700;margin-bottom:4px;color:#0f265c;text-transform:uppercase;font-size:11px;letter-spacing:0.5px;">${LAYER_LABELS[layer] || layer}</div>`;

  if (layer === "station") {
    const p = props as import("@/types/spatial").StationFeature;
    html += `<div><strong>${p.name}</strong> (${p.code})</div>`;
    if (p.zone) html += `<div style="color:#667085">Zone: ${p.zone}</div>`;
  } else if (layer === "section") {
    const p = props as import("@/types/spatial").SectionFeature;
    html += `<div><strong>${p.name || p.code}</strong></div>`;
    html += `<div style="color:#667085">${p.start_station} → ${p.end_station}</div>`;
    if (p.distance_km) html += `<div style="color:#667085">${p.distance_km} km, ${p.tracks} tracks</div>`;
  } else if (layer === "track") {
    const p = props as import("@/types/spatial").TrackFeature;
    html += `<div><strong>${p.code}</strong> — ${p.name || "Track"}</div>`;
    html += `<div style="color:#667085">${p.direction || "—"} | ${p.status}</div>`;
  } else if (layer === "asset") {
    const p = props as import("@/types/spatial").AssetFeature;
    html += `<div><strong>${p.code}</strong> — ${p.name || p.type}</div>`;
    html += `<div style="color:#667085">Type: ${p.type} | Status: ${p.status}</div>`;
    if (p.condition_score != null) html += `<div style="color:#667085">Condition: ${p.condition_score}%</div>`;
  } else if (layer === "resource") {
    const p = props as import("@/types/spatial").ResourceFeature;
    html += `<div><strong>${p.code}</strong> — ${p.name || p.type}</div>`;
    html += `<div style="color:#667085">Type: ${p.type} | Qty: ${p.quantity} | Dept: ${p.department}</div>`;
  } else if (layer === "incident") {
    const p = props as import("@/types/spatial").IncidentFeature;
    html += `<div><strong>${p.code}</strong></div>`;
    html += `<div style="color:#667085">Type: ${p.type} | Severity: ${p.severity}</div>`;
    html += `<div style="color:#667085">Status: ${p.status}</div>`;
  }

  html += `</div>`;
  return html;
}
