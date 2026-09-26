import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.database import engine
from sqlalchemy import text

with engine.connect() as conn:
    conn.execute(text("ALTER TABLE block_candidates DROP CONSTRAINT IF EXISTS block_candidates_safety_status_check;"))
    conn.execute(text("ALTER TABLE block_candidates DROP CONSTRAINT IF EXISTS block_candidates_safety_check;"))
    conn.execute(text("ALTER TABLE block_candidates ADD CONSTRAINT block_candidates_safety_check CHECK (safety_status IN ('FEASIBLE', 'INFEASIBLE', 'SAFE', 'UNSAFE'));"))
    conn.commit()
    print("Successfully updated block_candidates safety_status check constraint in PostgreSQL")
