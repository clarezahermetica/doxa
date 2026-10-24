import asyncio
import json
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from typer.testing import CliRunner

from doxa.api.app import create_app
from doxa.cli.main import app
from doxa.core.config import Settings
from doxa.core.controller import CapabilityUnavailable, ConfigureRun, Controller
from doxa.core.models import ProtocolMode
from doxa.environments.sandbox import DisabledSandbox, SandboxLimits
from doxa.storage.artifacts import ArtifactStore


def test_cli_http_export_agree_and_execution_is_explicitly_unavailable(
    tmp_path: Path,
    command: ConfigureRun,
):
    config = tmp_path / "command.json"
    config.write_text(command.model_dump_json(), encoding="utf-8")
    runner = CliRunner()
    assert runner.invoke(app, ["init", "--data-dir", str(tmp_path)]).exit_code == 0
    result = runner.invoke(app, ["configure", str(config), "--data-dir", str(tmp_path)])
    assert result.exit_code == 0, result.output
    run_id = json.loads(result.output)["id"]
    cli = runner.invoke(app, ["inspect", run_id, "--data-dir", str(tmp_path)])
    assert cli.exit_code == 0, cli.output
    with TestClient(create_app(Settings(data_dir=tmp_path))) as client:
        bundle = client.get(f"/api/runs/{run_id}").json()
        assert bundle == json.loads(cli.output)
        assert bundle == client.get(f"/api/runs/{run_id}/export").json()
        assert client.post("/api/runs", json=command.model_dump(mode="json")).status_code == 201
        assert len(client.get("/api/runs").json()) == 1
        assert client.post(f"/api/runs/{run_id}/execute").status_code == 501
        assert client.get(f"/api/runs/{uuid4()}").status_code == 404
        assert client.get("/api/runs/not-a-uuid").status_code == 422
        assert client.get("/api/health", headers={"host": "attacker.example"}).status_code == 400
        assert (
            client.options(
                "/api/runs",
                headers={
                    "origin": "https://attacker.example",
                    "access-control-request-method": "POST",
                },
            ).status_code
            == 405
        )
    assert len(bundle["events"]) == 1


@pytest.mark.parametrize("mode", list(ProtocolMode))
def test_all_protocol_slots_are_honest_contracts(
    controller: Controller,
    command: ConfigureRun,
    mode: ProtocolMode,
):
    run = controller.configure_run(command.model_copy(update={"mode": mode}))
    assert run.mode == mode and run.status == "configured"
    with pytest.raises(CapabilityUnavailable):
        controller.execute(run.id)


def test_sandbox_fails_closed(tmp_path):
    source = ArtifactStore(tmp_path).put(b"never executed")
    with pytest.raises(CapabilityUnavailable, match="disabled"):
        asyncio.run(DisabledSandbox().execute(source, SandboxLimits()))
