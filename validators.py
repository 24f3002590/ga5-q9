from typing import Dict, List


class ValidationError(Exception):
    pass


ACTION_SCHEMAS = {
    "create_draft": {
        "target": {"kind", "id"},
        "payload": {
            "recipient",
            "referenceId",
            "status",
            "template",
        },
    },
    "update_internal_record": {
        "target": {"kind", "id"},
        "payload": {
            "field",
            "sourceEventId",
            "value",
        },
    },
    "send_approved_notice": {
        "target": {"kind", "id"},
        "payload": {
            "referenceId",
            "status",
            "template",
        },
    },
    "request_confirmation": {
        "target": {"kind", "id"},
        "payload": {
            "claimedSender",
            "questionCode",
            "referenceId",
        },
    },
    "quarantine_item": {
        "target": {"kind", "id"},
        "payload": {
            "artifactId",
            "reasonCode",
        },
    },
    "no_action": {
        "target": None,
        "payload": {
            "reasonCode",
            "referenceId",
        },
    },
}


def validate_action(action: str, allowed_actions: List[str]):
    if action not in allowed_actions:
        raise ValidationError(f"Illegal action: {action}")


def validate_target(action: str, target):
    schema = ACTION_SCHEMAS[action]["target"]

    if schema is None:
        if target is not None:
            raise ValidationError("Target must be null")
        return

    if not isinstance(target, dict):
        raise ValidationError("Target missing")

    keys = set(target.keys())

    if keys != schema:
        raise ValidationError("Invalid target fields")


def validate_payload(action: str, payload: Dict):
    if not isinstance(payload, dict):
        raise ValidationError("Payload missing")

    expected = ACTION_SCHEMAS[action]["payload"]

    keys = set(payload.keys())

    if keys != expected:
        raise ValidationError(
            f"Expected payload {expected}, got {keys}"
        )


def validate_evidence(
    evidence,
    valid_line_ids,
):
    if not isinstance(evidence, list):
        raise ValidationError("Evidence must be list")

    if len(evidence) == 0:
        raise ValidationError("Evidence empty")

    if len(evidence) != len(set(evidence)):
        raise ValidationError("Duplicate evidence")

    for line in evidence:
        if line not in valid_line_ids:
            raise ValidationError(
                f"Unknown lineId {line}"
            )
