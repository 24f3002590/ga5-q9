from hashing import fingerprint_dossier, make_call_id
from storage import get_cached_proposal, cache_proposal
from validators import (
    validate_action,
    validate_evidence,
)
from ai import call_model


class ProposalError(Exception):
    pass


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


async def build_proposal(dossier, allowed_actions):

    dossier_hash = fingerprint_dossier(dossier)

    cached = get_cached_proposal(dossier_hash)

    if cached:
        return cached

    ai = await call_model(
        dossier,
        allowed_actions,
    )

    action = ai["action"]

    validate_action(action, allowed_actions)

    valid_line_ids = collect_line_ids(dossier)

    validate_evidence(
        ai["evidence"],
        valid_line_ids,
    )

    proposal = {
        "dossierId": dossier["dossierId"],
        "callId": make_call_id(dossier_hash),
        "action": action,
        "target": build_target(
            action,
            dossier["mailbox"],
            ai["fields"],
        ),
        "payload": build_payload(
            action,
            ai["fields"],
        ),
        "evidence": sorted(ai["evidence"]),
    }

    cache_proposal(
        dossier_hash,
        proposal,
    )

    return proposal


async def build_all_proposals(
    dossiers,
    allowed_actions,
):
    proposals = []

    for dossier in dossiers:
        proposal = await build_proposal(
            dossier,
            allowed_actions,
        )

        proposals.append(proposal)

    return proposals
