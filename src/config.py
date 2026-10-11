import os
from pathlib import Path
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / '.env')
AS_OF = '2026-01-01 00:00:00'


def database_url():
    return os.getenv('DATABASE_URL', f"sqlite:///{(ROOT / 'data' / 'supply_chain.db').as_posix()}")


def prepare_dirs():
    for name in ['data/raw', 'data/processed', 'data/rejected', 'models', 'reports', 'logs']:
        (ROOT / name).mkdir(parents=True, exist_ok=True)
