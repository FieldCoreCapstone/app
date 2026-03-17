"""Shared test fixtures for FieldCore."""

import importlib

from backend import config
from backend.scripts.init_db import init_db

import pytest


@pytest.fixture
def client(tmp_path, monkeypatch):
    """Create a Flask test client backed by an isolated temporary database."""
    db_path = str(tmp_path / "test.db")
    monkeypatch.setenv("FIELDCORE_DB", db_path)

    # Reload config so all modules see the new DB path
    importlib.reload(config)

    init_db(db_path)

    # Import app after config reload so blueprints use the right DB
    import app as app_module
    importlib.reload(app_module)
    flask_app = app_module.create_app()
    flask_app.config["TESTING"] = True

    with flask_app.test_client() as c:
        yield c
