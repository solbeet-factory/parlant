# Solbeet fork: a lone guideline that opted in answers with its canned response as-is,
# without drafting or selecting. See solbeet-factory/parlant-service#207.
#
# When a guideline's only job is a fixed text (a product explanation, an opt-out
# acknowledgement), the generator still drafts a reply (~2-3 s) and then asks the model
# to pick the canned response that matches it (~1-2 s), to end up sending that canned
# response verbatim. In 11 of 47 real webchat turns of one account the whole draft was
# thrown away like that.
#
# Opt-in, per guideline: metadata `canned_direct: true`. The shortcut only applies when
# nothing else could change the answer: exactly one ordinary guideline matched, no
# tool-enabled guidelines, no active journeys, no staged tool or message events in the
# turn, and the guideline has exactly one canned response among the ones eligible this
# turn. If the template fails to render, the normal path runs.
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from parlant.core.engines.alpha.canned_response_generator import (
    DIRECT_CANNED_METADATA_KEY,
    CannedResponseGenerator,
    _CannedResponseRenderResult,
)


def _canned(id_: str, value: str) -> SimpleNamespace:
    return SimpleNamespace(id=id_, value=value, metadata={})


def _match(metadata: dict, id_: str = "g1") -> SimpleNamespace:
    return SimpleNamespace(guideline=SimpleNamespace(id=id_, metadata=metadata))


def _context(**overrides) -> SimpleNamespace:
    base = dict(
        ordinary_guideline_matches=[_match({DIRECT_CANNED_METADATA_KEY: True})],
        tool_enabled_guideline_matches={},
        journeys=[],
        staged_tool_events=[],
        staged_message_events=[],
    )
    base.update(overrides)
    return SimpleNamespace(**base)


def _generator(
    own: list, rendered: str | None = "Lia es un gerente comercial."
) -> CannedResponseGenerator:
    gen = CannedResponseGenerator.__new__(CannedResponseGenerator)
    gen._entity_queries = SimpleNamespace(
        find_canned_responses_for_guidelines=AsyncMock(return_value=own)
    )
    gen._render_responses = AsyncMock(
        return_value=[
            _CannedResponseRenderResult(response=r, failed=rendered is None, rendered_text=rendered)
            for r in own
        ]
    )
    gen._canrep_draft_generator = SimpleNamespace(
        generate=AsyncMock(side_effect=AssertionError("drafted"))
    )
    gen._logger = SimpleNamespace(
        debug=lambda *_: None, info=lambda *_: None, trace=lambda *_: None
    )
    return gen


@pytest.mark.asyncio
async def test_that_an_opted_in_lone_guideline_sends_its_canned_response_verbatim() -> None:
    c1 = _canned("c1", "Lia es un gerente comercial.")
    result = await _generator([c1])._direct_canned_response(_context(), [c1])

    assert result is not None
    assert result.message == "Lia es un gerente comercial."
    assert result.draft is None
    assert result.chosen_canned_responses == [("c1", "Lia es un gerente comercial.")]


@pytest.mark.asyncio
async def test_that_generate_response_skips_the_draft_when_the_shortcut_applies() -> None:
    c1 = _canned("c1", "Lia es un gerente comercial.")
    gen = _generator([c1])

    info, result = await gen._generate_response(None, _context(), [c1], None, 0.1)

    assert info == {}
    assert result.message == "Lia es un gerente comercial."
    gen._canrep_draft_generator.generate.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "overrides",
    [
        {"ordinary_guideline_matches": [_match({})]},
        {"ordinary_guideline_matches": [_match({DIRECT_CANNED_METADATA_KEY: "yes"})]},
        {
            "ordinary_guideline_matches": [
                _match({DIRECT_CANNED_METADATA_KEY: True}),
                _match({}, "g2"),
            ]
        },
        {"ordinary_guideline_matches": []},
        {"tool_enabled_guideline_matches": {"g3": ["t"]}},
        {"journeys": [SimpleNamespace(id="j1")]},
        {"staged_tool_events": [SimpleNamespace()]},
        {"staged_message_events": [SimpleNamespace()]},
    ],
    ids=[
        "no-opt-in",
        "opt-in-not-true",
        "two-guidelines",
        "no-guidelines",
        "tools",
        "journey",
        "tool-events",
        "message-already-sent",
    ],
)
async def test_that_the_shortcut_does_not_apply_when_something_else_could_change_the_answer(
    overrides,
) -> None:
    c1 = _canned("c1", "Lia es un gerente comercial.")
    assert await _generator([c1])._direct_canned_response(_context(**overrides), [c1]) is None


@pytest.mark.asyncio
async def test_that_the_shortcut_needs_exactly_one_eligible_canned_response() -> None:
    c1, c2 = _canned("c1", "Uno."), _canned("c2", "Dos.")

    assert await _generator([c1, c2])._direct_canned_response(_context(), [c1, c2]) is None
    assert await _generator([])._direct_canned_response(_context(), [c1]) is None
    # Associated with the guideline but not eligible this turn (e.g. its required tool did not run).
    assert await _generator([c1])._direct_canned_response(_context(), [c2]) is None


@pytest.mark.asyncio
async def test_that_a_template_that_fails_to_render_falls_back_to_the_normal_path() -> None:
    c1 = _canned("c1", "Hola {{std.customer.name}}")
    assert await _generator([c1], rendered=None)._direct_canned_response(_context(), [c1]) is None


def test_that_the_fork_declares_the_feature() -> None:
    from parlant import solbeet

    assert "canned-direct" in solbeet.FEATURES
