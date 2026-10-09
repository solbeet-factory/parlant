# Draft pull requests to emcie-co/parlant

One file per generic fork commit. They are **drafts**: not opened until reviewed
(see FORK.md, "Upstream PRs"). Each says which fork commit it comes from, what
changes against `develop`, and the PR body to paste.

| draft | fork commit | status |
|---|---|---|
| [01](01-json-flush-window.md) | `perf(db): optional flush window for JSONFileDocumentDatabase` | draft |
| [02](02-on-cancelled-hook.md) | `feat(engine): on_cancelled hook for cancelled processing runs` | draft |
| [03](03-manual-mode-precedence.md) | `fix(engine): "manual" wins when tools request conflicting session modes` | draft |
| [04](04-process-without-status-event.md) | `fix(sessions): process() reports ready when the run emitted no status event` | draft |
| [05](05-canned-response-id-resolution.md) | `fix(canned): resolve slightly mis-transcribed canned response IDs` | draft |
| [06](06-openai-schema-validation-retry.md) | `fix(openai): retry when the model's JSON does not match the schema` | draft |
