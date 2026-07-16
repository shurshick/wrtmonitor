import os
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]

os.environ.setdefault("PYTHONPATH", str(REPO_ROOT))
os.environ.setdefault(
    "WRTMONITOR_DATABASE_URL",
    "postgresql+psycopg://wrtmonitor:local-test-password@localhost:5432/wrtmonitor_test",
)
os.environ.setdefault("WRTMONITOR_ALLOW_INSECURE_LOCAL", "true")
os.environ.setdefault("WRTMONITOR_ALLOW_INSECURE_DEV_DEFAULTS", "true")
os.environ.setdefault(
    "WRTMONITOR_JWT_SECRET",
    "local-test-secret-value-with-more-than-32-characters",
)
os.environ.setdefault("WRTMONITOR_SKIP_E2E", "1")
