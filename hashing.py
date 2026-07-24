import hashlib
import json
from typing import Any


def canonical_json(data: Any) -> str:
    """
    Produce recursively key-sorted compact JSON.

    Arrays preserve order.
    """

    return json.dumps(
        data,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _to_plain(value: Any) -> Any:
    """
    Recursively convert Pydantic models (or lists/dicts containing them)
    into plain JSON-safe data. A list of Pydantic models does NOT itself
    have .model_dump(), only its items do -- this is the bug we're fixing.
    """

    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")

    if isinstance(value, list):
        return [_to_plain(v) for v in value]

    if isinstance(value, dict):
        return {k: _to_plain(v) for k, v in value.items()}

    return value


def compute_input_digest(dossiers) -> str:
    """
    SHA256 of canonical dossiers JSON.

    `dossiers` may be a single Pydantic model, a list of Pydantic models,
    a list of plain dicts, or a plain dict -- all are normalized first.
    """

    payload = _to_plain(dossiers)

    canonical = canonical_json(payload)

    return sha256_hex(canonical.encode("utf-8"))


def normalize_proposal(proposal: dict) -> dict:
    """
    Keep ONLY the fields required by the grader.
    Sort evidence before hashing.
    """

    return {
        "dossierId": proposal["dossierId"],
        "callId": proposal["callId"],
        "action": proposal["action"],
        "target": proposal.get("target"),
        "payload": proposal["payload"],
        "evidence": sorted(proposal["evidence"]),
    }


def compute_proposal_digest(proposal: dict) -> str:
    normalized = normalize_proposal(proposal)

    canonical = canonical_json(normalized)

    return sha256_hex(canonical.encode("utf-8"))


def make_call_id(dossier_hash: str) -> str:
    """
    Stable callId.

    Only uses allowed characters.

    call-xxxxxxxxxxxxxxxxxxxxxxxx
    """

    return "call-" + dossier_hash[:24]


def fingerprint_dossier(dossier) -> str:
    """
    Stable dossier fingerprint.

    Used for cache key.
    """

    payload = _to_plain(dossier)

    canonical = canonical_json(payload)

    return sha256_hex(canonical.encode("utf-8"))
