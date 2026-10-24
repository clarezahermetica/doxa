"""Scan publishable working files or staged blobs without displaying secret values."""

import argparse
import re
import subprocess
from pathlib import Path

from doxa.core.secrets import secret_values

parser = argparse.ArgumentParser()
parser.add_argument("--staged", action="store_true")
args = parser.parse_args()
command = ["git", "ls-files", "-z", "--cached"]
if not args.staged:
    command += ["--others", "--exclude-standard"]
files = sorted(set(subprocess.check_output(command).decode().strip("\0").split("\0")))
known = [value.encode() for value in secret_values()]
patterns = {
    "Moss token": rb"moss_[A-Za-z0-9]{24,}",
    "GitHub token": rb"gh[pousr]_[A-Za-z0-9]{24,}",
    "GitHub fine-grained token": rb"github_pat_[A-Za-z0-9_]{24,}",
    "RunPod token": rb"rpa_[A-Za-z0-9_-]{24,}",
    "Hugging Face token": rb"hf_[A-Za-z0-9]{24,}",
    "private key": rb"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----",
    "AWS access ID": rb"AKIA[A-Z0-9]{16}",
    "provider secret": rb"sk-(?:proj-|ant-)?[A-Za-z0-9_-]{24,}",
}
forbidden = {".venv", ".doxa", "node_modules", "private", "exports", ".moss"}
failures = []
for name in files:
    if not name:
        continue
    path = Path(name)
    if set(path.parts) & forbidden or (
        path.name.startswith(".env") and path.name != ".env.example"
    ):
        failures.append((name, "excluded local path"))
    data = (
        subprocess.check_output(["git", "show", ":" + name]) if args.staged else path.read_bytes()
    )
    if any(value in data for value in known):
        failures.append((name, "configured secret"))
    for label, pattern in patterns.items():
        if re.search(pattern, data):
            failures.append((name, label))
    for match in re.finditer(
        rb"(?m)^([A-Z0-9_]*(?:KEY|TOKEN|SECRET|PASSWORD))=[\"']?([^\r\n]+)", data
    ):
        value = match[2].strip(b"\"' ")
        if value and value not in {b"replace_me", b"", b"false"}:
            failures.append((name, "embedded credential assignment"))
for name, category in failures:
    print(f"FAIL {name}: {category}")
print(
    f"Scanned {len(files)} {'staged blobs' if args.staged else 'publishable files'}; "
    f"{len(failures)} secret/path findings. No secret values printed."
)
raise SystemExit(bool(failures))
