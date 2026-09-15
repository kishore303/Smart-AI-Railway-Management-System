import sys
from pathlib import Path

backend_dir = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(backend_dir))

from sqlalchemy import text
from app.database import engine


def test_connection():
    with engine.connect() as conn:
        assert conn.execute(text("SELECT 1")).scalar() == 1


def test_postgis_enabled():
    with engine.connect() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS postgis"))
        ver = conn.execute(text("SELECT postgis_version()")).scalar()
        assert ver is not None
        print(f"PostGIS version: {ver}")


def test_public_tables_nonempty():
    with engine.connect() as conn:
        count = conn.execute(
            text("SELECT count(*) FROM information_schema.tables WHERE table_schema='public' AND table_type='BASE TABLE'")
        ).scalar()
        assert count >= 28, f"Expected >=28 tables, got {count}"


if __name__ == "__main__":
    test_connection()
    print("test_connection OK")
    test_postgis_enabled()
    print("test_postgis_enabled OK")
    test_public_tables_nonempty()
    print("test_public_tables_nonempty OK")
    print("All connection tests passed")
