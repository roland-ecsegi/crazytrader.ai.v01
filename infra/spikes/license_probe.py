"""Fetch exact upstream license documents with normal proxy/CA verification."""

import hashlib
import json
from pathlib import Path
from urllib.request import urlopen

SOURCES = {
    "nats": "https://raw.githubusercontent.com/nats-io/nats-server/v2.11.8/LICENSE",
    "opa": "https://raw.githubusercontent.com/open-policy-agent/opa/v1.8.0/LICENSE",
    "openbao": "https://raw.githubusercontent.com/openbao/openbao/v2.3.2/LICENSE",
    "clickhouse": "https://raw.githubusercontent.com/ClickHouse/ClickHouse/v25.8.3.66-lts/LICENSE",
    "mlflow": "https://raw.githubusercontent.com/mlflow/mlflow/v3.4.0/LICENSE.txt",
    "seaweedfs": "https://raw.githubusercontent.com/seaweedfs/seaweedfs/3.97/LICENSE",
    "postgres": "https://raw.githubusercontent.com/postgres/postgres/REL_17_6/COPYRIGHT",
}


def main() -> None:
    records = {}
    for name, url in SOURCES.items():
        print("inspecting", name, flush=True)
        with urlopen(url, timeout=30) as response:
            content = response.read()
        text = content.decode()
        if "Apache License" in text:
            license_name = "Apache-2.0"
        elif "Mozilla Public License" in text:
            license_name = "MPL-2.0"
        elif "PostgreSQL" in text and "Permission to use, copy, modify" in text:
            license_name = "PostgreSQL"
        else:
            raise ValueError(f"unrecognized license: {name}")
        records[name] = {
            "url": url,
            "sha256": hashlib.sha256(content).hexdigest(),
            "license": license_name,
        }
    path = Path(__file__).resolve().parents[2] / "docs/evidence/spikes/platform-licenses.json"
    path.write_text(json.dumps(records, indent=2, sort_keys=True) + "\n")
    print("exact-tag upstream license inspection PASS")


if __name__ == "__main__":
    main()
