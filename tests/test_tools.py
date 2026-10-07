"""Tests for MCP server tools, resources, and prompts."""

import json
from pathlib import Path
from typing import Any

import pytest

from notes_mcp.server import create_mcp


@pytest.fixture
def mcp_server(tmp_path: Path):
    db_file = tmp_path / "notes_test.db"
    return create_mcp(db_file)


async def call_tool_single(server, name: str, args: dict[str, Any]) -> Any:
    result = await server.call_tool(name, args)
    assert len(result.content) == 1
    return json.loads(result.content[0].text)


async def call_tool_multi(server, name: str, args: dict[str, Any]) -> Any:
    result = await server.call_tool(name, args)
    if len(result.content) == 1:
        parsed = json.loads(result.content[0].text)
        if isinstance(parsed, dict) and "error" in parsed:
            return parsed
    return [json.loads(c.text) for c in result.content]


async def test_add_and_get_note(mcp_server) -> None:
    # Add note
    added = await call_tool_single(
        mcp_server,
        "add_note",
        {"title": "My Note", "content": "Full note content", "tags": ["tag1", "tag2"]},
    )
    assert "error" not in added
    assert added["id"] == 1
    assert added["title"] == "My Note"
    assert added["content"] == "Full note content"
    assert added["tags"] == ["tag1", "tag2"]

    # Get note returns full content
    fetched = await call_tool_single(mcp_server, "get_note", {"note_id": 1})
    assert fetched == added


async def test_search_and_preview_truncation(mcp_server) -> None:
    long_content = "A" * 300
    await call_tool_single(
        mcp_server,
        "add_note",
        {"title": "Long Note", "content": long_content, "tags": ["test"]},
    )

    results = await call_tool_multi(mcp_server, "search_notes", {"query": "Long"})
    assert isinstance(results, list)
    assert len(results) == 1
    item = results[0]
    assert item["title"] == "Long Note"
    assert "content" not in item
    assert "preview" in item
    # 200 chars + "..."
    assert len(item["preview"]) == 203
    assert item["preview"].startswith("A" * 200)
    assert item["preview"].endswith("...")


async def test_list_recent_notes(mcp_server) -> None:
    await call_tool_single(mcp_server, "add_note", {"title": "Note 1", "content": "Content 1"})
    await call_tool_single(mcp_server, "add_note", {"title": "Note 2", "content": "Content 2"})

    results = await call_tool_multi(mcp_server, "list_recent_notes", {"limit": 10})
    assert len(results) == 2
    assert results[0]["title"] == "Note 2"
    assert "preview" in results[0]
    assert "content" not in results[0]


async def test_update_note(mcp_server) -> None:
    added = await call_tool_single(
        mcp_server,
        "add_note",
        {"title": "Initial", "content": "Initial content", "tags": ["tag1"]},
    )
    note_id = added["id"]

    updated = await call_tool_single(
        mcp_server,
        "update_note",
        {"note_id": note_id, "title": "Updated Title", "tags": ["newtag"]},
    )
    assert updated["title"] == "Updated Title"
    assert updated["content"] == "Initial content"
    assert updated["tags"] == ["newtag"]


async def test_delete_note(mcp_server) -> None:
    added = await call_tool_single(
        mcp_server, "add_note", {"title": "Delete Me", "content": "Body"}
    )
    note_id = added["id"]

    res = await call_tool_single(mcp_server, "delete_note", {"note_id": note_id})
    assert res == {"status": "deleted", "note_id": note_id}

    # Fetching deleted note returns error
    fetch_err = await call_tool_single(mcp_server, "get_note", {"note_id": note_id})
    assert "error" in fetch_err


async def test_error_cases(mcp_server) -> None:
    # Get nonexistent note
    err_get = await call_tool_single(mcp_server, "get_note", {"note_id": 999})
    assert "error" in err_get

    # Delete nonexistent note
    err_del = await call_tool_single(mcp_server, "delete_note", {"note_id": 999})
    assert "error" in err_del

    # Update nonexistent note
    err_up = await call_tool_single(mcp_server, "update_note", {"note_id": 999, "title": "New"})
    assert "error" in err_up

    # Update with no fields
    err_empty_up = await call_tool_single(mcp_server, "update_note", {"note_id": 1})
    assert "error" in err_empty_up

    # Empty search query
    err_search = await call_tool_multi(mcp_server, "search_notes", {"query": "   "})
    assert "error" in err_search


async def test_input_validation(mcp_server) -> None:
    # Empty title
    assert "error" in await call_tool_single(
        mcp_server, "add_note", {"title": "", "content": "Text"}
    )

    # Title > 200 chars
    long_title = "x" * 201
    assert "error" in await call_tool_single(
        mcp_server, "add_note", {"title": long_title, "content": "Text"}
    )

    # Empty content
    assert "error" in await call_tool_single(
        mcp_server, "add_note", {"title": "Valid", "content": ""}
    )

    # Content > 20000 chars
    long_body = "x" * 20001
    assert "error" in await call_tool_single(
        mcp_server, "add_note", {"title": "Valid", "content": long_body}
    )

    # Tags > 20
    too_many_tags = [f"tag{i}" for i in range(21)]
    assert "error" in await call_tool_single(
        mcp_server, "add_note", {"title": "Valid", "content": "Text", "tags": too_many_tags}
    )

    # Tag > 50 chars
    long_tag = ["a" * 51]
    assert "error" in await call_tool_single(
        mcp_server, "add_note", {"title": "Valid", "content": "Text", "tags": long_tag}
    )


async def test_limit_clamping(mcp_server) -> None:
    for i in range(55):
        await call_tool_single(
            mcp_server, "add_note", {"title": f"Note {i}", "content": "Content"}
        )

    # Limit <= 0 is clamped to 1
    min_res = await call_tool_multi(mcp_server, "list_recent_notes", {"limit": 0})
    assert len(min_res) == 1

    # Limit > 50 is clamped to 50
    max_res = await call_tool_multi(mcp_server, "list_recent_notes", {"limit": 100})
    assert len(max_res) == 50


async def test_tags_resource(mcp_server) -> None:
    await call_tool_single(
        mcp_server,
        "add_note",
        {"title": "Note 1", "content": "Content 1", "tags": ["tagA", "tagB"]},
    )
    await call_tool_single(
        mcp_server,
        "add_note",
        {"title": "Note 2", "content": "Content 2", "tags": ["tagA"]},
    )

    resource_contents = await mcp_server.read_resource("notes://tags")
    assert len(resource_contents) == 1
    tag_data = json.loads(resource_contents[0].content)
    assert tag_data == [
        {"name": "taga", "count": 2},
        {"name": "tagb", "count": 1},
    ]


async def test_summarize_recent_notes_prompt(mcp_server) -> None:
    prompt = await mcp_server.get_prompt("summarize_recent_notes", {"days": 7})
    assert len(prompt.messages) > 0
    text = prompt.messages[0].content.text
    assert "7 days" in text
    assert "list_recent_notes" in text or "search_notes" in text
