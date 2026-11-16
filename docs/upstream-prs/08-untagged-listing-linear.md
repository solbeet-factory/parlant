# Draft: perf(stores): list untagged entities with a set difference, not one `$ne` per tagged id

- Fork commit: `perf(stores): untagged listings in linear time` (solbeet/3.3.x, `3.3.2+solbeet.8`)
- Target: `emcie-co/parlant:develop`. Parlant 4.0 moved these stores; `canned_responses.py`,
  `context_variables.py` and `customers.py` on develop still build the same filter as of 2026-11-16.
- Status: draft, not opened.

---

## Summary

`list_canned_responses(tags=[])` (and the same method on the guideline, journey, glossary and
context-variable stores) means "the entities without any tag". It reads every tag association and
builds

```python
{"$and": [{"id": {"$ne": id}} for id in tagged_ids]}
```

which the in-memory collections evaluate against every document: O(tagged × total) comparisons.
`EntityQueries` calls these listings several times per turn (the global entities, an agent with no
tags, a turn with no journeys). In a server where every entity is tagged by its agent they always
return nothing, and with ~100 agents (1,610 canned responses, 2,869 guidelines) one canned listing
took 1.3 s and one guideline listing 4.6 s on our production nodes: about 12 s of every turn.

With this PR the store reads the documents and drops the tagged ids with a set lookup. Same result,
linear cost. `CapabilityVectorStore` is left untouched: it collects the association ids instead of
the capability ids, so its untagged listing excludes nothing today (a separate bug).

## Tests

`tests/solbeet/test_untagged_listing_is_linear.py`, per store:

- `test_that_listing_untagged_entities_returns_exactly_the_untagged_ones`
- `test_that_listing_untagged_entities_does_not_compare_every_pair` (counts filter comparisons:
  45,750 before, under 6,040 after, for 302 documents)

## Notes for review

On Mongo the old filter ran server-side; the new code fetches the documents and filters in Python.
Only stores that Parlant keeps in memory in the SDK's default configuration are changed.
`CustomerDocumentStore` (often on Mongo) keeps the old query.
