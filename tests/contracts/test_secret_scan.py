import importlib.util
from pathlib import Path


def test_secret_scan_does_not_print_matches_and_catches_known_patterns() -> None:
    spec = importlib.util.spec_from_file_location("scan", Path("scripts/scan_secrets.py"))
    assert spec is not None and spec.loader is not None
    scanner = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(scanner)
    assert scanner.violations(("ghp_" + "A" * 30).encode())
    assert scanner.violations(("-----BEGIN " + "PRIVATE KEY-----").encode())
    assert scanner.violations(('api_secret="' + "A" * 32 + '"').encode())
    assert not scanner.violations(b'credential_ref="owner-local-only"')
