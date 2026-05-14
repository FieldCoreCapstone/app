"""Unit tests for backend.models.database.get_db context manager."""

import sqlite3

import pytest

from backend.models.database import get_db

pytestmark = pytest.mark.unit


class TestGetDb:
    def test_yields_working_connection(self, db):
        with get_db(db) as conn:
            assert conn.execute("SELECT 1").fetchone()[0] == 1

    def test_wal_journal_mode_enabled(self, db):
        with get_db(db) as conn:
            mode = conn.execute("PRAGMA journal_mode").fetchone()[0]
            assert mode.lower() == "wal"

    def test_foreign_keys_enabled(self, db):
        with get_db(db) as conn:
            fk = conn.execute("PRAGMA foreign_keys").fetchone()[0]
            assert fk == 1

    def test_row_factory_is_row(self, db):
        with get_db(db) as conn:
            conn.execute(
                "INSERT INTO nodes (id, name, latitude, longitude) VALUES (1, 'A', 0, 0)"
            )
            conn.commit()
            row = conn.execute("SELECT name FROM nodes WHERE id = 1").fetchone()
            # sqlite3.Row supports both index and key access
            assert row["name"] == "A"

    def test_uncommitted_changes_rollback_on_exception(self, db):
        """If the context body raises, uncommitted writes must not persist."""
        with pytest.raises(RuntimeError):
            with get_db(db) as conn:
                conn.execute(
                    "INSERT INTO nodes (id, name, latitude, longitude) VALUES (99, 'X', 0, 0)"
                )
                # Note: no commit — the rollback in the except branch should fire.
                raise RuntimeError("simulated failure")

        # Reopen and confirm nothing persisted.
        with get_db(db) as conn:
            row = conn.execute("SELECT id FROM nodes WHERE id = 99").fetchone()
            assert row is None

    def test_connection_closed_after_context(self, db):
        with get_db(db) as conn:
            pass
        # Operating on the closed connection raises ProgrammingError.
        with pytest.raises(sqlite3.ProgrammingError):
            conn.execute("SELECT 1")
