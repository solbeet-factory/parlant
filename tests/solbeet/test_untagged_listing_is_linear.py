# Solbeet fork: listing the untagged entities of a store (`list_*(tags=[])`)
# built one `{"id": {"$ne": id}}` clause per tagged entity and evaluated that
# `$and` against every document: O(tagged x total) comparisons. EntityQueries
# runs that listing several times per turn (globals, an agent without tags, a
# turn without journeys), and with every entity tagged by its agent it always
# returns nothing. In production (96 agents, 1,610 canned responses, 2,869
# guidelines in one pod) one canned listing took 1.3 s and one guideline
# listing 4.6 s: ~12 s of every turn spent on empty results
# (solbeet-factory/parlant-service#200).
#
# CapabilityVectorStore is left as upstream: it collects the association ids,
# not the capability ids, so its untagged listing excludes nothing today.
#
# These tests pin both halves of the fix: the result is exactly the untagged
# entities, as before, and the cost no longer grows with tagged x total.
from collections.abc import AsyncIterator, Awaitable, Callable, Sequence
from contextlib import AsyncExitStack
from typing import Any
from unittest.mock import MagicMock

import pytest

import parlant.core.persistence.common as persistence_common
from parlant.adapters.db.transient import TransientDocumentDatabase
from parlant.adapters.vector_db.transient import TransientVectorDatabase
from parlant.core.canned_responses import CannedResponseVectorStore
from parlant.core.common import IdGenerator
from parlant.core.context_variables import ContextVariableDocumentStore
from parlant.core.glossary import GlossaryVectorStore
from parlant.core.guidelines import GuidelineDocumentStore
from parlant.core.journeys import JourneyVectorStore
from parlant.core.nlp.embedding import Embedder, EmbedderFactory, NullEmbedder, NullEmbeddingCache
from parlant.core.tags import TagId

TAGGED = 300
UNTAGGED = 2
# A linear listing compares each document a handful of times. The quadratic
# one needs ~TAGGED^2 / 2 (45,000 here): any bound between the two separates them.
MAX_COMPARISONS = 20 * (TAGGED + UNTAGGED)


async def _null_embedder_type() -> type[Embedder]:
    return NullEmbedder


def _vector_store_kwargs() -> dict[str, Any]:
    factory = EmbedderFactory(MagicMock())
    return {
        "vector_db": TransientVectorDatabase(
            MagicMock(), MagicMock(), factory, lambda: NullEmbeddingCache()
        ),
        "document_db": TransientDocumentDatabase(),
        "embedder_factory": factory,
        "embedder_type_provider": _null_embedder_type,
    }


Create = Callable[[Any, str, Sequence[TagId]], Awaitable[Any]]
List = Callable[[Any], Awaitable[Sequence[Any]]]

STORES: dict[str, tuple[Callable[[], Any], Create, List]] = {
    "canned_responses": (
        lambda: CannedResponseVectorStore(IdGenerator(), **_vector_store_kwargs()),
        lambda s, name, tags: s.create_canned_response(value=name, tags=tags),
        lambda s: s.list_canned_responses(tags=[]),
    ),
    "guidelines": (
        lambda: GuidelineDocumentStore(IdGenerator(), TransientDocumentDatabase()),
        lambda s, name, tags: s.create_guideline(condition=name, action=name, tags=tags),
        lambda s: s.list_guidelines(tags=[]),
    ),
    "journeys": (
        lambda: JourneyVectorStore(IdGenerator(), **_vector_store_kwargs()),
        lambda s, name, tags: s.create_journey(
            title=name, description=name, conditions=[], tags=tags
        ),
        lambda s: s.list_journeys(tags=[]),
    ),
    "glossary": (
        lambda: GlossaryVectorStore(IdGenerator(), **_vector_store_kwargs()),
        lambda s, name, tags: s.create_term(name=name, description=name, tags=tags),
        lambda s: s.list_terms(tags=[]),
    ),
    "context_variables": (
        lambda: ContextVariableDocumentStore(IdGenerator(), TransientDocumentDatabase()),
        lambda s, name, tags: s.create_variable(name=name, tags=tags),
        lambda s: s.list_variables(tags=[]),
    ),
}


def _name(entity: Any) -> str:
    for attr in ("value", "name", "title"):
        if isinstance(getattr(entity, attr, None), str):
            return str(getattr(entity, attr))
    return str(entity.content.condition)


@pytest.fixture(params=sorted(STORES))
async def populated(request: pytest.FixtureRequest) -> AsyncIterator[tuple[Any, List]]:
    make, create, list_untagged = STORES[request.param]
    async with AsyncExitStack() as stack:
        store = await stack.enter_async_context(make())
        for i in range(TAGGED):
            await create(store, f"tagged-{i}", [TagId(f"agent:{i % 7}")])
        for i in range(UNTAGGED):
            await create(store, f"untagged-{i}", [])
        yield store, list_untagged


async def test_that_listing_untagged_entities_returns_exactly_the_untagged_ones(
    populated: tuple[Any, List],
) -> None:
    store, list_untagged = populated

    names = sorted(_name(e) for e in await list_untagged(store))

    assert names == [f"untagged-{i}" for i in range(UNTAGGED)]


async def test_that_listing_untagged_entities_does_not_compare_every_pair(
    populated: tuple[Any, List],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store, list_untagged = populated
    comparisons = 0
    original = persistence_common._evaluate_filter

    def counting(operator: str, field_value: Any, filter_value: Any) -> bool:
        nonlocal comparisons
        comparisons += 1
        return original(operator, field_value, filter_value)

    monkeypatch.setattr(persistence_common, "_evaluate_filter", counting)

    await list_untagged(store)

    assert comparisons <= MAX_COMPARISONS, (
        f"{comparisons} filter comparisons for {TAGGED + UNTAGGED} documents"
    )
