"""Assemble a separately versioned Windows terminal distribution; never rewrite old ZIPs."""

import hashlib
import json
import shutil
import sys
import zipfile
from pathlib import Path

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root / "src"))
from doxa.version import TERMINAL_BUILD, VERSION  # noqa: E402

build = sys.argv[1] if len(sys.argv) > 1 else TERMINAL_BUILD
if build != TERMINAL_BUILD:
    raise ValueError("Build directory must match the shared terminal build identity")
folder = root / "dist" / f"DOXA-Terminal-{build}"
archive = root / "dist" / f"DOXA-Terminal-{build}-Windows.zip"
if archive.exists():
    raise FileExistsError("Existing distributions are never replaced")
for name in ("Install-DOXA.ps1", "Uninstall-DOXA.ps1", "DOXA-InstallCommon.ps1"):
    shutil.copyfile(root / "scripts/windows" / name, folder / name)
shutil.copyfile(root / "docs/windows-installation.md", folder / "INSTALLATION.md")
shutil.copyfile(root / "docs/canonical-research.md", folder / "OFFLINE-RESEARCH.md")
shutil.copytree(root / "examples/canonical-research", folder / "examples/canonical-research")
shutil.copyfile(
    root / "scripts/inspect_research_archive.py", folder / "inspect_research_archive.py"
)
files = []
for path in sorted(folder.rglob("*")):
    if not path.is_file() or path.name == "package-manifest.json":
        continue
    relative = path.relative_to(folder).as_posix()
    if path.is_symlink() or set(path.relative_to(folder).parts) & {
        ".env",
        ".doxa",
        "credentials",
        "node_modules",
        "ledger.sqlite3",
        "private",
    }:
        raise ValueError("Private or linked distribution entry refused")
    files.append({"path": relative, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()})
(folder / "package-manifest.json").write_text(
    json.dumps(
        {
            "application": "DOXA",
            "format": 1,
            "version": VERSION,
            "build": build,
            "files": files,
        },
        indent=2,
    ),
    encoding="utf-8",
)
with zipfile.ZipFile(archive, "x", compression=zipfile.ZIP_DEFLATED) as output:
    for path in sorted(folder.rglob("*")):
        if path.is_file():
            output.write(path, path.relative_to(folder).as_posix())
print(
    json.dumps(
        {
            "archive": str(archive),
            "bytes": archive.stat().st_size,
            "sha256": hashlib.sha256(archive.read_bytes()).hexdigest(),
        }
    )
)
