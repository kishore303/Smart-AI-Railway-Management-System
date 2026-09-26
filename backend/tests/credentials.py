import os
import re
from pathlib import Path

from dotenv import load_dotenv


load_dotenv(Path(__file__).resolve().parents[1] / ".env")


def seeded_password(account_name: str) -> str:
    key = re.sub(r"[^A-Z0-9]+", "_", account_name.upper()).strip("_")
    variable = f"SIH_SEED_PASSWORD_{key}"
    password = os.environ.get(variable)
    if not password:
        raise RuntimeError(f"Required local test credential is missing: {variable}")
    return password