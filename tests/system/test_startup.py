"""System tests for start.sh and the env-var configuration paths.

These tests subprocess out to bash for start.sh shape verification, and
exercise the env-var-driven config reload paths in-process for the
FIELDCORE_DB / FLASK_DEBUG / CORS_ORIGINS knobs.
"""

import importlib
import sqlite3
import subprocess
from pathlib import Path

import pytest

pytestmark = pytest.mark.system

APP_ROOT = Path(__file__).resolve().parents[2]
START_SH = APP_ROOT / "start.sh"


class TestStartSh:
    def test_help_flag_exits_zero(self):
        result = subprocess.run(
            ["bash", str(START_SH), "--help"],
            capture_output=True,
            text=True,
            cwd=str(APP_ROOT),
            timeout=10,
        )
        assert result.returncode == 0
        assert "Usage" in result.stdout

    def test_help_flag_documents_seed_test_prod(self):
        result = subprocess.run(
            ["bash", str(START_SH), "--help"],
            capture_output=True,
            text=True,
            cwd=str(APP_ROOT),
            timeout=10,
        )
        for flag in ("--seed", "--test", "--prod"):
            assert flag in result.stdout, f"--help should document {flag}"


class TestFieldcoreDbEnvVar:
    def test_custom_db_path_is_used(self, tmp_path, monkeypatch):
        custom = tmp_path / "custom.db"
        monkeypatch.setenv("FIELDCORE_DB", str(custom))

        from backend import config
        importlib.reload(config)
        assert config.DATABASE_PATH == str(custom)

        from backend.scripts.init_db import init_db
        init_db(str(custom))
        assert custom.exists()

    def test_init_db_creates_expected_tables(self, tmp_path):
        db_path = str(tmp_path / "schema.db")
        from backend.scripts.init_db import init_db
        init_db(db_path)
        conn = sqlite3.connect(db_path)
        try:
            tables = {
                r[0]
                for r in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                ).fetchall()
            }
        finally:
            conn.close()
        assert {"nodes", "readings"}.issubset(tables)

    def test_init_db_is_idempotent(self, tmp_path):
        """Running init_db on an existing DB does not error or drop data."""
        db_path = str(tmp_path / "idem.db")
        from backend.scripts.init_db import init_db
        init_db(db_path)

        conn = sqlite3.connect(db_path)
        conn.execute(
            "INSERT INTO nodes (id, name, latitude, longitude) VALUES (1, 'A', 0, 0)"
        )
        conn.commit()
        conn.close()

        init_db(db_path)  # second call must not raise or drop

        conn = sqlite3.connect(db_path)
        try:
            count = conn.execute("SELECT COUNT(*) FROM nodes").fetchone()[0]
        finally:
            conn.close()
        assert count == 1


class TestFlaskDebugEnvVar:
    def test_debug_on_when_env_is_one(self, monkeypatch):
        monkeypatch.setenv("FLASK_DEBUG", "1")
        from backend import config
        importlib.reload(config)
        assert config.DEBUG is True

    def test_debug_off_when_env_is_zero(self, monkeypatch):
        monkeypatch.setenv("FLASK_DEBUG", "0")
        from backend import config
        importlib.reload(config)
        assert config.DEBUG is False

    def test_debug_off_when_env_missing(self, monkeypatch):
        monkeypatch.delenv("FLASK_DEBUG", raising=False)
        from backend import config
        importlib.reload(config)
        assert config.DEBUG is False


class TestCorsOriginsEnvVar:
    def test_prod_mode_only_allows_listed_origin(self, tmp_path, monkeypatch):
        """In non-debug mode, the configured CORS origin is the only one allowed."""
        db_path = str(tmp_path / "cors.db")
        monkeypatch.setenv("FIELDCORE_DB", db_path)
        monkeypatch.setenv("FLASK_DEBUG", "0")
        monkeypatch.setenv("CORS_ORIGINS", "https://example.com")

        from backend import config
        importlib.reload(config)
        from backend.scripts.init_db import init_db
        init_db(db_path)

        import app as app_module
        importlib.reload(app_module)
        flask_app = app_module.create_app()
        flask_app.config["TESTING"] = True

        with flask_app.test_client() as c:
            # Request from the allowed origin → header echoes it.
            resp = c.get("/api/health", headers={"Origin": "https://example.com"})
            assert resp.status_code == 200
            assert resp.headers.get("Access-Control-Allow-Origin") == "https://example.com"

            # Request from a different origin → header missing or doesn't match.
            resp = c.get("/api/health", headers={"Origin": "https://evil.example"})
            allow = resp.headers.get("Access-Control-Allow-Origin")
            assert allow != "https://evil.example"
