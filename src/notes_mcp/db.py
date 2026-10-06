"""SQLite database layer for notes-mcp."""

import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path


def get_connection(db_path: str | Path) -> sqlite3.Connection:
    """Create and return a configured sqlite3 connection."""
    str_path = str(db_path)
    if str_path != ":memory:":
        Path(str_path).parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(str_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    return conn


def init_db(db_path: str | Path) -> None:
    """Initialize database tables and indexes."""
    conn = get_connection(db_path)
    try:
        with conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS notes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL,
                    content TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS tags (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL UNIQUE
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS note_tags (
                    note_id INTEGER NOT NULL,
                    tag_id INTEGER NOT NULL,
                    PRIMARY KEY (note_id, tag_id),
                    FOREIGN KEY (note_id) REFERENCES notes(id) ON DELETE CASCADE,
                    FOREIGN KEY (tag_id) REFERENCES tags(id) ON DELETE CASCADE
                )
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_notes_created_at
                ON notes(created_at DESC)
                """
            )
    finally:
        conn.close()


def normalize_tags(tags: list[str] | None) -> list[str]:
    """Trim whitespace, lowercase, remove empty strings and duplicates while preserving order."""
    if not tags:
        return []
    seen: set[str] = set()
    cleaned_tags: list[str] = []
    for tag in tags:
        cleaned = tag.strip().lower()
        if cleaned and cleaned not in seen:
            seen.add(cleaned)
            cleaned_tags.append(cleaned)
    return cleaned_tags


def escape_like(query: str) -> str:
    """Escape special characters for SQL LIKE operator."""
    return query.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def utc_now_iso() -> str:
    """Return current UTC time in ISO 8601 format."""
    return datetime.now(UTC).isoformat()


def _sync_note_tags(conn: sqlite3.Connection, note_id: int, tags: list[str]) -> None:
    """Sync tag relationships for a given note within current transaction."""
    conn.execute("DELETE FROM note_tags WHERE note_id = ?", (note_id,))
    for tag in tags:
        conn.execute("INSERT OR IGNORE INTO tags (name) VALUES (?)", (tag,))
        tag_row = conn.execute("SELECT id FROM tags WHERE name = ?", (tag,)).fetchone()
        if tag_row:
            conn.execute(
                "INSERT INTO note_tags (note_id, tag_id) VALUES (?, ?)",
                (note_id, tag_row["id"]),
            )


def _hydrate_notes(conn: sqlite3.Connection, rows: list[sqlite3.Row]) -> list[dict]:
    """Hydrate note rows with their associated tags."""
    if not rows:
        return []
    note_ids = [row["id"] for row in rows]
    placeholders = ",".join("?" for _ in note_ids)
    tag_rows = conn.execute(
        f"""
        SELECT nt.note_id, t.name
        FROM tags t
        JOIN note_tags nt ON t.id = nt.tag_id
        WHERE nt.note_id IN ({placeholders})
        ORDER BY t.name ASC
        """,
        note_ids,
    ).fetchall()

    tags_by_note: dict[int, list[str]] = {nid: [] for nid in note_ids}
    for tr in tag_rows:
        tags_by_note[tr["note_id"]].append(tr["name"])

    return [
        {
            "id": row["id"],
            "title": row["title"],
            "content": row["content"],
            "tags": tags_by_note[row["id"]],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }
        for row in rows
    ]


def create_note(
    conn: sqlite3.Connection,
    title: str,
    content: str,
    tags: list[str] | None = None,
) -> dict:
    """Create a new note with optional tags."""
    norm_tags = normalize_tags(tags)
    now = utc_now_iso()
    with conn:
        cursor = conn.execute(
            """
            INSERT INTO notes (title, content, created_at, updated_at)
            VALUES (?, ?, ?, ?)
            """,
            (title, content, now, now),
        )
        note_id = cursor.lastrowid
        if note_id is None:
            raise RuntimeError("Failed to insert note")
        _sync_note_tags(conn, note_id, norm_tags)

    note = get_note(conn, note_id)
    if note is None:
        raise RuntimeError(f"Failed to fetch newly created note {note_id}")
    return note


def get_note(conn: sqlite3.Connection, note_id: int) -> dict | None:
    """Retrieve a note by its ID, or None if not found."""
    row = conn.execute(
        "SELECT id, title, content, created_at, updated_at FROM notes WHERE id = ?",
        (note_id,),
    ).fetchone()
    if row is None:
        return None
    return _hydrate_notes(conn, [row])[0]


def search_notes(conn: sqlite3.Connection, query: str, limit: int = 10) -> list[dict]:
    """Search notes by title or content matching query (case-insensitive LIKE)."""
    pattern = f"%{escape_like(query)}%"
    rows = conn.execute(
        """
        SELECT id, title, content, created_at, updated_at
        FROM notes
        WHERE title LIKE ? ESCAPE '\\' OR content LIKE ? ESCAPE '\\'
        ORDER BY created_at DESC
        LIMIT ?
        """,
        (pattern, pattern, limit),
    ).fetchall()
    return _hydrate_notes(conn, rows)


def list_recent_notes(conn: sqlite3.Connection, limit: int = 10) -> list[dict]:
    """List most recent notes, newest first."""
    rows = conn.execute(
        """
        SELECT id, title, content, created_at, updated_at
        FROM notes
        ORDER BY created_at DESC
        LIMIT ?
        """,
        (limit,),
    ).fetchall()
    return _hydrate_notes(conn, rows)


def update_note(
    conn: sqlite3.Connection,
    note_id: int,
    title: str | None = None,
    content: str | None = None,
    tags: list[str] | None = None,
) -> dict | None:
    """Update fields of an existing note. Returns updated note or None if not found."""
    existing = conn.execute("SELECT id FROM notes WHERE id = ?", (note_id,)).fetchone()
    if existing is None:
        return None

    fields: list[str] = []
    params: list = []

    if title is not None:
        fields.append("title = ?")
        params.append(title)
    if content is not None:
        fields.append("content = ?")
        params.append(content)

    now = utc_now_iso()
    fields.append("updated_at = ?")
    params.append(now)

    params.append(note_id)

    with conn:
        conn.execute(
            f"UPDATE notes SET {', '.join(fields)} WHERE id = ?",
            params,
        )
        if tags is not None:
            _sync_note_tags(conn, note_id, normalize_tags(tags))

    return get_note(conn, note_id)


def delete_note(conn: sqlite3.Connection, note_id: int) -> bool:
    """Delete a note by ID. Returns True if deleted, False if not found."""
    with conn:
        cursor = conn.execute("DELETE FROM notes WHERE id = ?", (note_id,))
        return cursor.rowcount > 0


def list_tags(conn: sqlite3.Connection) -> list[dict]:
    """Return all distinct tags with their note counts."""
    rows = conn.execute(
        """
        SELECT t.name, COUNT(nt.note_id) AS count
        FROM tags t
        JOIN note_tags nt ON t.id = nt.tag_id
        GROUP BY t.name
        HAVING count > 0
        ORDER BY count DESC, t.name ASC
        """
    ).fetchall()
    return [{"name": row["name"], "count": row["count"]} for row in rows]


def notes_since(conn: sqlite3.Connection, days: int, limit: int = 10) -> list[dict]:
    """Return notes created within the last N days."""
    cutoff = (datetime.now(UTC) - timedelta(days=days)).isoformat()
    rows = conn.execute(
        """
        SELECT id, title, content, created_at, updated_at
        FROM notes
        WHERE created_at >= ?
        ORDER BY created_at DESC
        LIMIT ?
        """,
        (cutoff, limit),
    ).fetchall()
    return _hydrate_notes(conn, rows)
