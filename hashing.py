import hashlib
import json
import base64
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


def compute_input_digest(dossiers) -> str:
    """
    SHA256 of canonical dossiers JSON.
    """

    if hasattr(dossiers, "model_dump"):
        payload = dossiers.model_dump(mode="json")
    else:
        payload = dossiers

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

    if hasattr(dossier, "model_dump"):
        payload = dossier.model_dump(mode="json")
    else:
        payload = dossier

    canonical = canonical_json(payload)

    return sha256_hex(canonical.encode("utf-8"))
