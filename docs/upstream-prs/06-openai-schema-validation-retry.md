# Draft: fix(openai): retry when the model's JSON does not match the schema

- Fork commit: `fix(openai): retry when the model's JSON does not match the schema` (solbeet/3.3.x)
- Target: `emcie-co/parlant:develop`. The commit applies cleanly on develop as of 2026-10-09 (sync check).
- Status: draft, not opened.

---

## Summary

`OpenAISchematicGenerator.do_generate` retries `APIConnectionError`, `APITimeoutError`, `ConflictError`, `RateLimitError`, `APIResponseValidationError` and `InternalServerError`, but not `pydantic.ValidationError`. When the model returns valid JSON that lacks a required field, `_do_generate` logs "does not match expected schema" and re-raises, and the whole engine run ends in error: the customer gets no reply.

Each attempt is a fresh completion and the model rarely omits the same field twice in a row, so a short retry recovers almost every case. This PR adds

```python
retry(ValidationError, max_exceptions=3, wait_times=(0.5, 2.0)),
```

to the policy list: at most three attempts and ~2.5 s of extra wait in the worst case. Other errors keep their current policies.

We saw it in production: 4 of 50 turns in one conversation ended silent with a `ValidationError` in `GenericPreviouslyAppliedActionableGuidelineMatchingBatch` and `SingleToolBatchSchema`. We ran this as a monkeypatch for two months before moving it into the adapter.

## Tests

`tests/solbeet/test_openai_schema_validation_retry.py` (to be moved next to the adapter tests upstream):

- `test_that_a_schema_mismatch_is_retried_until_it_succeeds`
- `test_that_a_persistent_schema_mismatch_is_raised_after_three_attempts`
- `test_that_other_errors_are_not_retried_by_this_policy`

## Notes for review

Other adapters with the same `model_validate` + re-raise shape (Azure, LiteLLM, ...) could get the same policy; kept to OpenAI here to keep the change small.
