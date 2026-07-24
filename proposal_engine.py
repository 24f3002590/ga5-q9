import asyncio

from hashing import fingerprint_dossier, make_call_id
from storage import get_cached_proposal, cache_proposal
from validators import (
    validate_action,
    validate_evidence,
    validate_target,
    validate_payload,
    ValidationError,
)
from ai import call_model, AIError


class ProposalError(Exception):
    pass


REQUIRED_FIELDS = {
    "create_draft": {"recipient", "referenceId", "status"},
    "update_internal_record": {"caseId", "sourceEventId", "value"},
    "send_approved_notice": {"recipient", "referenceId", "status"},
    "request_confirmation": {"team", "claimedSender", "referenceId"},
    "quarantine_item": {"artifactId"},
    "no_action": {"reasonCode", "referenceId"},
}


def collect_line_ids(dossier: dict):
    ids = set()

    for source in dossier["sources"]:
        for line in source["lines"]:
            ids.add(line["lineId"])

    return ids


def build_target(action, mailbox, extracted):

    if action == "create_draft":
        return {
            "kind": "draft_queue",
            "id": f"mailbox:{mailbox}",
        }

    if action == "update_internal_record":
        return {
            "kind": "case_record",
            "id": extracted["caseId"],
        }

    if action == "send_approved_notice":
        return {
            "kind": "email",
            "id": extracted["recipient"],
        }

    if action == "request_confirmation":
        return {
            "kind": "approval_queue",
            "id": extracted["team"],
        }

    if action == "quarantine_item":
        return {
            "kind": "security_queue",
            "id": "mailroom",
        }

    return None


def build_payload(action, extracted):

    if action == "create_draft":
        return {
            "recipient": extracted["recipient"],
            "referenceId": extracted["referenceId"],
            "status": extracted["status"],
            "template": "order_status",
        }

    if action == "update_internal_record":
        return {
            "field": "delivery_window",
            "sourceEventId": extracted["sourceEventId"],
            "value": extracted["value"],
        }

    if action == "send_approved_notice":
        return {
            "referenceId": extracted["referenceId"],
            "status": extracted["status"],
            "template": "approved_delivery_notice",
        }

    if action == "request_confirmation":
        return {
            "claimedSender": extracted["claimedSender"],
            "questionCode": "VERIFY_REQUEST",
            "referenceId": extracted["referenceId"],
        }

    if action == "quarantine_item":
        return {
            "artifactId": extracted["artifactId"],
            "reasonCode": "INDIRECT_PROMPT_INJECTION",
        }

    return {
        "reasonCode": extracted["reasonCode"],
        "referenceId": extracted["referenceId"],
    }


def fallback_result(dossier: dict, valid_line_ids):
    """
    Used only when the model call fails, times out, or returns something
    that doesn't validate. Always produces a schema-valid, non-outbound,
    non-destructive proposal so a bug/timeout in the AI layer never breaks
    contract shape or performs an unsafe action. Routes to a human queue.
    """

    any_line = next(iter(valid_line_ids)) if valid_line_ids else None

    evidence = [any_line] if any_line else []

    return {
        "action": "request_confirmation",
        "target": {"kind": "approval_queue", "id": "mailroom-ops"},
        "payload": {
            "claimedSender": "unknown",
            "questionCode": "VERIFY_REQUEST",
            "referenceId": dossier.get("dossierId", "unknown"),
        },
        "evidence": evidence,
    }


async def build_proposal(dossier: dict, allowed_actions: list):

    dossier_hash = fingerprint_dossier(dossier)

    cached = get_cached_proposal(dossier_hash)
    if cached:
        return cached

    valid_line_ids = collect_line_ids(dossier)

    try:
        ai = await call_model(dossier, allowed_actions)

        action = ai["action"]
        validate_action(action, allowed_actions)

        evidence = sorted(ai["evidence"])
        validate_evidence(evidence, valid_line_ids)

        extracted = ai.get("fields", {})
        if not isinstance(extracted, dict):
            raise ValidationError("fields must be an object")

        required = REQUIRED_FIELDS.get(action, set())
        missing = required - set(extracted.keys())
        if missing:
            raise ValidationError(
                f"Missing fields {missing} for action {action}"
            )

        target = build_target(action, dossier["mailbox"], extracted)
        payload = build_payload(action, extracted)

        validate_target(action, target)
        validate_payload(action, payload)

        result = {
            "action": action,
            "target": target,
            "payload": payload,
            "evidence": evidence,
        }

    except (AIError, ValidationError, KeyError, TypeError, ValueError):
        result = fallback_result(dossier, valid_line_ids)

    proposal = {
        "dossierId": dossier["dossierId"],
        "callId": make_call_id(dossier_hash),
        **result,
    }

    cache_proposal(dossier_hash, proposal)

    return proposal


async def build_all_proposals(
    dossiers,
    allowed_actions,
    concurrency: int = 8,
):
    """
    Run model calls concurrently (bounded) instead of one-by-one, since
    a Check batches 64+ dossiers and each request only has ~55s.
    asyncio.gather preserves input order in its results regardless of
    completion order.
    """

    semaphore = asyncio.Semaphore(concurrency)

    async def _one(dossier):
        async with semaphore:
            return await build_proposal(dossier, allowed_actions)

    tasks = [_one(d) for d in dossiers]

    return await asyncio.gather(*tasks)
