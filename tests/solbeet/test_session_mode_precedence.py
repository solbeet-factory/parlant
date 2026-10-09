# Solbeet fork: conflicting session-mode requests resolve to "manual".
# See solbeet-factory/parlant-service#103 and #100.
from types import SimpleNamespace
from typing import Any

import pytest

from parlant.core.engines.alpha.engine import AlphaEngine


class _Commands:
    def __init__(self) -> None:
        self.writes: list[tuple[str, dict[str, Any]]] = []

    async def update_session(self, session_id: str, params: dict[str, Any]) -> None:
        self.writes.append((session_id, params))


def _context(current_mode: str, *controls: dict[str, Any]) -> Any:
    events = [
        SimpleNamespace(
            data={
                "tool_calls": [
                    {"tool_id": f"local:t{i}", "result": {"control": c}}
                    for i, c in enumerate(controls)
                ]
            }
        )
    ]
    return SimpleNamespace(
        session=SimpleNamespace(id="s1", mode=current_mode),
        state=SimpleNamespace(tool_events=events),
    )


async def _run(context: Any) -> list[tuple[str, dict[str, Any]]]:
    engine = AlphaEngine.__new__(AlphaEngine)
    engine._logger = SimpleNamespace(info=lambda *a, **k: None)  # type: ignore[attr-defined]
    engine._entity_commands = _Commands()  # type: ignore[attr-defined]
    await engine._update_session_mode(context)
    return engine._entity_commands.writes  # type: ignore[attr-defined, no-any-return]


@pytest.mark.parametrize(
    "controls",
    [
        ({"mode": "manual"}, {"mode": "auto"}),
        ({"mode": "auto"}, {"mode": "manual"}),
        ({"mode": "auto"}, {}, {"mode": "manual"}, {"mode": "auto"}),
    ],
)
async def test_that_manual_wins_a_conflict_regardless_of_order(controls: Any) -> None:
    assert await _run(_context("auto", *controls)) == [("s1", {"mode": "manual"})]


async def test_that_a_conflict_is_written_even_if_the_run_started_in_manual() -> None:
    # The snapshot says manual, but a tool may already have persisted "auto".
    assert await _run(_context("manual", {"mode": "auto"}, {"mode": "manual"})) == [
        ("s1", {"mode": "manual"})
    ]


async def test_that_a_single_auto_request_switches_to_auto() -> None:
    assert await _run(_context("manual", {"mode": "auto"})) == [("s1", {"mode": "auto"})]


async def test_that_a_single_manual_request_switches_to_manual() -> None:
    assert await _run(_context("auto", {"mode": "manual"})) == [("s1", {"mode": "manual"})]


async def test_that_an_unchanged_mode_is_not_written() -> None:
    assert await _run(_context("auto", {"mode": "auto"}, {})) == []


async def test_that_controls_without_mode_are_not_written() -> None:
    assert await _run(_context("auto", {}, {})) == []
