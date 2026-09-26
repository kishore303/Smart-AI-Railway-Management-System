"""Seed minimal synthetic railway data for Module 4 tests — clearly labelled SYNTHETIC."""
import sys
from pathlib import Path
from datetime import date

backend_dir = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(backend_dir))

from app.database import SessionLocal
from app.models.department import Department
from app.models.station import Station
from app.models.railway import RailwaySection, Track
from app.models.asset import Asset
from app.models.resource import Resource
from geoalchemy2.elements import WKTElement

db = SessionLocal()

def get_or_create_station(code, name, lat, lon):
    existing = db.query(Station).filter(Station.code == code).first()
    if existing:
        return existing
    s = Station(name=name, code=code, zone="NR", latitude=lat, longitude=lon, location=WKTElement(f"POINT({lon} {lat})", srid=4326))
    db.add(s)
    db.flush()
    print(f"Created station {code}")
    return s

def get_or_create_section(code, name, start_id, end_id):
    existing = db.query(RailwaySection).filter(RailwaySection.section_code == code).first()
    if existing:
        return existing
    sec = RailwaySection(section_code=code, name=name, start_station_id=start_id, end_station_id=end_id, distance_km=10.5, max_speed_kmph=110, number_of_tracks=2)
    db.add(sec)
    db.flush()
    print(f"Created section {code}")
    return sec

def get_or_create_track(section_id, track_code, track_name):
    existing = db.query(Track).filter(Track.section_id == section_id, Track.track_code == track_code).first()
    if existing:
        return existing
    t = Track(section_id=section_id, track_code=track_code, track_name=track_name, direction="UP", track_type="MAIN", status="ACTIVE")
    db.add(t)
    db.flush()
    print(f"Created track {track_code} in section {section_id}")
    return t

def get_or_create_asset(asset_code, name, asset_type, dept_code, section_id, track_id):
    existing = db.query(Asset).filter(Asset.asset_code == asset_code).first()
    if existing:
        return existing
    dept = db.query(Department).filter(Department.code == dept_code).first()
    a = Asset(asset_code=asset_code, name=name, asset_type=asset_type, department_id=dept.id, section_id=section_id, track_id=track_id, condition_score=75.0, asset_health_score=80.0, status="ACTIVE", installation_date=date(2020,1,15))
    db.add(a)
    db.flush()
    print(f"Created asset {asset_code}")
    return a

def get_or_create_resource(code, name, dept_code, rtype):
    existing = db.query(Resource).filter(Resource.resource_code == code).first()
    if existing:
        return existing
    dept = db.query(Department).filter(Department.code == dept_code).first()
    r = Resource(resource_code=code, name=name, department_id=dept.id, resource_type=rtype, quantity=5, is_available=True)
    db.add(r)
    db.flush()
    print(f"Created resource {code}")
    return r

try:
    s1 = get_or_create_station("SYN001", "SYN Station Alpha", 28.6139, 77.2090)
    s2 = get_or_create_station("SYN002", "SYN Station Beta", 28.7041, 77.1025)
    s3 = get_or_create_station("SYN003", "SYN Station Gamma", 28.5355, 77.3910)
    sec1 = get_or_create_section("SYN-SEC-01", "SYN Section 01 (Alpha-Beta)", s1.id, s2.id)
    sec2 = get_or_create_section("SYN-SEC-02", "SYN Section 02 (Beta-Gamma)", s2.id, s3.id)
    t1 = get_or_create_track(sec1.id, "T1", "Track 1 UP")
    t2 = get_or_create_track(sec1.id, "T2", "Track 2 DOWN")
    t3 = get_or_create_track(sec2.id, "T1", "Track 1 UP")
    a1 = get_or_create_asset("SYN-AST-001", "SYN Track Asset 001", "Track", "ENG", sec1.id, t1.id)
    a2 = get_or_create_asset("SYN-AST-002", "SYN OHE Asset 002", "OHE", "ELEC", sec1.id, t1.id)
    a3 = get_or_create_asset("SYN-AST-003", "SYN Signal Asset 003", "Signal", "SNT", sec1.id, t1.id)
    a4 = get_or_create_asset("SYN-AST-004", "SYN Track Asset 004", "Track", "ENG", sec1.id, t2.id)
    a5 = get_or_create_asset("SYN-AST-005", "SYN Signal Asset 005", "Signal", "SNT", sec2.id, t3.id)
    a6 = get_or_create_asset("SYN-AST-006", "SYN OHE Asset 006", "OHE", "ELEC", sec2.id, t3.id)
    r1 = get_or_create_resource("SYN-RES-001", "SYN Track Machine", "ENG", "Track machine")
    r2 = get_or_create_resource("SYN-RES-002", "SYN OHE Staff Crew", "ELEC", "Worker")
    # Additional asset for ELEC
    db.commit()
    print("Seed complete")
    # Summary
    from sqlalchemy import text
    with db.bind.connect() as conn:
        for tbl in ["stations","railway_sections","tracks","assets","resources"]:
            cnt = conn.execute(text(f"SELECT count(*) FROM {tbl}")).scalar()
            print(f"{tbl}: {cnt}")
finally:
    db.close()
