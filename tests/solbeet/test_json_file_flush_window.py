# Solbeet fork: coalesced flushes for JSONFileDocumentDatabase.
# See solbeet-factory/parlant-service#103.
import json
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest

from parlant.adapters.db.json_file import FLUSH_WINDOW_ENV_VAR, JSONFileDocumentDatabase
from parlant.core.persistence.document_database import BaseDocument, identity_loader


async def _insert(path: Path, count: int, **kwargs: Any) -> tuple[int, int]:
    db = JSONFileDocumentDatabase(MagicMock(), path, **kwargs)
    writes = []
    original_save = db._save_data

    async def counting_save(data: Any) -> None:
        writes.append(1)
        await original_save(data)

    db._save_data = counting_save  # type: ignore[method-assign]

    async with db:
        collection = await db.get_or_create_collection(
            name="c", schema=BaseDocument, document_loader=identity_loader
        )
        for i in range(count):
            await collection.insert_one(
                {"id": f"d{i}", "creation_utc": "2026-08-31T00:00:00Z", "version": "0.1.0"}  # type: ignore[typeddict-item]
            )

    saved = json.loads(path.read_text())
    return len(writes), len(saved.get("c", []))


async def test_that_without_a_window_every_insert_rewrites_the_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv(FLUSH_WINDOW_ENV_VAR, raising=False)
    writes, saved = await _insert(tmp_path / "a.json", 20)
    assert saved == 20
    assert writes == 21  # 20 inserts + the final write on __aexit__


async def test_that_a_window_coalesces_flushes(tmp_path: Path) -> None:
    writes, saved = await _insert(tmp_path / "b.json", 20, flush_window_seconds=60.0)
    assert saved == 20
    assert writes == 2  # the first insert, then __aexit__


async def test_that_a_window_never_loses_the_last_writes(tmp_path: Path) -> None:
    path = tmp_path / "c.json"
    _, saved = await _insert(path, 50, flush_window_seconds=3600.0)
    assert saved == 50
    assert {d["id"] for d in json.loads(path.read_text())["c"]} == {f"d{i}" for i in range(50)}


async def test_that_the_window_can_come_from_the_environment(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(FLUSH_WINDOW_ENV_VAR, "60")
    writes, saved = await _insert(tmp_path / "d.json", 10)
    assert (writes, saved) == (2, 10)


@pytest.mark.parametrize("value", ["", "nope", "-3"])
async def test_that_an_invalid_environment_value_keeps_the_original_behavior(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, value: str
) -> None:
    monkeypatch.setenv(FLUSH_WINDOW_ENV_VAR, value)
    writes, _ = await _insert(tmp_path / "e.json", 5)
    assert writes == 6
