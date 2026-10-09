# Solbeet fork: EngineHooks.on_cancelled. See solbeet-factory/parlant-service#103.
from types import SimpleNamespace
from typing import Any, Optional

from parlant.core.engines.alpha.engine import AlphaEngine
from parlant.core.engines.alpha.hooks import EngineHookResult, EngineHooks


class _Emitter:
    def __init__(self) -> None:
        self.statuses: list[Any] = []

    async def emit_status_event(self, trace_id: str, data: Any) -> None:
        self.statuses.append((trace_id, data["status"]))


def _engine(hooks: EngineHooks) -> Any:
    engine = AlphaEngine.__new__(AlphaEngine)
    engine._hooks = hooks  # type: ignore[attr-defined]
    engine._tracer = SimpleNamespace(trace_id="run-A")  # type: ignore[attr-defined]
    engine._logger = SimpleNamespace(  # type: ignore[attr-defined]
        warnings=[], warning=lambda m: engine._logger.warnings.append(m)
    )
    return engine


async def test_that_on_cancelled_runs_after_the_cancelled_status_with_the_trace_id() -> None:
    seen: list[Any] = []
    emitter = _Emitter()

    async def hook(context: Any, payload: Any, exc: Optional[Exception]) -> EngineHookResult:
        seen.append((payload, list(emitter.statuses)))
        return EngineHookResult.CALL_NEXT

    hooks = EngineHooks(on_cancelled=[hook])
    context = SimpleNamespace(session_event_emitter=emitter)

    await AlphaEngine._emit_cancellation_event(_engine(hooks), context)  # type: ignore[arg-type]

    assert seen == [("run-A", [("run-A", "cancelled")])]


async def test_that_a_failing_on_cancelled_hook_does_not_break_the_cancellation() -> None:
    async def hook(context: Any, payload: Any, exc: Optional[Exception]) -> EngineHookResult:
        raise RuntimeError("boom")

    engine = _engine(EngineHooks(on_cancelled=[hook]))
    emitter = _Emitter()

    await AlphaEngine._emit_cancellation_event(
        engine, SimpleNamespace(session_event_emitter=emitter)
    )  # type: ignore[arg-type]

    assert emitter.statuses == [("run-A", "cancelled")]
    assert engine._logger.warnings and "boom" in engine._logger.warnings[0]


async def test_that_no_on_cancelled_hooks_is_a_no_op() -> None:
    emitter = _Emitter()
    await AlphaEngine._emit_cancellation_event(  # type: ignore[arg-type]
        _engine(EngineHooks()), SimpleNamespace(session_event_emitter=emitter)
    )
    assert emitter.statuses == [("run-A", "cancelled")]
