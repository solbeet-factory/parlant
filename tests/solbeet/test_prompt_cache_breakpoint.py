# Solbeet fork: explicit prompt-cache breakpoint for OpenAI-compatible endpoints
# (gpt-6-luna on Bedrock). The implicit cache only hits when two prompts have the
# exact same length, so Parlant's batches never read it. See
# solbeet-factory/parlant-service#170.
from contextlib import contextmanager
from types import SimpleNamespace
from typing import Any, Iterator

import pytest
from pydantic import BaseModel

from parlant.adapters.nlp import openai_service
from parlant.adapters.nlp.openai_service import OpenAISchematicGenerator
from parlant.core.engines.alpha.prompt_builder import BuiltInSection, PromptBuilder


def _builder(guidelines: str = "g-1", with_history: bool = True) -> PromptBuilder:
    builder = PromptBuilder()
    builder.add_section(name="instructions", template="  You are a matcher.  ")
    builder.add_section(name="identity", template="Agent: {name}", props={"name": "Lía 🙂"})
    if with_history:
        builder.add_section(name=BuiltInSection.INTERACTION_HISTORY, template="customer: hola")
        builder.add_section(name=BuiltInSection.STAGED_EVENTS, template="tool: ok")
    builder.add_section(
        name=BuiltInSection.GUIDELINES, template="Guidelines: {g}", props={"g": guidelines}
    )
    builder.add_section(name="output", template="Answer in JSON.  ")
    return builder


def test_that_the_parts_rebuild_the_exact_prompt() -> None:
    builder = _builder()

    prefix, rest = builder.build_parts()

    assert prefix + rest == builder.build()


def test_that_the_prefix_ends_after_the_history_and_staged_events() -> None:
    prefix, rest = _builder().build_parts()

    assert prefix.endswith("tool: ok\n\n")
    assert rest.startswith("Guidelines: g-1")


def test_that_two_batches_of_the_same_turn_share_the_prefix() -> None:
    assert _builder("g-1").build_parts()[0] == _builder("g-2").build_parts()[0]


def test_that_a_prompt_without_history_has_no_prefix() -> None:
    builder = _builder(with_history=False)

    assert builder.build_parts() == ("", builder.build())


class _Schema(BaseModel):
    ok: bool


class _Logger:
    @contextmanager
    def scope(self, name: str) -> Iterator[None]:
        yield

    def trace(self, message: str) -> None:
        pass


class _Completions:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    async def create(self, **kwargs: Any) -> Any:
        self.calls.append(kwargs)
        details = SimpleNamespace(cached_tokens=900, cache_write_tokens=0)
        usage = SimpleNamespace(
            prompt_tokens=1000,
            completion_tokens=5,
            prompt_tokens_details=details,
            model_dump_json=lambda indent=None: "{}",
        )
        message = SimpleNamespace(content='{"ok": true}')
        return SimpleNamespace(choices=[SimpleNamespace(message=message)], usage=usage)


class _Generator(OpenAISchematicGenerator[_Schema]):
    @property
    def max_tokens(self) -> int:
        return 1024


def _generator(breakpoint: bool) -> Any:
    generator: Any = _Generator.__new__(_Generator)
    generator.logger = _Logger()
    generator.schema = _Schema
    generator.model_name = "openai.gpt-6-luna"
    generator.meter = None
    generator.prompt_cache_breakpoint = breakpoint
    completions = _Completions()
    generator._client = SimpleNamespace(chat=SimpleNamespace(completions=completions))
    return generator, completions


@pytest.fixture(autouse=True)
def _no_metrics(monkeypatch: pytest.MonkeyPatch) -> list[float]:
    async def _record(*args: Any, **kwargs: Any) -> None:
        pass

    waits: list[float] = []

    async def _sleep(seconds: float) -> None:
        waits.append(seconds)

    monkeypatch.setattr(openai_service, "record_llm_metrics", _record)
    monkeypatch.setattr(openai_service.asyncio, "sleep", _sleep)
    openai_service._PROMPT_CACHE_FIRST_SEEN.clear()
    return waits


async def test_that_without_the_option_the_prompt_goes_as_one_string() -> None:
    generator, completions = _generator(breakpoint=False)
    builder = _builder()

    await generator._do_generate(builder)

    assert completions.calls[0]["messages"] == [{"role": "developer", "content": builder.build()}]
    assert "extra_body" not in completions.calls[0]


async def test_that_with_the_option_the_prefix_carries_an_explicit_breakpoint() -> None:
    generator, completions = _generator(breakpoint=True)
    prefix, rest = _builder().build_parts()

    result = await generator._do_generate(_builder())

    assert completions.calls[0]["messages"] == [
        {
            "role": "developer",
            "content": [
                {"type": "text", "text": prefix, "prompt_cache_breakpoint": {"mode": "explicit"}},
                {"type": "text", "text": rest},
            ],
        }
    ]
    assert completions.calls[0]["extra_body"] == {
        "prompt_cache_options": {"mode": "explicit", "ttl": "30m"}
    }
    assert result.info.usage.extra["cached_input_tokens"] == 900
    assert result.info.usage.extra["cache_write_tokens"] == 0


async def test_that_a_prompt_without_prefix_goes_as_one_string_even_with_the_option() -> None:
    generator, completions = _generator(breakpoint=True)
    builder = _builder(with_history=False)

    await generator._do_generate(builder)

    assert completions.calls[0]["messages"] == [{"role": "developer", "content": builder.build()}]


async def test_that_a_concurrent_call_with_the_same_prefix_waits_for_the_first_write(
    _no_metrics: list[float], monkeypatch: pytest.MonkeyPatch
) -> None:
    now = [100.0]
    monkeypatch.setattr(openai_service.time, "monotonic", lambda: now[0])
    generator, _ = _generator(breakpoint=True)

    await generator._do_generate(_builder("g-1"))
    now[0] = 100.2
    await generator._do_generate(_builder("g-2"))
    now[0] = 101.0
    await generator._do_generate(_builder("g-3"))

    assert _no_metrics == [pytest.approx(0.3)]
