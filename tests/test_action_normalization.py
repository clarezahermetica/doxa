import json

import pytest

from doxa.core.action_normalization import ResponseFormatError, normalize_action
from doxa.core.action_output import prompt_examples, research_schema


@pytest.mark.parametrize("fenced", [False, True])
@pytest.mark.parametrize("wrapped", [False, True])
def test_equivalent_formats_preserve_action_values(fenced, wrapped):
    action = {"operation": "claim", "proposition": "  Preserve é and spacing.  "}
    text = json.dumps({"research_action": {"operations": [action]} if wrapped else action})
    text = f"\r\n```JSON\r\n{text}\r\n```\r\n" if fenced else text
    result = normalize_action(text)
    assert result.action == action
    assert result.transforms == (
        *(("json_fence",) if fenced else ()),
        *(("singleton_operations",) if wrapped else ()),
    )


@pytest.mark.parametrize(
    ("reply", "code"),
    [
        ("", "malformed_json"),
        ('{"research_action":', "malformed_json"),
        ('Prose\n```json\n{"research_action":{}}\n```', "malformed_json"),
        ('```json\n{"research_action":{}}\n```\nProse', "malformed_json"),
        ('{"research_action":{"n":NaN}}', "malformed_json"),
        ('{"research_action":{"n":1e999}}', "malformed_json"),
        (
            '{"research_action":{"operation":"claim","operation":"respond"}}',
            "duplicate_json_member",
        ),
        ('{"research_action":{},"research_action":{}}', "duplicate_json_member"),
        ('{"operation":"claim"}', "invalid_envelope"),
        ('{"research_action":{},"tool_request":{}}', "invalid_envelope"),
        ('{"research_action":{"operations":[]}}', "operation_count"),
        ('{"research_action":{"operations":[{},{}]}}', "operation_count"),
        ('{"research_action":{"operations":["claim"]}}', "invalid_action_object"),
        ('{"research_action":[]}', "invalid_action_object"),
    ],
)
def test_reject_ambiguous_or_malformed_reply(reply, code):
    with pytest.raises(ResponseFormatError) as error:
        normalize_action(reply)
    assert error.value.code == code


def test_prompt_and_native_schema_share_enums_and_single_action_shape():
    prompt = prompt_examples(("respond", "adjudicate"))
    examples = [json.loads(line)["research_action"] for line in prompt.splitlines()[1:-1]]
    assert [action["operation"] for action in examples] == ["respond", "adjudicate"]
    variants = research_schema()["properties"]["research_action"]["anyOf"]
    for example in examples:
        properties = next(
            v["properties"]
            for v in variants
            if v["properties"]["operation"]["const"] == example["operation"]
        )
        assert set(example) == set(properties)
        for name, spec in properties.items():
            if "enum" in spec:
                assert example[name] in spec["enum"]
