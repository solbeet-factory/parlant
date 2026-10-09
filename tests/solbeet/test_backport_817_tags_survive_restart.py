# Solbeet fork: the #817 backport. On 3.3.2 GuidelineDocumentStore writes tag
# associations as 0.10.0 but only loaded "0.5.0", so on any persistent store
# every guideline tag was dropped on restart (reproduced on Mongo 7 too).
from pathlib import Path
from unittest.mock import MagicMock

from parlant.adapters.db.json_file import JSONFileDocumentDatabase
from parlant.core.common import IdGenerator
from parlant.core.customers import CustomerDocumentStore
from parlant.core.guidelines import GuidelineDocumentStore
from parlant.core.tags import TagId


async def _open_and_list(path: Path, create: bool) -> tuple[list[list[str]], list[list[str]]]:
    async with (
        JSONFileDocumentDatabase(MagicMock(), path / "guidelines.json") as gdb,
        JSONFileDocumentDatabase(MagicMock(), path / "customers.json") as cdb,
    ):
        async with (
            GuidelineDocumentStore(IdGenerator(), gdb) as guidelines,
            CustomerDocumentStore(IdGenerator(), cdb) as customers,
        ):
            if create:
                await guidelines.create_guideline(
                    condition="c", action="a", tags=[TagId("journey:x")]
                )
                await customers.create_customer(name="n", tags=[TagId("t1")])

            return (
                [list(g.tags) for g in await guidelines.list_guidelines()],
                [list(c.tags) for c in await customers.list_customers() if c.name == "n"],
            )


async def test_that_guideline_and_customer_tags_survive_a_restart(tmp_path: Path) -> None:
    before = await _open_and_list(tmp_path, create=True)
    after = await _open_and_list(tmp_path, create=False)

    assert before == ([["journey:x"]], [["t1"]])
    assert after == before
