"""Canonical typed artifacts and stable SHA-256 identities."""

import hashlib
import json

from .models import Contract


def canonical(model: Contract) -> str:
    return json.dumps(model.model_dump(mode="json"), sort_keys=True, separators=(",", ":"))


def digest(body: str) -> str:
    return hashlib.sha256(body.encode()).hexdigest()
