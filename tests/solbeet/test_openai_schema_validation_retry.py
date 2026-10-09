# Solbeet fork: OpenAISchematicGenerator.do_generate retries when the model's JSON
# does not match the schema. See solbeet-factory/parlant-service#103.
from contextlib import contextmanager
from types import SimpleNamespace
from typing import Any, Iterator

import pytest
from pydantic import BaseModel, ValidationError

from parlant.adapters.nlp.openai_service import OpenAISchematicGenerator
from parlant.core.nlp import policies


class _Schema(BaseModel):
    required: str


def _validation_error() -> ValidationError:
    try:
        _Schema.model_validate({})
    except ValidationError as exc:
        return exc
    raise AssertionError("unreachable")


class _Logger:
    @contextmanager
    def scope(self, name: str) -> Iterator[None]:
        yield


class _Generator(OpenAISchematicGenerator[_Schema]):
    @property
    def max_tokens(self) -> int:
        return 1024


def _generator(outcomes: list[Any]) -> Any:
    generator: Any = _Generator.__new__(_Generator)
    generator.logger = _Logger()
    generator.schema = _Schema
    generator.calls = 0

    async def _do_generate(prompt: Any, hints: Any = {}) -> Any:
        outcome = outcomes[generator.calls]
        generator.calls += 1
        if isinstance(outcome, Exception):
            raise outcome
        return outcome

    generator._do_generate = _do_generate
    return generator


@pytest.fixture(autouse=True)
def _no_wait(monkeypatch: pytest.MonkeyPatch) -> list[float]:
    waits: list[float] = []

    async def _sleep(seconds: float) -> None:
        waits.append(seconds)

    monkeypatch.setattr(policies.asyncio, "sleep", _sleep)
    return waits


async def test_that_a_schema_mismatch_is_retried_until_it_succeeds(_no_wait: list[float]) -> None:
    ok = SimpleNamespace(content=_Schema(required="x"))
    generator = _generator([_validation_error(), _validation_error(), ok])

    assert await generator.do_generate("prompt") is ok
    assert generator.calls == 3
    assert _no_wait == [0.5, 2.0]


async def test_that_a_persistent_schema_mismatch_is_raised_after_three_attempts() -> None:
    generator = _generator([_validation_error()] * 4)

    with pytest.raises(ValidationError):
        await generator.do_generate("prompt")
    assert generator.calls == 3


async def test_that_other_errors_are_not_retried_by_this_policy() -> None:
    generator = _generator([ValueError("boom"), SimpleNamespace(content=None)])

    with pytest.raises(ValueError):
        await generator.do_generate("prompt")
    assert generator.calls == 1
