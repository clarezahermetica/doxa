"""Offline discovery metadata, never an inference registry or experimental authority."""

import json
import os
import sqlite3
import tempfile
from contextlib import closing
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, cast

from doxa.core.profiles import ModelProfile
from doxa.core.secrets import reject_secrets


@dataclass(frozen=True)
class CatalogEntry:
    developer: str
    family: str
    model_id: str
    display_name: str = ""
    checkpoint: str = ""
    source: str = "User registration"
    kind: str = "model"
    status: str = "unverified"
    open_weight: bool = False
    checked: str = ""


def catalog_notes(directory: Path) -> list[dict[str, Any]]:
    path = directory / "model-catalog.json"
    if not path.exists():
        return []
    if path.stat().st_size > 2_000_000:
        raise ValueError("Local catalog notes exceed 2 MB; preserve and review the file")
    value = json.loads(path.read_text(encoding="utf-8"))
    if (
        not isinstance(value, dict)
        or value.get("version") != 1
        or not isinstance(value.get("entries"), list)
    ):
        raise ValueError("Unsupported local catalog notes; no entries will be replaced")
    if not all(isinstance(item, dict) for item in value["entries"]):
        raise ValueError("Invalid catalog entry; preserve the file for review")
    return cast(list[dict[str, Any]], value["entries"])


def save_catalog_note(directory: Path, note: dict[str, Any]) -> None:
    """Append UI metadata atomically. Canonical assignments remain ModelProfiles in SQLite."""
    with (
        closing(
            sqlite3.connect(
                (directory.resolve() / "ledger.sqlite3").as_uri() + "?mode=rw", uri=True, timeout=5
            )
        ) as db,
        db,
    ):
        db.execute("BEGIN IMMEDIATE")
        entries = catalog_notes(directory)
        entries.append(note)
        body = json.dumps({"version": 1, "entries": entries}, ensure_ascii=False, indent=2)
        reject_secrets(body, directory=directory)
        if len(body.encode()) > 2_000_000:
            raise ValueError("Local catalog notes exceed 2 MB; no entries replaced")
        target = directory / "model-catalog.json"
        fd, temp = tempfile.mkstemp(dir=directory, prefix="catalog-", suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as stream:
                stream.write(body)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temp, target)
        finally:
            Path(temp).unlink(missing_ok=True)


def catalog_entries(directory: Path, profiles: tuple[ModelProfile, ...] = ()) -> list[CatalogEntry]:
    value = json.loads(Path(__file__).with_name("model_catalog.json").read_text(encoding="utf-8"))
    entries = [CatalogEntry(**item) for item in value["entries"]]
    fields = set(CatalogEntry.__dataclass_fields__)
    for item in catalog_notes(directory):
        identity = item.get("identity", {})
        entries.append(CatalogEntry(**{k: v for k, v in identity.items() if k in fields}))
    # Existing custom profiles remain selectable even if their optional descriptive note is absent.
    known = {e.model_id for e in entries}
    for p in profiles:
        if p.model_id not in known:
            entries.append(CatalogEntry("User registered", "Custom", p.model_id, p.id))
    return [CatalogEntry("Other / Custom", "Custom", "", kind="custom"), *entries]


def search_catalog(entries: list[CatalogEntry], query: str) -> list[CatalogEntry]:
    words = query.casefold().split()
    return [
        entry
        for entry in entries
        if all(
            word in " ".join(str(v) for v in asdict(entry).values()).casefold() for word in words
        )
    ]


@dataclass(frozen=True)
class Connection:
    key: str
    title: str
    adapter: str | None
    protocol: str
    base_url: str = ""
    credential: str = "MODEL_API_KEY"
    local: bool = False
    source: str = ""


CONNECTIONS: tuple[Connection, ...] = (
    Connection(
        "openai_responses",
        "Native APIs / OpenAI Responses",
        "openai",
        "openai",
        credential="OPENAI_API_KEY",
    ),
    Connection("openai", "Native APIs / OpenAI", "openai", "openai", credential="OPENAI_API_KEY"),
    Connection(
        "anthropic", "Native APIs / Anthropic", "claude", "claude", credential="ANTHROPIC_API_KEY"
    ),
    Connection(
        "gemini",
        "Native APIs / Google Gemini",
        "gemini",
        "gemini",
        credential="GOOGLE_API_KEY",
    ),
    Connection(
        "xai",
        "Native APIs / xAI (registration only; compatible endpoint is separate)",
        None,
        "xai",
        credential="XAI_API_KEY",
    ),
    Connection(
        "cohere",
        "Native APIs / Cohere (registration only)",
        None,
        "cohere",
        credential="COHERE_API_KEY",
    ),
    Connection(
        "openrouter",
        "Hosted / OpenRouter — chat completions",
        "openai_compatible",
        "openai_compatible",
        "https://openrouter.ai/api/v1",
        "OPENROUTER_API_KEY",
        source="https://openrouter.ai/docs/api-reference/overview",
    ),
    Connection(
        "together",
        "Hosted / Together AI — chat completions",
        "openai_compatible",
        "openai_compatible",
        "https://api.together.ai/v1",
        "TOGETHER_API_KEY",
        source="https://docs.together.ai/docs/openai-api-compatibility",
    ),
    Connection(
        "fireworks",
        "Hosted / Fireworks AI — chat completions",
        "openai_compatible",
        "openai_compatible",
        "https://api.fireworks.ai/inference/v1",
        "FIREWORKS_API_KEY",
        source="https://docs.fireworks.ai/tools-sdks/openai-compatibility",
    ),
    Connection(
        "groq",
        "Hosted / Groq — chat completions",
        "openai_compatible",
        "openai_compatible",
        "https://api.groq.com/openai/v1",
        "GROQ_API_KEY",
        source="https://console.groq.com/docs/openai",
    ),
    Connection(
        "runpod",
        "Hosted / RunPod — existing vLLM OpenAI endpoint",
        "runpod",
        "runpod",
        credential="RUNPOD_API_KEY",
    ),
    Connection(
        "ollama",
        "Local / Ollama — OpenAI-compatible server",
        "openai_compatible",
        "openai_compatible",
        "http://127.0.0.1:11434/v1",
        local=True,
        source="https://docs.ollama.com/openai",
    ),
    Connection(
        "vllm",
        "Self-hosted / vLLM — compatible server",
        "openai_compatible",
        "openai_compatible",
        local=True,
    ),
    Connection(
        "lmstudio",
        "Local / LM Studio — compatible server",
        "openai_compatible",
        "openai_compatible",
        "http://127.0.0.1:1234/v1",
        local=True,
        source="https://lmstudio.ai/docs/developer/openai-compat",
    ),
    Connection(
        "sglang",
        "Self-hosted / SGLang — compatible server",
        "openai_compatible",
        "openai_compatible",
        local=True,
        source="https://docs.sglang.ai/basic_usage/openai_api.html",
    ),
    Connection("bedrock", "Deployment services / AWS Bedrock (registration only)", None, "bedrock"),
    Connection(
        "vertex", "Deployment services / Google Vertex AI (registration only)", None, "vertex"
    ),
    Connection(
        "azure", "Deployment services / Azure native API (registration only)", None, "azure"
    ),
    Connection(
        "custom",
        "Other / Custom connection or compatible endpoint",
        "openai_compatible",
        "openai_compatible",
    ),
)
CONNECTIONS += tuple(
    Connection(
        key,
        "Local account CLIs / " + title,
        key if key == "codex_cli" else None,
        key,
        credential="",
    )
    for key, title in (
        ("codex_cli", "Codex CLI"),
        ("claude_cli", "Claude Code"),
        ("gemini_cli", "Gemini CLI"),
        ("copilot_cli", "GitHub Copilot CLI"),
    )
)
# The menu starts with keyless local servers, then sign-in, then optional API keys.
CONNECTIONS = tuple(
    sorted(
        CONNECTIONS,
        key=lambda c: (0 if c.local else 1 if c.key == "codex_cli" else 2),
    )
)
CONNECTION_BY_ID = {c.key: c for c in CONNECTIONS}
PROTOCOLS = {
    "openai_compatible": "OpenAI-compatible Chat Completions",
    "openai": "OpenAI official Chat Completions (existing adapter)",
    "claude": "Anthropic official Messages (existing adapter)",
    "runpod": "RunPod vLLM OpenAI endpoint (not Jobs API)",
    "gemini": "Gemini native generateContent",
    "xai": "xAI native — unsupported; choose compatible Chat explicitly if applicable",
    "cohere": "Cohere native — unsupported",
    "bedrock": "Bedrock SigV4 — unsupported",
    "vertex": "Vertex native — unsupported",
    "azure": "Azure API-key native — unsupported",
    "ollama_native": "Ollama /api/chat native — unsupported",
    "responses": "Responses API — unsupported by current DOXA adapter",
}
