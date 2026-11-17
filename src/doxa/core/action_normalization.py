"""Transport syntax for one generated research action, before controller validation."""

import json
import math
from dataclasses import dataclass
from typing import Literal, Never

VERSION = "research-action-normalization-v1"
Transform = Literal["json_fence", "singleton_operations"]


class ResearchReplyError(ValueError):
    category: str

    def __init__(self, code: str, message: str, transforms: tuple[Transform, ...] = ()):
        self.code = code
        self.transforms = transforms
        super().__init__(message)


class ResponseFormatError(ResearchReplyError):
    category = "research_response_format"


class ResearchActionError(ResearchReplyError):
    category = "invalid_research_operation"


@dataclass(frozen=True)
class NormalizedAction:
    action: dict[str, object]
    transforms: tuple[Transform, ...]


class _DuplicateMember(ValueError):
    pass


def _object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise _DuplicateMember
        result[key] = value
    return result


def _invalid_constant(_: str) -> Never:
    raise ValueError("Non-JSON numeric constant")


def strict_json(text: str) -> object:
    """Never let duplicate members select an operation or overwrite action arguments."""

    def finite_float(token: str) -> float:
        number = float(token)
        if not math.isfinite(number):
            _invalid_constant(token)
        return number

    return json.loads(
        text, object_pairs_hook=_object, parse_constant=_invalid_constant, parse_float=finite_float
    )


def normalize_action(text: str) -> NormalizedAction:
    candidate = text.strip(" \t\r\n")
    transforms: tuple[Transform, ...] = ()
    first, separator, remainder = candidate.partition("\n")
    if separator and first.rstrip("\r").lower() in {"```", "```json"}:
        body, last_separator, closing = remainder.rpartition("\n")
        if last_separator and closing == "```":
            candidate = body
            transforms = ("json_fence",)
    try:
        parsed = strict_json(candidate)
    except _DuplicateMember:
        raise ResponseFormatError(
            "duplicate_json_member", "Reply contains duplicate JSON members", transforms
        ) from None
    except (ValueError, RecursionError):
        raise ResponseFormatError(
            "malformed_json", "Expected one JSON research reply", transforms
        ) from None
    if not isinstance(parsed, dict) or set(parsed) != {"research_action"}:
        raise ResponseFormatError(
            "invalid_envelope", "Expected one structured research action", transforms
        )
    action = parsed["research_action"]
    if isinstance(action, dict) and set(action) == {"operations"}:
        operations = action["operations"]
        if not isinstance(operations, list) or len(operations) != 1:
            raise ResponseFormatError(
                "operation_count", "Expected exactly one research action", transforms
            )
        action = operations[0]
        transforms += ("singleton_operations",)
    if not isinstance(action, dict):
        raise ResponseFormatError(
            "invalid_action_object", "Expected one structured research action object", transforms
        )
    return NormalizedAction(action, transforms)
