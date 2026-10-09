# Solbeet fork: tolerant resolution of the canned response ID chosen by the LLM.
# See solbeet-factory/parlant-service#103.
import pytest

from parlant.core.engines.alpha.canned_response_generator import resolve_canned_response_id

# The IDs offered in a real production selection prompt (2026-09-25).
OFFERED = [
    "coHquWc26I",
    "EmdTj2QMN6",
    "5quwu58lsa",
    "NIhZIz0It9",
    "LNlpZ3XaeM",
    "gVrLgLpOi9",
    "0dAdy0LLLT",
    "OMFuAObgfz",
    "tvWmEI5hNO",
    "nZbIVrB1RR",
    "quVqBj6fHn",
    "qAY0TeqChp",
]


@pytest.mark.parametrize(
    "chosen, expected",
    [
        ("coHquWc26I", "coHquWc26I"),  # exact
        ("coHquWc26", "coHquWc26I"),  # dropped the last character (the production case)
        ("coHquWc2", "coHquWc26I"),  # dropped two
        ("coHquWc26IX", "coHquWc26I"),  # appended one
        ("coHquWc26IXY", "coHquWc26I"),  # appended two
        ("cohquwc26i", "coHquWc26I"),  # lost the capitalization
        ("COHQUWC26", "coHquWc26I"),  # lost capitalization and the last character
        ("0dAdy0LLL", "0dAdy0LLLT"),
    ],
)
def test_that_plausible_mistranscriptions_resolve(chosen: str, expected: str) -> None:
    assert resolve_canned_response_id(chosen, OFFERED) == expected


@pytest.mark.parametrize("chosen", ["zzzzzzzzzz", "", "   ", "xyz", "coHquWc"])
def test_that_implausible_ids_do_not_resolve(chosen: str) -> None:
    assert resolve_canned_response_id(chosen, OFFERED) is None


@pytest.mark.parametrize("chosen", ["5", "c", "0", "co", "5q", "qAY"])
def test_that_short_outputs_do_not_resolve_by_unique_prefix(chosen: str) -> None:
    # Most offered IDs start with a different character, so without a length
    # floor almost any short output would be a "unique prefix" of one of them.
    assert resolve_canned_response_id(chosen, OFFERED) is None


def test_that_ambiguity_does_not_resolve() -> None:
    assert resolve_canned_response_id("abc123", ["abc123XY", "abc123ZW"]) is None


def test_that_an_empty_pool_does_not_resolve() -> None:
    assert resolve_canned_response_id("coHquWc26", []) is None
