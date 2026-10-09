# Draft: fix(sessions): utter() reports the run's status when it emitted no message

- Fork commit: `fix(sessions): utter() reports the run's status when it emitted no message` (solbeet/3.3.x)
- Target: `emcie-co/parlant:develop`. `SessionModule.utter` on develop still has `event, *_ = ...`; the commit cherry-picks cleanly onto develop as of 2026-10-09.
- Status: draft, not opened.

---

## Summary

`SessionModule.utter` runs the engine and returns

```python
event, *_ = await self._session_store.list_events(session_id=..., trace_id=..., kinds=[EventKind.MESSAGE])
```

The engine can finish an utterance **without** a message event: the message composer may return compositions with no events (a `_generate_response` override that decides not to reply, an `on_message_generated` hook that drops the message, a streaming run that yields no chunks), and a failed run (`AlphaEngine.utter` catches the exception) only emits an `error` status. The unpack then raises `ValueError: not enough values to unpack (expected at least 1, got 0)` and the caller of `POST /sessions/{id}/events` (an `ai_agent` message with `guidelines`) gets an opaque **500**.

We hit it in production with proactive utterances whose reply was intentionally suppressed.

With this PR, when no message event exists `utter()` logs a warning and:

- returns the run's `error` status event if the run failed, or
- creates a `ready` status event with `data = {"reason": "no_message_from_engine", "trace_id": ...}`,

so the caller gets a typed result (a status event instead of a message) and can treat the utterance as completed without a message. Same approach as the companion fix for `process()` without a status event.

## Tests

- `test_that_the_first_message_event_of_the_utterance_is_returned`
- `test_that_an_utterance_without_messages_reports_ready_instead_of_raising`
- `test_that_an_utterance_that_failed_reports_its_error_status`

## Notes for review

The response of `POST /sessions/{id}/events` for an utterance was always a message event; now it can be a status event. Clients that read `kind` already handle both shapes for the `process()` path. An alternative is a 204 / dedicated error code at the API layer; we kept it at the module boundary so non-HTTP callers of `SessionModule.utter` get the same behaviour.
