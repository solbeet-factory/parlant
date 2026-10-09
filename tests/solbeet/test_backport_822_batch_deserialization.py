# Solbeet fork: the #822 backport (batch deserialization) adapted to 3.3.2.
from typing import Any, Mapping

from parlant.adapters.db.transient import TransientDocumentDatabase
from parlant.core.common import IdGenerator
from parlant.core.guidelines import GuidelineDocumentStore
from parlant.core.journeys import JourneyVectorStore
from parlant.core.tags import TagId


async def test_that_listed_guidelines_carry_their_tags() -> None:
    async with GuidelineDocumentStore(IdGenerator(), TransientDocumentDatabase()) as store:
        tagged = await store.create_guideline(condition="c1", action="a1", tags=[TagId("t1")])
        await store.upsert_tag(tagged.id, TagId("t2"))
        untagged = await store.create_guideline(condition="c2", action="a2")

        listed = {g.id: g for g in await store.list_guidelines()}

        assert set(listed[tagged.id].tags) == {"t1", "t2"}
        assert list(listed[untagged.id].tags) == []
        assert [g.id for g in await store.list_guidelines(tags=[TagId("t2")])] == [tagged.id]


class _Collection:
    def __init__(self, docs: list[Mapping[str, Any]]) -> None:
        self.docs = docs

    async def find(self, filters: Mapping[str, Any]) -> list[Mapping[str, Any]]:
        ((field, condition),) = filters.items()
        return [d for d in self.docs if d[field] in condition["$in"]]


async def test_that_journeys_are_batch_deserialized_with_conditions_and_tags() -> None:
    store = JourneyVectorStore.__new__(JourneyVectorStore)
    store._tag_association_collection = _Collection(  # type: ignore[assignment]
        [{"journey_id": "j1", "tag_id": "t1"}, {"journey_id": "j2", "tag_id": "t2"}]
    )
    store._condition_association_collection = _Collection(  # type: ignore[assignment]
        [{"journey_id": "j1", "condition": "g1"}, {"journey_id": "j1", "condition": "g2"}]
    )

    def doc(id: str) -> dict[str, Any]:
        return {
            "id": id,
            "creation_utc": "2026-10-09T00:00:00+00:00",
            "title": f"title {id}",
            "description": "",
            "root_id": f"root-{id}",
            "labels": [],
        }

    j1, j2 = await store._deserialize_batch([doc("j1"), doc("j2")])  # type: ignore[list-item]

    assert (list(j1.conditions), list(j1.tags), j1.title) == (["g1", "g2"], ["t1"], "title j1")
    assert (list(j2.conditions), list(j2.tags)) == ([], ["t2"])
