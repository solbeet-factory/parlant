# Draft: fix(engine): "manual" wins when tools request conflicting session modes

- Fork commit: `fix(engine): "manual" wins when tools request conflicting session modes` (solbeet/3.3.x)
- Target: `emcie-co/parlant:develop`. `_update_session_mode` applies cleanly on develop as of 2026-10-09 (sync check).
- Status: draft, not opened.

---

## Summary

`AlphaEngine._update_session_mode` walks the `control` outputs of the run's tool calls and keeps the **last** requested mode:

```python
for control_output in tool_call_control_outputs:
    new_session_mode = control_output.get("mode") or current_session_mode
```

The order of those tool events is chosen by the tool-calling LLM. When one run fires both a hand-off tool (`mode="manual"`) and a resume tool (`mode="auto"`), whether the conversation ends with the human or with the agent is effectively random. We reproduced it by running the same conversation twice: one run called resume then hand-off, the other only resume.

This PR makes `manual` take precedence when both modes are requested in the same run: a hand-off to a human is never undone in the same breath it was requested. In that case the mode is written unconditionally, because `context.session` is the snapshot from the start of the run and the tools may have already persisted a different mode themselves (`Session.current.update`). Without a conflict, behavior is unchanged.

## Tests

- `test_that_manual_wins_a_conflict_regardless_of_order` (parametrized orders)
- `test_that_a_conflict_is_written_even_if_the_run_started_in_manual`
- `test_that_a_single_auto_request_switches_to_auto`
- `test_that_a_single_manual_request_switches_to_manual`
- `test_that_an_unchanged_mode_is_not_written`
- `test_that_controls_without_mode_are_not_written`

## Notes for review

If you would rather make the precedence configurable (e.g. an engine policy), we are happy to go that way; `manual` seemed the only safe default.
