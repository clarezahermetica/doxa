"""Offline parser and context coverage checks; never invoke model providers."""

import base64
import json
import os
import subprocess
import sys
from uuid import uuid4

from doxa.core.models import BudgetPolicy, CouncilLimits, Role, TaskSpecification
from doxa.core.workbench import (
    ContextAssembler,
    ImportSource,
    NewAgent,
    NewExperiment,
    ParticipantGroup,
    add_agent,
    create_experiment,
    import_source,
)
from doxa.retrieval.excerpts import evidence_excerpt


def test_document_worker_outputs_utf8_even_with_legacy_console_encoding():
    text = "Unicode evidence: \u2217 \u03b1 \u4e2d\u6587"
    body = json.dumps(
        {"filename": "evidence.txt", "data": base64.b64encode(text.encode()).decode()}
    )
    result = subprocess.run(
        [sys.executable, "-m", "doxa.retrieval.document_worker"],
        input=body.encode(),
        capture_output=True,
        env={**os.environ, "PYTHONIOENCODING": "cp1252"},
        timeout=12,
    )
    assert result.returncode == 0
    assert json.loads(result.stdout)["text"] == text


def test_full_text_when_it_fits_and_multiple_located_excerpts_when_not(controller):
    text = (
        "[Page 1]\n" + "methodology evidence " * 100 + "\n[Page 2]\n" + "feedback evidence " * 100
    )
    identity = uuid4()
    assert (
        evidence_excerpt(controller.settings.database_path, identity, text, "evidence", 10000)
        == text
    )
    partial = evidence_excerpt(controller.settings.database_path, identity, text, "evidence", 3500)
    assert partial.count("[Excerpt ") >= 2
    assert "characters " in partial and "PDF page" in partial and "Partial source" in partial
    assert len(json.dumps(partial).encode()) <= 3500
    assert partial == evidence_excerpt(
        controller.settings.database_path, identity, text, "evidence", 3500
    )


def test_unicode_excerpt_budget_counts_serialized_bytes(controller):
    text = "\u4e2d\u6587\u03b1" * 1000
    result = evidence_excerpt(controller.settings.database_path, uuid4(), text, "\u4e2d\u6587", 900)
    assert result and len(json.dumps(result).encode()) <= 900


def test_context_supplies_full_paper_or_records_partial_coverage(controller):
    actor = add_agent(
        controller,
        NewAgent(display_name="Reader", role=Role.RESEARCHER, instructions="Cite evidence."),
    )
    text = (
        "[Page 1]\n" + "methodology evidence " * 150 + "\n[Page 2]\n" + "external feedback " * 150
    )
    for ceiling in (16000, 4096):
        run = create_experiment(
            controller,
            NewExperiment(
                name="Coverage test",
                task=TaskSpecification(
                    question="methodology evidence feedback", council=CouncilLimits(rounds=1)
                ),
                participants=(ParticipantGroup(agent_id=actor.id),),
                budget=BudgetPolicy(max_context_tokens=ceiling, max_output_tokens=256),
                idempotency_key=str(uuid4()),
            ),
        )
        source = import_source(
            controller, run.id, ImportSource(title="Paper", text=text, idempotency_key="paper")
        )
        assembler = ContextAssembler(controller, run.id)
        manifest = assembler.assemble(assembler.runtime.experiment.agents[0], "coverage")
        messages = json.loads(assembler.runtime.store.get(manifest.messages))
        supplied = json.loads(messages[1]["content"].split("\n", 1)[1])["untrusted_content"]
        assert source.id in manifest.source_ids
        assert manifest.input_token_upper_bound <= ceiling - 256
        if ceiling == 16000:
            assert supplied == text and str(source.id) not in manifest.omitted
        else:
            assert "Partial source" in supplied
            assert manifest.omitted[str(source.id)].startswith("partial_source")
