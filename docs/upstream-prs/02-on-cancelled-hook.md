# Draft: feat(engine): on_cancelled hook for cancelled processing runs

- Fork commit: `feat(engine): on_cancelled hook for cancelled processing runs` (solbeet/3.3.x)
- Target: `emcie-co/parlant:develop`. **Needs adapting**: `hooks.py` changed on develop after 3.3.2 (the sync check reports a conflict there). The change is additive: one `EngineHooks` field, one `call_on_cancelled` method, and the call in `AlphaEngine._emit_cancellation_event`.
- Status: draft, not opened.

---

## Summary

When new events arrive while a run is still preparing, `BackgroundTaskService.restart` cancels it. Messages are protected by the latch, but whatever the run already wrote to the session (tool events, mostly) stays there, and there is no supported way to react: integrators end up monkeypatching `AlphaEngine._emit_cancellation_event`.

This PR adds `EngineHooks.on_cancelled`, called right after the `cancelled` status event is emitted, with the cancelled run's **trace ID** as payload, so a hook can find exactly the events that run left behind.

Semantics:

- hooks run while the cancellation propagates: they cannot stop it, and their result is ignored;
- an exception in a hook is logged as a warning and never replaces the `CancelledError`;
- `restart` awaits the cancelled task under its lock before starting the new run, so hooks finish before the next run reads the session.

## Use case

Our tools are *decisions* executed later by another service, reading the session. When a run is cancelled, its tool events read as facts for the next run ("the brochure was already sent") although nothing was executed. With this hook we soft-delete the tool events of the cancelled run (`SessionStore.delete_event`) and let the new run decide again. That policy stays in our code; the engine only needs the extension point.

## Tests

`tests/core/stable/engines/alpha/test_on_cancelled_hook.py` (or wherever you prefer):

- `test_that_on_cancelled_runs_after_the_cancelled_status_with_the_trace_id`
- `test_that_a_failing_on_cancelled_hook_does_not_break_the_cancellation`
- `test_that_no_on_cancelled_hooks_is_a_no_op`

Happy to rewrite them on top of `SDKTest` if you prefer an end-to-end test that cancels a real run.
