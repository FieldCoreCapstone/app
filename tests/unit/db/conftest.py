"""Per-test SQLite fixture for backend.models.database unit tests.

These tests exercise the DB helper functions directly (no Flask client),
so we just need an initialized empty schema in a tmp_path.
"""

import pytest

from backend.scripts.init_db import init_db


@pytest.fixture
def db(tmp_path):
    db_path = str(tmp_path / "test.db")
    init_db(db_path)
    return db_path
