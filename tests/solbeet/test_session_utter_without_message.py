# Solbeet fork: SessionModule.utter no longer raises when the engine emits no
# message event. See solbeet-factory/parlant-service#85.
from contextlib import contextmanager
from types import SimpleNamespace
from typing import Any, Iterator

from parlant.core.app_modules.sessions import SessionModule
from parlant.core.sessions import EventKind, EventSource


class _Store:
    def __init__(self, events: dict[EventKind, list[Any]]) -> None:
        self.events = events
        self.queries: list[Any] = []

    async def read_session(self, session_id: str) -> Any:
        return SimpleNamespace(id=session_id, agent_id="a1")

    async def list_events(self, session_id: str, trace_id: str, kinds: Any) -> list[Any]:
        self.queries.append((session_id, trace_id, list(kinds)))
        return [e for kind in kinds for e in self.events.get(kind, [])]


class _Tracer:
    trace_id = "trace-1"

    @contextmanager
    def span(self, *args: Any, **kwargs: Any) -> Iterator[None]:
        yield


class _Engine:
    def __init__(self) -> None:
        self.calls = 0

    async def utter(self, **kwargs: Any) -> bool:
        self.calls += 1
        return True


class _EmitterFactory:
    async def create_event_emitter(self, **kwargs: Any) -> Any:
        return SimpleNamespace()


def _module(store: _Store) -> Any:
    module = SessionModule.__new__(SessionModule)
    module._session_store = store  # type: ignore[attr-defined]
    module._tracer = _Tracer()  # type: ignore[attr-defined]
    module._engine = _Engine()  # type: ignore[attr-defined]
    module._event_emitter_factory = _EmitterFactory()  # type: ignore[attr-defined]
    module._logger = SimpleNamespace(warning=lambda *a, **k: None)  # type: ignore[attr-defined]
    created: list[dict[str, Any]] = []

    async def create_status_event(**kwargs: Any) -> Any:
        created.append(kwargs)
        return SimpleNamespace(kind=EventKind.STATUS, **kwargs)

    module.create_status_event = create_status_event  # type: ignore[method-assign]
    module.created = created  # type: ignore[attr-defined]
    return module


async def test_that_the_first_message_event_of_the_utterance_is_returned() -> None:
    message = SimpleNamespace(id="m1", kind=EventKind.MESSAGE)
    store = _Store({EventKind.MESSAGE: [message, SimpleNamespace(id="m2")]})
    module = _module(store)

    assert await module.utter("s1", []) is message
    assert store.queries == [("s1", "trace-1", [EventKind.MESSAGE])]
    assert module.created == []


async def test_that_an_utterance_without_messages_reports_ready_instead_of_raising() -> None:
    ready = SimpleNamespace(id="st1", kind=EventKind.STATUS, data={"status": "ready", "data": {}})
    module = _module(_Store({EventKind.STATUS: [ready]}))

    event = await module.utter("s1", [])

    assert module.created == [
        {
            "session_id": "s1",
            "source": EventSource.SYSTEM,
            "status": "ready",
            "data": {"reason": "no_message_from_engine", "trace_id": "trace-1"},
            "metadata": None,
        }
    ]
    assert event.kind == EventKind.STATUS
    assert event.status == "ready"


async def test_that_an_utterance_that_failed_reports_its_error_status() -> None:
    error = SimpleNamespace(
        id="st2", kind=EventKind.STATUS, data={"status": "error", "data": {"exception": "x"}}
    )
    ready = SimpleNamespace(id="st3", kind=EventKind.STATUS, data={"status": "ready", "data": {}})
    module = _module(_Store({EventKind.STATUS: [ready, error]}))

    assert await module.utter("s1", []) is error
    assert module.created == []
