# Documentation

Start with the installation instructions in the repository [README](../README.md).

| Guide | Purpose |
| --- | --- |
| [Workbench](workbench.md) | Terminal navigation, models, agents, experiments and evidence. |
| [Offline research exercise](canonical-research.md) | A complete synthetic workflow and independently inspectable exports. |
| [Architecture](architecture.md) | Controller, ledger, adapters and research boundaries. |
| [Research systems](research-systems.md) | The six systems and their finite cache-policy checks. |
| [Provider support](provider-support.md) | Implemented transports, mocked verification and unsupported capabilities. |
| [Live acceptance](live-acceptance.md) | Separately authorized provider/model/spending checks. |
| [Storage](storage-map.md) and [recovery](recovery.md) | Workspace paths, backups, interrupted calls and reservations. |
| [Windows packaging](windows-installation.md) | Optional internal builds, installation and removal. |
| [Status](status.md) | Observed verification and remaining limitations. |
| [Design references](sources.md) | Original design provenance; not implementation acceptance. |

## Development checks

From the repository root after creating the Python environment described in README:

```powershell
.\.venv\Scripts\python.exe -m pip install -e '.[dev]'
.\.venv\Scripts\python.exe -m pytest
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m mypy --platform linux
.\.venv\Scripts\python.exe -m mypy --platform win32
.\.venv\Scripts\python.exe scripts/export_contracts.py
git diff --exit-code docs/contracts
```

The public regression suite is used by GitHub CI and is not bundled in the installed
application. It uses synthetic fixtures and mocked providers; passing tests do not
establish live-provider compatibility or research quality. Actual credentials and
research workspaces must remain private and outside the source tree.

Earlier pass reports, copied specifications and retired GUI instructions remain in Git
history. They are not current setup instructions. Current generated contracts are in
[contracts](contracts/).
