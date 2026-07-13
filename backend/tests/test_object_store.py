"""LocalObjectStore: content-addressed write-once storage."""

import pytest

from app.storage.object_store import LocalObjectStore, sha256_hex


def test_put_then_get_round_trips(tmp_path) -> None:
    store = LocalObjectStore(tmp_path)
    uri = store.put(b"hello")
    assert store.get(uri) == b"hello"
    assert uri == f"file://{sha256_hex(b'hello')}"


def test_identical_content_writes_once(tmp_path) -> None:
    store = LocalObjectStore(tmp_path)
    first = store.put(b"same bytes")
    second = store.put(b"same bytes")
    assert first == second


def test_get_rejects_path_traversal(tmp_path) -> None:
    store = LocalObjectStore(tmp_path)
    with pytest.raises(ValueError, match="Invalid storage URI"):
        store.get("file://../../../../etc/passwd")
