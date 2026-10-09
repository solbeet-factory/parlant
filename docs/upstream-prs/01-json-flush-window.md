# Draft: perf(db): optional flush window for JSONFileDocumentDatabase

- Fork commit: `perf(db): optional flush window for JSONFileDocumentDatabase` (solbeet/3.3.x)
- Target: `emcie-co/parlant:develop`. `json_file.py` is unchanged on develop since 3.3.2: the commit should apply as is.
- Status: draft, not opened.

---

## Summary

Every write on a `JSONFileDocumentCollection` ends in `database.flush()`, and `flush()` re-serializes the **whole** JSON file. A burst of N inserts therefore costs O(N²) bytes of JSON, all CPU under the GIL. The main victim is the embedding cache (`BasicEmbeddingCache` over `JSONFileDocumentDatabase`) while a server indexes its agents at startup.

This PR adds an opt-in flush window: `JSONFileDocumentDatabase(logger, path, flush_window_seconds=...)`, defaulting to the `PARLANT_JSON_FLUSH_WINDOW_SECONDS` environment variable, or 0 (current behavior). With a window > 0, a `flush()` that comes less than that many seconds after the previous one is skipped.

## Why it is safe

`__aexit__` calls `_flush_unlocked()` directly, not `flush()`, so a clean shutdown always writes everything pending. A crash may lose the writes of the last window, which is why it is opt-in and documented for rebuildable data such as the embedding cache.

## Numbers

Production deployment with 19 agents (524 guidelines, 303 canned responses, 3 journeys), measured on an isolated pod: the embedding cache reaches ~40 MB and startup provisioning took 261 s; with a 5 s window it took 54 s, with an identical resulting inventory.

## Tests

`tests/adapters/db/test_json_file.py` (new cases):

- `test_that_without_a_window_every_insert_rewrites_the_file`
- `test_that_a_window_coalesces_flushes`
- `test_that_a_window_never_loses_the_last_writes`
- `test_that_the_window_can_come_from_the_environment`
- `test_that_an_invalid_environment_value_keeps_the_original_behavior`

## Notes for review

- Open question for maintainers: would you rather expose it through `p.Server(...)` than an environment variable? The SDK builds the cache database in `bin/server.py`, so the env var was the least invasive switch.
