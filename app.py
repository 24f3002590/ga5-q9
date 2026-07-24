import asyncio
import json

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from schemas import ProposeRequest, CommitRequest
from hashing import compute_input_digest, compute_proposal_digest
from proposal_engine import build_all_proposals
from verifier import verify_signature
import storage

# Grader gives 55s per request / 180s total. Leave headroom for our own
# response marshalling.
REQUEST_TIMEOUT_SECONDS = 48
MAX_BODY_BYTES = 4 * 1024 * 1024  # generous cap for a ~75k-token corpus

app = FastAPI(
    title="Mailroom Agent",
    version="1.0.0",
)


@app.on_event("startup")
async def on_startup():
    storage.init_db()


@app.get("/")
async def root():
    return {
        "status": "running",
        "service": "mailroom-agent",
        "version": "1.0.0",
    }


@app.get("/health")
async def health():
    return {"status": "ok"}


def json_response(payload: dict, status_code: int = 200) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content=payload,
        media_type="application/json",
    )


@app.post("/")
async def mailroom(raw_request: Request):

    content_length = raw_request.headers.get("content-length")
    if content_length is not None and int(content_length) > MAX_BODY_BYTES:
        return json_response({"error": "Request body too large"}, 413)

    try:
        body = await raw_request.json()
    except Exception:
        return json_response({"error": "Malformed JSON body"}, 400)

    if not isinstance(body, dict):
        return json_response({"error": "Request body must be a JSON object"}, 400)

    op = body.get("operation")

    if op == "propose":
        return await handle_propose(body)

    if op == "commit":
        return await handle_commit(body)

    return json_response({"error": "Invalid or missing operation"}, 400)


async def handle_propose(body: dict) -> JSONResponse:
    try:
        parsed = ProposeRequest.model_validate(body)
    except Exception as e:
        return json_response(
            {"error": "Schema validation failed", "detail": str(e)}, 422
        )

    dossier_dicts = [d.model_dump(mode="json") for d in parsed.dossiers]

    dossier_ids = [d["dossierId"] for d in dossier_dicts]
    if len(dossier_ids) != len(set(dossier_ids)):
        return json_response({"error": "Duplicate dossierId in request"}, 422)

    input_digest = compute_input_digest(dossier_dicts)

    existing = storage.get_evaluation(parsed.evaluationId)

    if existing is not None:
        if existing["input_digest"] == input_digest:
            # Exact replay: same evaluationId, same content -> same answer,
            # no repeated model work.
            return json_response(json.loads(existing["response_json"]), 200)
        else:
            # Same evaluationId, different content.
            return json_response(
                {"error": "evaluationId already used with different content"},
                409,
            )

    try:
        proposals = await asyncio.wait_for(
            build_all_proposals(dossier_dicts, parsed.allowedActions),
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
    except asyncio.TimeoutError:
        return json_response({"error": "Timed out generating proposals"}, 504)

    response = {
        "profile": parsed.profile,
        "evaluationId": parsed.evaluationId,
        "status": "awaiting_receipts",
        "inputDigest": input_digest,
        "proposals": proposals,
    }

    # Persist BEFORE replying, per the spec.
    storage.save_evaluation(
        evaluation_id=parsed.evaluationId,
        input_digest=input_digest,
        public_key=json.dumps(parsed.receiptVerifier.publicKeyJwk),
        response=response,
    )

    for proposal in proposals:
        storage.save_proposal_for_evaluation(parsed.evaluationId, proposal)

    return json_response(response, 200)


async def handle_commit(body: dict) -> JSONResponse:
    try:
        parsed = CommitRequest.model_validate(body)
    except Exception as e:
        return json_response(
            {"error": "Schema validation failed", "detail": str(e)}, 422
        )

    receipt_dossier_ids = [r.dossierId for r in parsed.receipts]
    if len(receipt_dossier_ids) != len(set(receipt_dossier_ids)):
        return json_response({"error": "Duplicate dossierId in receipts"}, 422)

    evaluation = storage.get_evaluation(parsed.evaluationId)

    if evaluation is None:
        return json_response({"error": "Unknown evaluationId"}, 404)

    if evaluation["input_digest"] != parsed.inputDigest:
        return json_response({"error": "inputDigest does not match evaluation"}, 409)

    receipts_dicts = [r.model_dump(mode="json") for r in parsed.receipts]
    receipts_fingerprint = compute_input_digest(receipts_dicts)

    cached_commit = storage.get_commit_response(parsed.evaluationId)

    if cached_commit is not None:
        if cached_commit["receipts_fingerprint"] == receipts_fingerprint:
            # Exact commit replay: no re-verification, no re-recording.
            return json_response(cached_commit["response"], 200)
        else:
            return json_response(
                {"error": "commit already recorded with different receipts"},
                409,
            )

    public_key_jwk = json.loads(evaluation["public_key"])

    stored_proposals = storage.get_proposals_for_evaluation(parsed.evaluationId)
    proposals_by_key = {
        (p["dossierId"], p["callId"]): p for p in stored_proposals
    }

    outcomes = []

    for receipt in receipts_dicts:
        key = (receipt["dossierId"], receipt["callId"])
        stored = proposals_by_key.get(key)

        status = "rejected"

        # A receipt is only ever honored if it matches the exact proposal
        # this agent made for this evaluation -- same dossier, same
        # callId, same action, same proposal digest -- AND carries a
        # valid signature AND accepted == true. Any mismatch => rejected,
        # never invented/transferred from another proposal.
        if stored is not None and stored["action"] == receipt["action"]:
            expected_digest = compute_proposal_digest(stored)

            if expected_digest == receipt["proposalDigest"]:
                sig_message = {
                    k: v for k, v in receipt.items() if k != "receiptSignature"
                }

                sig_ok = verify_signature(
                    public_key_jwk,
                    sig_message,
                    receipt["receiptSignature"],
                )

                if sig_ok and receipt["accepted"] is True:
                    status = "executed"

        storage.save_receipt(parsed.evaluationId, receipt)

        outcomes.append({
            "dossierId": receipt["dossierId"],
            "callId": receipt["callId"],
            "action": receipt["action"],
            "proposalDigest": receipt["proposalDigest"],
            "receiptId": receipt["receiptId"],
            "status": status,
        })

    response = {
        "profile": parsed.profile,
        "evaluationId": parsed.evaluationId,
        "status": "completed",
        "inputDigest": parsed.inputDigest,
        "outcomes": outcomes,
    }

    storage.save_commit_response(parsed.evaluationId, receipts_fingerprint, response)
    storage.mark_committed(parsed.evaluationId)

    return json_response(response, 200)
