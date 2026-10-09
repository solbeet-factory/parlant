# Solbeet fork: SessionModule.process no longer raises when the engine emits
# no status event. See solbeet-factory/parlant-service#103 (and #71, #85).
from types import SimpleNamespace
from typing import Any

from parlant.core.app_modules.sessions import SessionModule
from parlant.core.sessions import EventKind, EventSource


class _Store:
    def __init__(self, status_events: list[Any]) -> None:
        self.status_events = status_events
        self.queries: list[Any] = []

    async def read_session(self, session_id: str) -> Any:
        return SimpleNamespace(id=session_id)

    async def list_events(self, session_id: str, trace_id: str, kinds: Any) -> list[Any]:
        self.queries.append((session_id, trace_id, list(kinds)))
        return self.status_events


class _Listener:
    async def wait_for_more_events(self, **kwargs: Any) -> bool:
        return False


def _module(store: _Store) -> Any:
    module = SessionModule.__new__(SessionModule)
    module._session_store = store  # type: ignore[attr-defined]
    module._session_listener = _Listener()  # type: ignore[attr-defined]
    module._logger = SimpleNamespace(warning=lambda *a, **k: None)  # type: ignore[attr-defined]
    created: list[dict[str, Any]] = []

    async def dispatch_processing_task(session: Any) -> str:
        return "trace-1"

    async def create_status_event(**kwargs: Any) -> Any:
        created.append(kwargs)
        return SimpleNamespace(kind=EventKind.STATUS, **kwargs)

    module.dispatch_processing_task = dispatch_processing_task  # type: ignore[method-assign]
    module.create_status_event = create_status_event  # type: ignore[method-assign]
    module.created = created  # type: ignore[attr-defined]
    return module


async def test_that_the_first_status_event_of_the_run_is_returned() -> None:
    ready = SimpleNamespace(id="e1")
    store = _Store([ready, SimpleNamespace(id="e2")])
    module = _module(store)

    assert await module.process("s1") is ready
    assert store.queries == [("s1", "trace-1", [EventKind.STATUS])]
    assert module.created == []


async def test_that_a_run_without_status_events_reports_ready_instead_of_raising() -> None:
    module = _module(_Store([]))

    event = await module.process("s1")

    assert module.created == [
        {
            "session_id": "s1",
            "source": EventSource.SYSTEM,
            "status": "ready",
            "data": {"reason": "no_status_from_engine", "trace_id": "trace-1"},
            "metadata": None,
        }
    ]
    assert event.status == "ready"
