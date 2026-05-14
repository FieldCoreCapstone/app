"""Unit tests for backend.models.database node query helpers."""

import sqlite3

import pytest

from backend.models.database import create_node, get_all_nodes, get_node

pytestmark = pytest.mark.unit


class TestGetAllNodes:
    def test_empty_db_returns_empty_list(self, db):
        assert get_all_nodes(db) == []

    def test_returns_nodes_sorted_by_id(self, db):
        create_node(3, latitude=0, longitude=0, name="C", db_path=db)
        create_node(1, latitude=0, longitude=0, name="A", db_path=db)
        create_node(2, latitude=0, longitude=0, name="B", db_path=db)
        rows = get_all_nodes(db)
        assert [r["node_id"] for r in rows] == [1, 2, 3]

    def test_response_uses_node_id_alias_not_raw_id(self, db):
        """Wire field is `node_id`; raw `id` must not leak."""
        create_node(1, latitude=0, longitude=0, name="A", db_path=db)
        row = get_all_nodes(db)[0]
        assert "node_id" in row
        assert "id" not in row

    def test_returns_full_column_set(self, db):
        create_node(
            1,
            latitude=37.42,
            longitude=-91.56,
            name="A",
            installed="2026-01-01",
            notes="hello",
            db_path=db,
        )
        row = get_all_nodes(db)[0]
        for key in ("node_id", "name", "latitude", "longitude", "installed", "notes"):
            assert key in row


class TestGetNode:
    def test_returns_dict_when_exists(self, db):
        create_node(1, latitude=0, longitude=0, name="A", db_path=db)
        row = get_node(1, db)
        assert row is not None
        assert row["node_id"] == 1
        assert row["name"] == "A"

    def test_returns_none_when_missing(self, db):
        assert get_node(999, db) is None


class TestCreateNode:
    def test_inserts_and_returns_row(self, db):
        row = create_node(1, latitude=37.4, longitude=-91.5, name="A", db_path=db)
        assert row["node_id"] == 1
        assert row["name"] == "A"
        assert row["latitude"] == 37.4
        assert row["longitude"] == -91.5

    def test_default_name_is_field_id(self, db):
        """Omitting `name` derives `field_{node_id}`."""
        row = create_node(7, latitude=0, longitude=0, db_path=db)
        assert row["name"] == "field_7"

    def test_duplicate_id_raises_integrity_error(self, db):
        create_node(1, latitude=0, longitude=0, name="A", db_path=db)
        with pytest.raises(sqlite3.IntegrityError):
            create_node(1, latitude=0, longitude=0, name="B", db_path=db)

    def test_keyword_only_args_prevent_coord_swap(self, db):
        """create_node's positional-arg lockdown stops accidental lat/lng swaps."""
        with pytest.raises(TypeError):
            # Old-style positional call should now fail because everything
            # after node_id is keyword-only.
            create_node(1, 37.4, -91.5)  # type: ignore[misc]
