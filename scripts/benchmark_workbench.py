"""Time read-only terminal projections on an already initialized workspace."""

import argparse
from pathlib import Path
from statistics import median
from time import perf_counter
from uuid import UUID

from doxa.cli.activity import operations
from doxa.core.config import Settings
from doxa.core.controller import Controller
from doxa.core.investigation import claim_threads, claim_threads_from_events
from doxa.core.models import Experiment
from doxa.core.workspaces import validate_workspace


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("workspace", type=Path)
    parser.add_argument("run", type=UUID)
    args = parser.parse_args()
    controller = Controller(Settings(data_dir=validate_workspace(args.workspace)))
    bundle = controller.inspect(args.run)
    events = list(bundle.events)
    branch = events[0].trajectory_id
    experiment = controller.ledger.get(bundle.run.experiment_id)
    assert isinstance(experiment, Experiment)
    workloads = {
        "Full poll read (baseline)": lambda: controller.inspect(args.run),
        "Unchanged poll read": lambda: (
            controller.ledger.latest_event_id(args.run),
            controller.run_accounting(args.run),
        ),
        "Claim projection incl. DB read (baseline)": lambda: claim_threads(
            controller, args.run, branch
        ),
        "Claim projection from loaded bundle": lambda: claim_threads_from_events(events, branch),
        "Activity search": lambda: operations(events, experiment, "reasoning"),
        "Activity search, 10× in-memory events": lambda: operations(
            events * 10, experiment, "reasoning"
        ),
    }
    print(f"{len(events)} committed events; median of 9 warm timings, milliseconds")
    for name, workload in workloads.items():
        workload()
        samples = []
        for _ in range(9):
            start = perf_counter()
            workload()
            samples.append((perf_counter() - start) * 1000)
        print(f"{name}: {median(samples):.2f} ms")


if __name__ == "__main__":
    main()
