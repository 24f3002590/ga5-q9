import copy
from typing import List

from ai import call_model
from hashing import (
    fingerprint_dossier,
    make_call_id,
)
from storage import (
    get_cached_proposal,
    cache_proposal,
)


class ProposalError(Exception):
    pass


def collect_line_ids(dossier: dict) -> set[str]:
    """
    Return every valid lineId in the dossier.
    """
    ids = set()

    for source in dossier["sources"]:
        for line in source["lines"]:
            ids.add(line["lineId"])

    return ids


def validate_target(action: str, target):
    if action == "no_action":
        if target is not None:
            raise ProposalError("no_action target must be null")
    else:
        if not isinstance(target, dict):
            raise ProposalError("Missing target")

        if "kind" not in target or "id" not in target:
            raise ProposalError("Invalid target")


def validate_payload(payload):
    if not isinstance(payload, dict):
        raise ProposalError("Payload must be object")


def validate_evidence(
    evidence: List[str],
    dossier: dict,
):
    if not evidence:
        raise ProposalError("Evidence missing")

    valid = collect_line_ids(dossier)

    if len(evidence) != len(set(evidence)):
        raise ProposalError("Duplicate evidence")

    for e in evidence:
        if e not in valid:
            raise ProposalError(f"Unknown lineId {e}")


async def build_proposal(
    dossier: dict,
    allowed_actions: list,
):
    """
    Produce one proposal.
    """

    dossier_hash = fingerprint_dossier(dossier)

    cached = get_cached_proposal(dossier_hash)

    if cached:
        return cached

    ai_result = await call_model(
        dossier,
        allowed_actions,
    )

    action = ai_result.get("action")

    if action not in allowed_actions:
        raise ProposalError("Illegal action")

    target = ai_result.get("target")

    payload = ai_result.get("payload")

    evidence = ai_result.get("evidence")

    validate_target(action, target)
    validate_payload(payload)
    validate_evidence(evidence, dossier)

    proposal = {
        "dossierId": dossier["dossierId"],
        "callId": make_call_id(dossier_hash),
        "action": action,
        "target": target,
        "payload": payload,
        "evidence": sorted(evidence),
    }

    cache_proposal(
        dossier_hash,
        proposal,
    )

    return proposal


async def build_all_proposals(
    dossiers: list,
    allowed_actions: list,
):
    proposals = []

    for dossier in dossiers:
        p = await build_proposal(
            copy.deepcopy(dossier),
            allowed_actions,
        )

        proposals.append(p)

    return proposals
