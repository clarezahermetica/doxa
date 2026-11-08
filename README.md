# DOXA

A terminal research environment for studying how AI agents make, challenge and revise claims.

DOXA records experiments, evidence, criticism and revisions for inspection and comparison.
It runs locally and can connect to configured model providers. It is an unfinished proof
of concept; the [status page](docs/status.md) distinguishes implemented behavior, recorded
verification and remaining limitations.

## Installation

Install from this source repository with **Python 3.12 or newer** and Git. The terminal
does not require Node.js or a browser. No public binary release is provided.

### Windows PowerShell

Confirm `py -3 --version` selects Python 3.12 or newer, then:

```powershell
git clone https://github.com/clarezahermetica/doxa.git
cd doxa
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e .
.\.venv\Scripts\doxa.exe --version
.\.venv\Scripts\doxa.exe
```

### macOS and Linux

Confirm `python3 --version` is 3.12 or newer, then:

```bash
git clone https://github.com/clarezahermetica/doxa.git
cd doxa
python3 -m venv .venv
.venv/bin/python -m pip install -e .
.venv/bin/doxa --version
.venv/bin/doxa
```

These commands use the checkout's virtual environment directly. If you already have a
checkout, use that directory instead of cloning another copy. An installed frozen Windows
application is separate from this environment; source installation does not upgrade it.

## First experiment

Open DOXA and explicitly create a new workspace or select an existing one. Keep active
workspaces outside synchronization folders where practical. F1 opens guidance; Ctrl+P
opens commands. Follow the [offline exercise](docs/canonical-research.md) to inspect
evidence, claims, criticism, revisions and exports without a model account or live call.

Configure live models separately through the [provider guide](docs/providers.md).
Saving a connection does not invoke it. A live start requires the applicable disclosure,
spending or subscription-quota acknowledgment and explicit run limits.

## Documentation

The [documentation index](docs/README.md) links the eight main guides. Start with the
[workbench](docs/workbench.md) for terminal use or
[development guide](docs/development.md) for tests and internal packaging.
