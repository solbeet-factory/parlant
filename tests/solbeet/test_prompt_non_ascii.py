# Solbeet fork: JSON that goes into an LLM prompt keeps non-ASCII text as-is.
# See solbeet-factory/parlant-service#172 and upstream emcie-co/parlant#823.
#
# json.dumps() escapes every non-ASCII character as \uXXXX by default. Our leads
# write Spanish (and Portuguese) with accents, "ñ" and emojis, and the history is
# re-serialized into every LLM call of a turn, so each message cost ~2x the tokens.
import ast
from datetime import datetime, timezone
from pathlib import Path
from typing import cast

from parlant.core.common import JSONSerializable, generate_id
from parlant.core.context_variables import (
    ContextVariable,
    ContextVariableId,
    ContextVariableValue,
    ContextVariableValueId,
)
from parlant.core.engines.alpha.guideline_matching.generic.common import (
    internal_representation,
)
from parlant.core.engines.alpha.prompt_builder import PromptBuilder
from parlant.core.engines.alpha.utils import context_variables_to_json
from parlant.core.guidelines import Criticality, Guideline, GuidelineContent, GuidelineId
from parlant.core.sessions import Event, EventId, EventKind, EventSource
from parlant.core.tags import Tag

from tests.core.common.utils import create_event_message

TEXT = "¿Tenés turno mañana? Sí, a las 10 👍"


def test_that_a_message_event_keeps_accents_enie_and_emoji() -> None:
    event = create_event_message(offset=0, source=EventSource.CUSTOMER, message=TEXT)

    result = PromptBuilder.adapt_event(event)

    assert TEXT in result
    assert "\\u" not in result


def test_that_a_tool_event_keeps_accents_enie_and_emoji() -> None:
    event = Event(
        id=EventId(generate_id()),
        source=EventSource.AI_AGENT,
        kind=EventKind.TOOL,
        offset=1,
        trace_id="<main>",
        data=cast(
            JSONSerializable,
            {
                "tool_calls": [
                    {
                        "tool_id": "svc:consultar_catalogo",
                        "arguments": {"consulta": "año 2025"},
                        "result": {"data": {"respuesta": TEXT}},
                    }
                ]
            },
        ),
        metadata={},
        creation_utc=datetime.now(timezone.utc),
        deleted=False,
    )

    result = PromptBuilder.adapt_event(event)

    assert "año 2025" in result
    assert TEXT in result
    assert "\\u" not in result


def test_that_a_guideline_keeps_non_ascii_but_still_escapes_quotes_and_newlines() -> None:
    guideline = Guideline(
        id=GuidelineId(generate_id()),
        creation_utc=datetime.now(timezone.utc),
        content=GuidelineContent(
            condition='El cliente pregunta por el "año" del auto\ny la seña',
            action="Respondé con la cotización 👍",
        ),
        enabled=True,
        tags=[],
        metadata={},
        criticality=Criticality.MEDIUM,
    )

    representation = internal_representation(guideline)

    assert representation.condition is not None
    assert representation.action is not None
    assert "seña" in representation.condition
    assert '\\"año\\"' in representation.condition
    assert "\\n" in representation.condition
    assert representation.action == "Respondé con la cotización 👍"


def test_that_context_variables_keep_non_ascii() -> None:
    variable = ContextVariable(
        id=ContextVariableId(generate_id()),
        creation_utc=datetime.now(timezone.utc),
        name="sucursal",
        description="Dirección de la sucursal",
        tool_id=None,
        freshness_rules=None,
        tags=[Tag.for_agent_id("agent")],
    )
    value = ContextVariableValue(
        id=ContextVariableValueId(generate_id()),
        last_modified=datetime.now(timezone.utc),
        data="Peñaloza 123, Córdoba",
    )

    result = context_variables_to_json([(variable, value)])

    assert "Peñaloza 123, Córdoba" in result
    assert "Dirección" in result
    assert "\\u" not in result


# Every json.dumps() in the code that builds LLM prompts must pass
# ensure_ascii=False. This guard catches a call added or reintroduced by an
# upstream sync. Calls that feed logs, the tracer or the tool-server wire are
# listed by (file, enclosing function) and keep the default on purpose.
SRC = Path(__file__).resolve().parents[2] / "src" / "parlant"
PROMPT_ROOTS = [
    SRC / "core" / "engines" / "alpha",
    SRC / "core" / "services" / "indexing",
]
PROMPT_FILES = [SRC / "core" / "services" / "tools" / "plugins.py"]
NOT_PROMPT = {
    ("core/engines/alpha/engine.py", "_add_tool_events_to_tracer"),
    ("core/engines/alpha/tool_calling/tool_caller.py", "_run_tool"),
    (
        "core/engines/alpha/guideline_matching/custom_guideline_matching_strategy.py",
        "process",
    ),
    # plugins.py: only _describe_parameters builds prompt text (tool parameter
    # descriptions); the rest is the plugin server's HTTP streaming protocol.
    ("core/services/tools/plugins.py", "*"),
}
PROMPT_FUNCTIONS_IN_EXEMPT_FILES = {("core/services/tools/plugins.py", "_describe_parameters")}


def _json_dumps_calls_without_ensure_ascii_false() -> list[str]:
    files = [p for root in PROMPT_ROOTS for p in root.rglob("*.py")] + PROMPT_FILES
    offenders: list[str] = []

    for path in files:
        rel = path.relative_to(SRC).as_posix()
        tree = ast.parse(path.read_text(encoding="utf-8"))

        def visit(node: ast.AST, function: str) -> None:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                function = node.name
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr == "dumps"
                and isinstance(node.func.value, ast.Name)
                and node.func.value.id == "json"
            ):
                exempt = (rel, function) in NOT_PROMPT or (
                    (rel, "*") in NOT_PROMPT
                    and (rel, function) not in PROMPT_FUNCTIONS_IN_EXEMPT_FILES
                )
                ok = any(
                    kw.arg == "ensure_ascii"
                    and isinstance(kw.value, ast.Constant)
                    and kw.value.value is False
                    for kw in node.keywords
                )
                if not exempt and not ok:
                    offenders.append(f"{rel}:{node.lineno} ({function})")
            for child in ast.iter_child_nodes(node):
                visit(child, function)

        visit(tree, "<module>")

    return offenders


def test_that_every_prompt_json_dumps_keeps_non_ascii() -> None:
    assert _json_dumps_calls_without_ensure_ascii_false() == []
