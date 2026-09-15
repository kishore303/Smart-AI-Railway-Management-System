"use client";

import React, { useState } from "react";
import dynamic from "next/dynamic";
import ProtectedRoute from "@/components/ProtectedRoute";
import AppShell from "@/components/AppShell";
import Breadcrumbs from "@/components/Breadcrumbs";
import type { FeatureProperties } from "@/types/spatial";

// MapLibre GL is a browser-only WebGL library. Loading it client-side keeps
// the large native dependency out of the server bundle (Next 14 server
// chunking emits a dangling vendor-chunk require for it otherwise).
const RailwayMap = dynamic(() => import("@/components/RailwayMap"), {
  ssr: false,
  loading: () => <div className="gov-loading" style={{ height: 600 }}>Loading geographic data…</div>,
});

export default function MapPage() {
  return (
    <ProtectedRoute>
      <AppShell>
        <MapContent />
      </AppShell>
    </ProtectedRoute>
  );
}

function MapContent() {
  const [selected, setSelected] = useState<FeatureProperties | null>(null);

  return (
    <div className="gov-page">
      <Breadcrumbs trail={[{ label: "Dashboard", href: "/dashboard" }, { label: "Railway Network Map" }]} />
      <h1 className="gov-title">Railway Network Map</h1>
      <p className="gov-sub">
        Real geographic data from PostGIS database — stations, sections, tracks, assets, resources, and incidents.
      </p>

      <div className="gov-card">
        <RailwayMap
          height={600}
          onSelect={setSelected}
          selectedId={selected && "id" in selected ? (selected as unknown as { id: number }).id : null}
        />
      </div>

      {selected ? (
        <div className="gov-card" style={{ marginTop: 16 }}>
          <h2>Selected Feature</h2>
          <dl className="gov-meta">
            <dt>Layer</dt>
            <dd>{selected.layer}</dd>
            {"code" in selected && <><dt>Code</dt><dd>{String((selected as unknown as { code: string }).code)}</dd></>}
            {"name" in selected && <><dt>Name</dt><dd>{String((selected as unknown as { name: string }).name)}</dd></>}
            {"id" in selected && <><dt>ID</dt><dd>{String((selected as unknown as { id: number }).id)}</dd></>}
            {"status" in selected && <><dt>Status</dt><dd>{String((selected as unknown as { status: string }).status)}</dd></>}
          </dl>
        </div>
      ) : null}
    </div>
  );
}
