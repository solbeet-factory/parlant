# Solbeet fork: journey text written by the agent's author reaches the LLM prompts
# literally, even when it contains "{" or "}". See solbeet-factory/parlant-service#192.
#
# PromptBuilder renders every section with `template.format(**props)`. The journey
# prompts used to build their text from the journey (title, description, activation
# conditions, step actions, transition conditions) and pass it as the TEMPLATE, so a
# step that says 'Answer "Thanks, {name}."' raised KeyError('name') while rendering:
#
# - at indexing, JourneyReachableNodesEvaluator failed and the whole journey
#   evaluation with it, so no node got `reachable_follow_ups` and the journey never
#   advanced past its first step;
# - at runtime, the next-step / backtrack prompts would fail the same way for any
#   step or transition whose text has braces.
#
# The text now travels in `props`, which `str.format` does not parse.
import ast
from pathlib import Path

from parlant.core.services.indexing.journey_reachable_nodes_evaluation import (
    JourneyNodeKind,
    JourneyReachableNodesEvaluator,
    _ChildInfo,
    _JourneyNode,
)

SRC = Path(__file__).resolve().parents[2] / "src" / "parlant" / "core"

JOURNEY_PROMPT_MODULES = [
    SRC / "services/indexing/journey_reachable_nodes_evaluation.py",
    SRC / "services/indexing/relative_action_proposer.py",
    SRC / "engines/alpha/guideline_matching/generic/journey/journey_next_step_selection.py",
    SRC / "engines/alpha/guideline_matching/generic/journey/journey_backtrack_check.py",
    SRC / "engines/alpha/guideline_matching/generic/journey/journey_backtrack_node_selection.py",
]

TEXT_WITH_BRACES = 'Answer "Thanks, {name}." and show the menu {A, B}'


def _dynamic_templates(module: Path) -> list[str]:
    tree = ast.parse(module.read_text())
    found = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and getattr(node.func, "attr", "") == "add_section":
            template = next((k.value for k in node.keywords if k.arg == "template"), None)
            if template is not None and not isinstance(template, ast.Constant):
                found.append(f"{module.name}:{node.lineno}")
    return found


def test_that_no_journey_prompt_section_uses_journey_text_as_its_template() -> None:
    offenders = [hit for module in JOURNEY_PROMPT_MODULES for hit in _dynamic_templates(module)]

    assert offenders == []


def test_that_the_reachable_nodes_prompt_renders_braces_in_actions_and_conditions() -> None:
    evaluator = JourneyReachableNodesEvaluator.__new__(JourneyReachableNodesEvaluator)
    node = _JourneyNode(
        id="1",
        action=TEXT_WITH_BRACES,
        incoming_edges=[],
        outgoing_edges=[],
        kind=JourneyNodeKind.CHAT,
        customer_dependent_action=False,
    )
    children = {
        "2": _ChildInfo(action="Ask for {email}", edge_condition="The customer wrote {name}")
    }

    prompt = evaluator._build_prompt(node=node, children_info=children, shots=[]).build()

    assert TEXT_WITH_BRACES in prompt
    assert "The customer wrote {name}" in prompt
