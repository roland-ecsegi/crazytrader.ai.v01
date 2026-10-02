"""Scan tracked/worktree source; report locations only, never matched values.

This baseline catches common credentials; Phase 14 adds dedicated supply-chain
and secret tooling. It cannot prove arbitrary strings contain no secrets.
"""

import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PATTERNS = (
    re.compile(rb"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    re.compile(rb"\b(?:ghp_|github_pat_|sk-ant-)[A-Za-z0-9_-]{20,}"),
    re.compile(rb"(?i)(?:api_secret|binance_secret|unseal_key)\s*[=:]\s*['\"][^'\"\s]{16,}['\"]"),
)


def violations(data: bytes) -> bool:
    return any(pattern.search(data) for pattern in PATTERNS)


def main() -> None:
    paths = subprocess.check_output(
        ["git", "ls-files", "-z", "--cached", "--others", "--exclude-standard"], cwd=ROOT
    ).split(b"\0")
    failures = []
    for raw in paths:
        if not raw:
            continue
        path = ROOT / raw.decode()
        if path.is_file() and violations(path.read_bytes()):
            failures.append(str(path.relative_to(ROOT)))
    if failures:
        raise SystemExit("credential pattern found in: " + ", ".join(failures))
    print("baseline source secret scan clean")


if __name__ == "__main__":
    main()
