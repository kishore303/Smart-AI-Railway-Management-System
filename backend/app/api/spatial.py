from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import text
from app.database import get_db
from app.core.rbac import get_current_active_user
from app.models.user import User

router = APIRouter(prefix="/api/spatial", tags=["spatial"])


def _to_geojson_feature(row, geometry_json, props):
    return {
        "type": "Feature",
        "geometry": geometry_json,
        "properties": props,
    }


@router.get("/geojson")
def get_geojson(
    layer: str = "all",
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    features = []
    valid_layers = {"stations", "sections", "tracks", "assets", "resources", "incidents"}

    with db.bind.connect() as conn:
        if layer in ("all", "stations"):
            rows = conn.execute(text("""
                SELECT id, name, code, zone, latitude, longitude,
                       ST_AsGeoJSON(location)::json as geojson
                FROM stations WHERE location IS NOT NULL
            """)).fetchall()
            for r in rows:
                features.append(_to_geojson_feature(
                    r, r[6],
                    {"layer": "station", "id": r[0], "name": r[1], "code": r[2], "zone": r[3],
                      "latitude": float(r[4]) if r[4] else None, "longitude": float(r[5]) if r[5] else None},
                ))

        if layer in ("all", "sections"):
            rows = conn.execute(text("""
                SELECT rs.id, rs.section_code, rs.name, rs.distance_km, rs.number_of_tracks,
                       ss.name as start_name, es.name as end_name,
                       ST_AsGeoJSON(rs.geometry)::json as geojson
                FROM railway_sections rs
                LEFT JOIN stations ss ON rs.start_station_id = ss.id
                LEFT JOIN stations es ON rs.end_station_id = es.id
                WHERE rs.geometry IS NOT NULL
            """)).fetchall()
            for r in rows:
                features.append(_to_geojson_feature(
                    r, r[7],
                    {"layer": "section", "id": r[0], "code": r[1], "name": r[2],
                     "distance_km": float(r[3]) if r[3] else None, "tracks": r[4],
                     "start_station": r[5], "end_station": r[6]},
                ))

        if layer in ("all", "tracks"):
            rows = conn.execute(text("""
                SELECT t.id, t.track_code, t.track_name, t.direction, t.status, t.section_id,
                       ST_AsGeoJSON(t.geometry)::json as geojson
                FROM tracks t
                WHERE t.geometry IS NOT NULL
            """)).fetchall()
            for r in rows:
                features.append(_to_geojson_feature(
                    r, r[6],
                    {"layer": "track", "id": r[0], "code": r[1], "name": r[2],
                     "direction": r[3], "status": r[4], "section_id": r[5]},
                ))

        if layer in ("all", "assets"):
            rows = conn.execute(text("""
                SELECT a.id, a.asset_code, a.name, a.asset_type, a.status, a.condition_score,
                       a.section_id, a.department_id,
                       ST_AsGeoJSON(a.location)::json as geojson
                FROM assets a
                WHERE a.location IS NOT NULL
            """)).fetchall()
            for r in rows:
                features.append(_to_geojson_feature(
                    r, r[8],
                    {"layer": "asset", "id": r[0], "code": r[1], "name": r[2],
                     "type": r[3], "status": r[4],
                     "condition_score": float(r[5]) if r[5] else None,
                     "section_id": r[6], "department_id": r[7]},
                ))

        if layer in ("all", "resources"):
            rows = conn.execute(text("""
                SELECT r.id, r.resource_code, r.name, r.resource_type, r.quantity, r.is_available,
                       d.code as dept_code,
                       ST_AsGeoJSON(r.location)::json as geojson
                FROM resources r
                LEFT JOIN departments d ON r.department_id = d.id
                WHERE r.location IS NOT NULL
            """)).fetchall()
            for r in rows:
                features.append(_to_geojson_feature(
                    r, r[7],
                    {"layer": "resource", "id": r[0], "code": r[1], "name": r[2],
                     "type": r[3], "quantity": r[4], "available": r[5], "department": r[6]},
                ))

        if layer in ("all", "incidents"):
            rows = conn.execute(text("""
                SELECT i.id, i.incident_code, i.incident_type, i.severity, i.response_status,
                       i.latitude, i.longitude,
                       ST_AsGeoJSON(i.location)::json as geojson
                FROM incidents i
                WHERE i.location IS NOT NULL
            """)).fetchall()
            for r in rows:
                features.append(_to_geojson_feature(
                    r, r[7],
                    {"layer": "incident", "id": r[0], "code": r[1], "type": r[2],
                     "severity": r[3], "status": r[4],
                     "latitude": float(r[5]) if r[5] else None, "longitude": float(r[6]) if r[6] else None},
                ))

    return {
        "type": "FeatureCollection",
        "features": features,
        "count": len(features),
        "layers": list(valid_layers),
    }


@router.get("/stations")
def list_stations_geojson(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    features = []
    with db.bind.connect() as conn:
        rows = conn.execute(text("""
            SELECT id, name, code, zone, latitude, longitude,
                   ST_AsGeoJSON(location)::json as geojson
            FROM stations WHERE location IS NOT NULL
        """)).fetchall()
        for r in rows:
            features.append(_to_geojson_feature(
                r, r[6],
                {"id": r[0], "name": r[1], "code": r[2], "zone": r[3],
                 "latitude": float(r[4]) if r[4] else None, "longitude": float(r[5]) if r[5] else None},
            ))
    return {"type": "FeatureCollection", "features": features, "count": len(features)}


@router.get("/sections")
def list_sections_geojson(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    features = []
    with db.bind.connect() as conn:
        rows = conn.execute(text("""
            SELECT rs.id, rs.section_code, rs.name, rs.distance_km, rs.number_of_tracks,
                   ss.name as start_name, es.name as end_name,
                   ST_AsGeoJSON(rs.geometry)::json as geojson
            FROM railway_sections rs
            LEFT JOIN stations ss ON rs.start_station_id = ss.id
            LEFT JOIN stations es ON rs.end_station_id = es.id
            WHERE rs.geometry IS NOT NULL
        """)).fetchall()
        for r in rows:
            features.append(_to_geojson_feature(
                r, r[7],
                {"id": r[0], "code": r[1], "name": r[2], "distance_km": float(r[3]) if r[3] else None,
                 "tracks": r[4], "start_station": r[5], "end_station": r[6]},
            ))
    return {"type": "FeatureCollection", "features": features, "count": len(features)}
