"""Regenerate HTTP and domain schemas; run from the repository root."""

import json
from pathlib import Path

from pydantic import TypeAdapter

from doxa.api.app import create_app
from doxa.core.models import Record

target = Path("docs/contracts")
target.mkdir(parents=True, exist_ok=True)
for name, schema in (
    ("openapi.json", create_app().openapi()),
    ("records.schema.json", TypeAdapter(Record).json_schema()),
):
    (target / name).write_text(json.dumps(schema, indent=2) + "\n", encoding="utf-8")
