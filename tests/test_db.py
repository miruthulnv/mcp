"""Tests for database layer."""

import sqlite3
from pathlib import Path

import pytest

from notes_mcp.db import (
    create_note,
    delete_note,
    get_connection,
    get_note,
    init_db,
    list_recent_notes,
    list_tags,
    notes_since,
    search_notes,
    update_note,
)


@pytest.fixture
def db_conn(tmp_path: Path):
    db_file = tmp_path / "test_notes.db"
    init_db(db_file)
    conn = get_connection(db_file)
    try:
        yield conn
    finally:
        conn.close()


def test_create_and_get_note(db_conn: sqlite3.Connection) -> None:
    note = create_note(
        db_conn,
        title="First Note",
        content="Hello world",
        tags=["Work", "todo", "WORK", "  "],
    )
    assert note["id"] == 1
    assert note["title"] == "First Note"
    assert note["content"] == "Hello world"
    # Tag normalization: lowercase, trimmed, duplicates and empties removed, sorted
    assert note["tags"] == ["todo", "work"]
    assert note["created_at"] is not None
    assert note["updated_at"] is not None

    fetched = get_note(db_conn, 1)
    assert fetched == note


def test_get_nonexistent_note_returns_none(db_conn: sqlite3.Connection) -> None:
    assert get_note(db_conn, 999) is None


def test_search_notes_and_escaping(db_conn: sqlite3.Connection) -> None:
    create_note(db_conn, title="Discount 100% off", content="Big sale today", tags=["deals"])
    create_note(db_conn, title="Discount 10 dollars off", content="Sale", tags=["deals"])
    create_note(db_conn, title="Special file_name.txt", content="Code file", tags=["code"])
    create_note(db_conn, title="Special filename.txt", content="No underscore", tags=["code"])

    # Search literal '%'
    results_percent = search_notes(db_conn, "100%")
    assert len(results_percent) == 1
    assert results_percent[0]["title"] == "Discount 100% off"

    # Search literal '_'
    results_underscore = search_notes(db_conn, "file_name")
    assert len(results_underscore) == 1
    assert results_underscore[0]["title"] == "Special file_name.txt"

    # Search content case-insensitive
    results_case = search_notes(db_conn, "bIg SaLe")
    assert len(results_case) == 1
    assert results_case[0]["title"] == "Discount 100% off"


def test_list_recent_notes_order(db_conn: sqlite3.Connection) -> None:
    n1 = create_note(db_conn, title="Note 1", content="One")
    n2 = create_note(db_conn, title="Note 2", content="Two")
    n3 = create_note(db_conn, title="Note 3", content="Three")

    recent = list_recent_notes(db_conn, limit=2)
    assert len(recent) == 2
    assert recent[0]["id"] == n3["id"]
    assert recent[1]["id"] == n2["id"]

    all_recent = list_recent_notes(db_conn, limit=10)
    assert [n["id"] for n in all_recent] == [n3["id"], n2["id"], n1["id"]]


def test_update_note(db_conn: sqlite3.Connection) -> None:
    note = create_note(db_conn, title="Old Title", content="Old Content", tags=["tag1", "tag2"])

    # Partial update: title only
    up1 = update_note(db_conn, note["id"], title="New Title")
    assert up1 is not None
    assert up1["title"] == "New Title"
    assert up1["content"] == "Old Content"
    assert up1["tags"] == ["tag1", "tag2"]

    # Partial update: tags only
    up2 = update_note(db_conn, note["id"], tags=["tag3"])
    assert up2 is not None
    assert up2["title"] == "New Title"
    assert up2["tags"] == ["tag3"]

    # Non-existent note returns None
    assert update_note(db_conn, 9999, title="Nope") is None


def test_delete_note_and_cascading(db_conn: sqlite3.Connection) -> None:
    note = create_note(db_conn, title="To Delete", content="Content", tags=["tag1"])
    note_id = note["id"]

    # Tag link exists
    tag_links_before = db_conn.execute(
        "SELECT COUNT(*) as cnt FROM note_tags WHERE note_id = ?",
        (note_id,),
    ).fetchone()["cnt"]
    assert tag_links_before == 1

    # Delete note
    deleted = delete_note(db_conn, note_id)
    assert deleted is True

    # Note no longer exists
    assert get_note(db_conn, note_id) is None

    # Tag link cascaded and was deleted
    tag_links_after = db_conn.execute(
        "SELECT COUNT(*) as cnt FROM note_tags WHERE note_id = ?",
        (note_id,),
    ).fetchone()["cnt"]
    assert tag_links_after == 0

    # Deleting again returns False
    assert delete_note(db_conn, note_id) is False


def test_list_tags_counts(db_conn: sqlite3.Connection) -> None:
    create_note(db_conn, title="N1", content="C", tags=["python", "fastmcp"])
    create_note(db_conn, title="N2", content="C", tags=["python", "docker"])
    create_note(db_conn, title="N3", content="C", tags=["python"])

    tags = list_tags(db_conn)
    # python: 3, docker: 1, fastmcp: 1
    assert tags == [
        {"name": "python", "count": 3},
        {"name": "docker", "count": 1},
        {"name": "fastmcp", "count": 1},
    ]


def test_notes_since(db_conn: sqlite3.Connection) -> None:
    create_note(db_conn, title="Recent", content="Fresh")
    notes = notes_since(db_conn, days=1, limit=10)
    assert len(notes) == 1
    assert notes[0]["title"] == "Recent"
