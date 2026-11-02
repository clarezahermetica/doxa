from pathlib import Path
from typing import TYPE_CHECKING, Any
from uuid import UUID

if TYPE_CHECKING:
    from doxa.core.controller import Controller


def export_run(controller: "Controller", run_id: UUID, destination: Path) -> Path:
    """Exact ledger export; never overwrite another export or include credentials."""
    if destination.suffix.lower() == ".zip":
        return export_archive(controller, run_id, destination)
    from doxa.core.local_files import atomic_write
    from doxa.core.secrets import reject_secrets

    content = controller.inspect(run_id).model_dump_json(indent=2)
    reject_secrets(content, directory=controller.settings.data_dir)
    atomic_write(destination.expanduser(), content.encode(), replace=False)
    return destination.expanduser().resolve()


def export_jsonl(controller: "Controller", run_id: UUID, destination: Path) -> Path:
    import json

    from doxa.core.local_files import atomic_write
    from doxa.core.secrets import reject_secrets

    bundle = controller.inspect(run_id)
    manifest = {
        "kind": "export_manifest",
        "schema_version": 1,
        "run": bundle.run.model_dump(mode="json"),
        "accounting": bundle.accounting,
    }
    lines = [json.dumps(manifest), *(event.model_dump_json() for event in bundle.events)]
    for line in lines:
        reject_secrets(line, directory=controller.settings.data_dir)
    atomic_write(destination.expanduser(), ("\n".join(lines) + "\n").encode(), replace=False)
    return destination.expanduser().resolve()


def export_archive(controller: "Controller", run_id: UUID, destination: Path) -> Path:
    """Portable history, pinned configurations and recursively referenced verified artifacts."""
    import hashlib
    import json
    import os
    import tempfile
    import zipfile

    from doxa.core.models import ArtifactRef, Experiment
    from doxa.core.secrets import reject_artifact_secrets, reject_secrets
    from doxa.storage.artifacts import ArtifactStore
    from doxa.storage.configurations import ConfigurationStore

    destination = destination.expanduser().resolve()
    if destination.exists():
        raise FileExistsError("Export destination already exists")
    bundle = controller.inspect(run_id)
    experiment = controller.ledger.get(bundle.run.experiment_id)
    assert isinstance(experiment, Experiment)
    configs = ConfigurationStore(controller.settings.database_path)
    profiles = [
        configs.get("profile", a.model_profile_id, a.model_profile_version).model_dump(mode="json")
        for a in experiment.agents
        if a.model_profile_id
    ]
    files: dict[str, bytes] = {
        "history.json": bundle.model_dump_json(indent=2).encode(),
        "configuration.json": json.dumps(
            {"experiment": experiment.model_dump(mode="json"), "profiles": profiles},
            sort_keys=True,
            indent=2,
        ).encode(),
    }
    store = ArtifactStore(controller.settings.data_dir / "artifacts")
    seen: set[str] = set()

    def visit(value: Any) -> None:
        if isinstance(value, list):
            for item in value:
                visit(item)
        elif isinstance(value, dict):
            if {"sha256", "relative_path", "size_bytes", "media_type"}.issubset(value):
                ref = ArtifactRef.model_validate(value)
                if ref.sha256 in seen:
                    return
                seen.add(ref.sha256)
                content = store.get(ref)
                reject_artifact_secrets(content, directory=controller.settings.data_dir)
                files["artifacts/" + ref.relative_path] = content
                if ref.media_type == "application/json":
                    visit(json.loads(content))
            else:
                for item in value.values():
                    visit(item)

    for data in tuple(files.values()):
        reject_secrets(data.decode(), directory=controller.settings.data_dir)
        visit(json.loads(data))
    manifest = {
        "format": "doxa-research-export-v1",
        "run_id": str(run_id),
        "files": {
            name: {"sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data)}
            for name, data in sorted(files.items())
        },
    }
    files["manifest.json"] = json.dumps(manifest, sort_keys=True, indent=2).encode()
    descriptor, temporary = tempfile.mkstemp(dir=destination.parent, prefix="doxa-export-")
    os.close(descriptor)
    try:
        with zipfile.ZipFile(temporary, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for name, data in sorted(files.items()):
                archive.writestr(name, data)
        # Atomic publication with exclusive destination creation; never replace an export.
        os.link(temporary, destination)
    finally:
        Path(temporary).unlink(missing_ok=True)
    return destination
