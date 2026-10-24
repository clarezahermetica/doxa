from pathlib import Path

import pytest

from doxa.core.config import Settings
from doxa.core.controller import ConfigureRun, Controller
from doxa.core.models import Experiment


@pytest.fixture
def controller(tmp_path: Path) -> Controller:
    controller = Controller(Settings(data_dir=tmp_path))
    controller.initialize()
    return controller


@pytest.fixture
def command() -> ConfigureRun:
    return ConfigureRun(
        idempotency_key="test-command",
        execution_kind="synthetic",
        experiment=Experiment(
            name="Synthetic contract test",
            task_id="test",
            task_version="1",
            environment_version="1",
            policy_version="1",
            evaluator_version="1",
        ),
    )
