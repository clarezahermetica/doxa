"""Prompt and native schema for the canonical one-action reply."""

import json
from typing import Any


def research_schema() -> dict[str, Any]:
    """Native output choices mirror controller contracts; authorization stays in the controller."""
    from doxa.core.text_research import ReviewAssessment, ReviewDecision, ReviewResponse

    string = {"type": "string"}
    sources = {"type": "array", "items": string}
    nullable = {"type": ["string", "null"]}
    operations: dict[str, dict[str, Any]] = {
        "claim": {"proposition": string, "source_ids": sources, "revises_id": nullable},
        "challenge": {"claim_id": string, "objection": string, "source_ids": sources},
        "respond": {
            "challenge_id": string,
            "response": {
                **ReviewResponse.model_json_schema()["properties"]["response"],
                "description": "Disposition only. Put the prose explanation in reason.",
            },
            "reason": string,
            "revised_proposition": nullable,
            "revision_of": nullable,
            "source_ids": sources,
        },
        "adjudicate": {
            "claim_id": nullable,
            "challenge_id": nullable,
            "outcome": ReviewDecision.model_json_schema()["properties"]["outcome"],
            "reason": string,
            "source_ids": sources,
        },
        "assess": {
            "claim_id": string,
            "challenge_id": nullable,
            "stance": ReviewAssessment.model_json_schema()["properties"]["stance"],
            "reason": string,
            "source_ids": sources,
        },
    }
    variants = []
    for operation, properties in operations.items():
        props = {
            "operation": {"type": "string", "const": operation},
            **properties,
            "citation_ranges": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "source_id": string,
                        "start": {"type": "integer"},
                        "end": {"type": "integer"},
                    },
                    "required": ["source_id", "start", "end"],
                    "additionalProperties": False,
                },
            },
        }
        variants.append(
            {
                "type": "object",
                "properties": props,
                "required": list(props),
                "additionalProperties": False,
            }
        )
    return {
        "type": "object",
        "properties": {"research_action": {"anyOf": variants}},
        "required": ["research_action"],
        "additionalProperties": False,
    }


def prompt_examples(allowed: tuple[str, ...]) -> str:
    variants = research_schema()["properties"]["research_action"]["anyOf"]
    by_name = {v["properties"]["operation"]["const"]: v["properties"] for v in variants}
    examples = []
    choices = []
    for name in allowed:
        example: dict[str, object] = {}
        for field, spec in by_name[name].items():
            if "const" in spec:
                value = spec["const"]
            elif "enum" in spec:
                values = spec["enum"]
                value = values[0]
                choices.append(f"{name}.{field}: " + ", ".join(values))
            elif field == "claim_id":
                value = "supplied claim ID"
            elif isinstance(spec["type"], list):
                value = None
            elif spec["type"] == "array":
                value = []
            elif field.endswith("_id"):
                value = f"supplied {field.replace('_', ' ')}"
            else:
                value = "..."
            example[field] = value
        examples.append(json.dumps({"research_action": example}))
    return (
        "Choose one reply format. Replace placeholders and choose evidence-supported values:\n"
        + "\n".join(examples)
        + ("\nAllowed field values: " + "; ".join(choices) + "." if choices else "")
    )
