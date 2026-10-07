"""MCP server implementation for notes-mcp."""

import json
import sqlite3
from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path

from mcp.server.mcpserver import MCPServer

from notes_mcp import db

# Alias MCPServer as FastMCP for compatibility
FastMCP = MCPServer


@contextmanager
def db_session(db_path: str | Path) -> Generator[sqlite3.Connection, None, None]:
    """Context manager to yield a db connection and guarantee it is closed."""
    conn = db.get_connection(db_path)
    try:
        yield conn
    finally:
        conn.close()


def clamp_limit(limit: int) -> int:
    """Clamp limit to the range [1, 50]."""
    return max(1, min(50, limit))


def to_preview_note(note: dict) -> dict:
    """Return note dict with 'preview' field instead of full 'content'."""
    content = note["content"]
    preview = content[:200] + ("..." if len(content) > 200 else "")
    return {
        "id": note["id"],
        "title": note["title"],
        "preview": preview,
        "tags": note["tags"],
        "created_at": note["created_at"],
        "updated_at": note["updated_at"],
    }


def validate_title(title: str | None) -> str | None:
    """Validate title is between 1 and 200 characters."""
    if title is None or not (1 <= len(title.strip()) <= 200):
        return "Title must be between 1 and 200 characters."
    return None


def validate_content(content: str | None) -> str | None:
    """Validate content is between 1 and 20,000 characters."""
    if content is None or not (1 <= len(content.strip()) <= 20000):
        return "Content must be between 1 and 20,000 characters."
    return None


def validate_tags(tags: list[str] | None) -> str | None:
    """Validate tag count is at most 20 and each tag is 1 to 50 characters."""
    if tags is None:
        return None
    if len(tags) > 20:
        return "A maximum of 20 tags is allowed."
    for tag in tags:
        if not (1 <= len(tag.strip()) <= 50):
            return f"Tag '{tag}' must be between 1 and 50 characters."
    return None


def create_mcp(db_path: str | Path) -> FastMCP:
    """Create and configure the FastMCP server with tools, resources, and prompts."""
    db.init_db(db_path)

    mcp = FastMCP(
        name="notes",
        instructions=(
            "Personal notes server storing notes in SQLite. "
            "Allows adding, searching, reading, updating, and deleting notes, "
            "inspecting tags, and summarizing recent activity."
        ),
    )

    @mcp.tool()
    def add_note(title: str, content: str, tags: list[str] | None = None) -> dict:
        """Create and store a new note in SQLite.

        Args:
            title: The title of the note (1 to 200 characters).
            content: The text/markdown content of the note (1 to 20,000 characters).
            tags: Optional list of tag names (up to 20 tags, max 50 characters each).

        Returns:
            The created note object, or an error dictionary if validation fails.
        """
        err = validate_title(title)
        if err:
            return {"error": err}
        err = validate_content(content)
        if err:
            return {"error": err}
        err = validate_tags(tags)
        if err:
            return {"error": err}

        with db_session(db_path) as conn:
            return db.create_note(conn, title=title.strip(), content=content, tags=tags or [])

    @mcp.tool()
    def get_note(note_id: int) -> dict:
        """Retrieve a single note with its full content by note ID.

        Args:
            note_id: The integer ID of the note to retrieve.

        Returns:
            The full note dictionary, or an error if not found.
        """
        with db_session(db_path) as conn:
            note = db.get_note(conn, note_id)
        if note is None:
            return {"error": f"Note {note_id} not found"}
        return note

    @mcp.tool()
    def search_notes(query: str, limit: int = 10) -> list[dict] | dict:
        """Search notes by matching title or content (case-insensitive).

        Args:
            query: The search text query.
            limit: Maximum results to return (clamped between 1 and 50, default 10).

        Returns:
            List of note previews, or an error dictionary.
        """
        if not query or not query.strip():
            return {"error": "Search query cannot be empty"}

        clamped = clamp_limit(limit)
        with db_session(db_path) as conn:
            results = db.search_notes(conn, query=query.strip(), limit=clamped)
        return [to_preview_note(n) for n in results]

    @mcp.tool()
    def list_recent_notes(limit: int = 10) -> list[dict]:
        """List the most recent notes, newest first.

        Args:
            limit: Maximum results to return (clamped between 1 and 50, default 10).

        Returns:
            List of note previews.
        """
        clamped = clamp_limit(limit)
        with db_session(db_path) as conn:
            results = db.list_recent_notes(conn, limit=clamped)
        return [to_preview_note(n) for n in results]

    @mcp.tool()
    def update_note(
        note_id: int,
        title: str | None = None,
        content: str | None = None,
        tags: list[str] | None = None,
    ) -> dict:
        """Update fields of an existing note.

        Args:
            note_id: The integer ID of the note to update.
            title: New title for the note (1 to 200 characters, optional).
            content: New content for the note (1 to 20,000 characters, optional).
            tags: New list of tags replacing existing tags (max 20 tags, optional).

        Returns:
            The updated note dictionary, or an error dictionary.
        """
        if title is None and content is None and tags is None:
            return {"error": "At least one field (title, content, or tags) must be provided"}

        if title is not None:
            err = validate_title(title)
            if err:
                return {"error": err}
            title = title.strip()

        if content is not None:
            err = validate_content(content)
            if err:
                return {"error": err}

        if tags is not None:
            err = validate_tags(tags)
            if err:
                return {"error": err}

        with db_session(db_path) as conn:
            updated = db.update_note(
                conn,
                note_id=note_id,
                title=title,
                content=content,
                tags=tags,
            )
        if updated is None:
            return {"error": f"Note {note_id} not found"}
        return updated

    @mcp.tool()
    def delete_note(note_id: int) -> dict:
        """Permanently delete a note by its ID.

        Args:
            note_id: The integer ID of the note to delete.

        Returns:
            Status confirmation or an error dictionary.
        """
        with db_session(db_path) as conn:
            deleted = db.delete_note(conn, note_id)
        if not deleted:
            return {"error": f"Note {note_id} not found"}
        return {"status": "deleted", "note_id": note_id}

    @mcp.resource("notes://tags")
    def tags_resource() -> str:
        """Resource returning all distinct tags with note counts."""
        with db_session(db_path) as conn:
            tags = db.list_tags(conn)
        return json.dumps(tags, indent=2)

    @mcp.prompt("summarize_recent_notes")
    def summarize_recent_notes(days: int = 7) -> str:
        """Generate a prompt template asking to summarize notes from the last N days."""
        safe_days = max(1, days)
        return (
            f"Please summarize the notes from the last {safe_days} days. "
            "Call `list_recent_notes` or `search_notes` to examine recent notes, "
            "and provide an organized summary by theme."
        )

    return mcp
