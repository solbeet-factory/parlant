# Draft: fix(canned): resolve slightly mis-transcribed canned response IDs

- Fork commit: `fix(canned): resolve slightly mis-transcribed canned response IDs` (solbeet/3.3.x)
- Target: `emcie-co/parlant:develop`. Applies cleanly on develop as of 2026-10-09 (sync check).
- Status: draft, not opened.

---

## Summary

In strict composition the selection LLM must copy the chosen template's ID verbatim, and `_generate_response` resolves it with an exact comparison (`canrep.id == selected_canrep_id`). IDs are random mixed-case strings, and the LLM occasionally slips: it drops the last character, adds one, or loses the capitalization. A correct choice is then logged as "Invalid canned response ID choice" and the customer gets the no-match response.

Production case: the template was `coHquWc26I`; the selector picked it with `match_quality: "high"` (its own rationale names the template) and returned `coHquWc26`. Nine retries truncated it the same way and the customer got no answer.

This PR adds `resolve_canned_response_id(chosen, valid_ids)` and uses it in step 5.3. It returns:

- the chosen ID when it is valid (unchanged happy path);
- otherwise a valid ID **only** when exactly one candidate is a plausible transcription: same ID ignoring case, or one is a prefix of the other, within 2 characters of length difference;
- `None` when ambiguous or implausible, so the turn still falls back to no-match. Sending the wrong canned response is worse than sending none.

The length floor matters: most IDs start with a different character, so without it almost any short output would be a "unique prefix".

A resolved ID is logged as a warning, so a model that keeps mis-transcribing is visible.

## Tests

- `test_that_plausible_mistranscriptions_resolve` (exact, -1/-2 chars, +1/+2 chars, case, case and -1)
- `test_that_implausible_ids_do_not_resolve`
- `test_that_short_outputs_do_not_resolve_by_unique_prefix`
- `test_that_ambiguity_does_not_resolve`
- `test_that_an_empty_pool_does_not_resolve`
