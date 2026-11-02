"""Owned failure-injection processes; never a production launcher or real network client."""

import asyncio
import json
import os
import sys
import time
from pathlib import Path
from uuid import UUID, uuid4

from doxa.core.config import Settings
from doxa.core.controller import ConfigureRun, Controller
from doxa.core.models import Agent, Experiment, Role
from doxa.core.profiles import AgentDefinition, CouncilConfig, ModelProfile


def main():
    mode, folder, marker, *extra = sys.argv[1:]
    workspace, ready = Path(folder), Path(marker)
    controller = Controller(Settings(data_dir=workspace))
    controller.initialize()

    def acknowledge(**values):
        ready.write_text(
            json.dumps({"pid": os.getpid(), "parent_pid": os.getppid(), **values}), encoding="utf-8"
        )

    def wait_forever():
        while True:
            time.sleep(0.1)

    if mode in {"theme", "viewer"}:
        from doxa.cli.console import ResearchConsole

        async def scenario():
            app = ResearchConsole(workspace, show_guide=False)
            async with app.run_test(size=(80, 24)) as pilot:
                if mode == "theme":
                    app.theme = "nord"
                await pilot.pause()
                acknowledge(theme=app.theme)
                await asyncio.Event().wait()

        asyncio.run(scenario())
    elif mode in {"window", "window_owner"}:
        import ctypes

        from doxa.cli.console import ResearchConsole

        class WindowProbe(ResearchConsole):
            def on_mount(self):
                super().on_mount()
                self.theme = "nord"
                get_window = ctypes.windll.kernel32.GetConsoleWindow
                get_window.restype = ctypes.c_void_p
                details = {}
                if mode == "window_owner":
                    from doxa.cli.operations import start_worker

                    process = start_worker(controller, UUID(extra[0]))
                    details["worker_launcher_pid"] = process.pid
                acknowledge(theme=self.theme, hwnd=get_window(), **details)

        WindowProbe(workspace, show_guide=False).run()
    elif mode == "pending":
        import httpx

        from doxa.core.workbench import DebateExecution, DebateRuntime
        from doxa.providers.runpod import RunPodProvider
        from doxa.storage.budget import BudgetStore

        async def pending(request):
            operations = BudgetStore(controller.settings.database_path).operations()
            assert len(operations) == 1 and operations[0]["state"] == "in_flight"
            acknowledge(operation_id=operations[0]["id"])
            await asyncio.Event().wait()

        controller.providers.create = lambda p, env, **kw: RunPodProvider(
            p, env, httpx.MockTransport(pending)
        )
        from decimal import Decimal

        asyncio.run(
            DebateRuntime(controller, UUID(extra[0])).execute_debate(
                DebateExecution(
                    authorize_paid=True,
                    authorize_external=True,
                    upper_bound_usd_per_attempt=Decimal("0.1"),
                )
            )
        )
    elif mode == "ledger":
        from doxa.storage.ledger import Ledger

        original = Ledger._append

        def blocked_commit(self, event, db):
            result = original(self, event, db)
            acknowledge(event_id=str(result.id))
            wait_forever()
            return result

        Ledger._append = blocked_commit
        controller.configure_run(
            ConfigureRun(
                experiment=Experiment(
                    name="Interrupted transaction",
                    task_id="fixture",
                    task_version="1",
                    environment_version="1",
                    policy_version="1",
                    evaluator_version="1",
                ),
                execution_kind="synthetic",
                idempotency_key="crash-ledger",
            )
        )
    elif mode == "configuration":
        import sqlite3
        from contextlib import contextmanager

        from doxa.storage import configurations

        class CommitGate(sqlite3.Connection):
            def __exit__(self, *args):
                acknowledge()
                wait_forever()
                return super().__exit__(*args)

        @contextmanager
        def gated_connection(path):
            db = sqlite3.connect(path, factory=CommitGate)
            db.execute("PRAGMA foreign_keys=ON")
            try:
                yield db
            finally:
                db.close()

        configurations.connection = gated_connection
        identity = uuid4()
        profile = ModelProfile(id="uncommitted", provider="openai", model_id="fixture")
        agent = AgentDefinition(
            id=identity,
            display_name="Uncommitted template",
            agent=Agent(id=identity, role=Role.RESEARCHER, instructions="Fixture"),
            model_profile_id=profile.id,
            model_profile_version=1,
        )
        controller.save_configuration(CouncilConfig(profiles=(profile,), agents=(agent,)))
    else:
        raise ValueError("Unknown test mode")


if __name__ == "__main__":
    main()
