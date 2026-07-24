import os
import sqlite3
import json
from typing import Optional

DB = os.getenv("DB_PATH", "database.db")


def get_db():
    conn = sqlite3.connect(DB, timeout=30)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()
    cur = conn.cursor()

    # WAL mode is friendlier to concurrent reads/writes on a single file.
    cur.execute("PRAGMA journal_mode=WAL")
    cur.execute("PRAGMA busy_timeout=30000")

    cur.execute("""
    CREATE TABLE IF NOT EXISTS evaluations(
        evaluation_id TEXT PRIMARY KEY,
        input_digest TEXT NOT NULL,
        public_key TEXT NOT NULL,
        response_json TEXT NOT NULL,
        committed INTEGER DEFAULT 0
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS proposal_cache(
        dossier_hash TEXT PRIMARY KEY,
        proposal_json TEXT NOT NULL
    )
    """)

    # Per-evaluation copy of each proposal, keyed by (evaluation, dossier,
    # callId). This is what commit uses to check that a receipt really
    # matches the proposal that was actually offered in THIS evaluation.
    cur.execute("""
    CREATE TABLE IF NOT EXISTS evaluation_proposals(
        evaluation_id TEXT NOT NULL,
        dossier_id TEXT NOT NULL,
        call_id TEXT NOT NULL,
        proposal_json TEXT NOT NULL,
        PRIMARY KEY (evaluation_id, dossier_id)
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS receipts(
        receipt_id TEXT PRIMARY KEY,
        evaluation_id TEXT NOT NULL,
        receipt_json TEXT NOT NULL
    )
    """)

    # Stores the final commit response per evaluation, so an exact commit
    # replay returns the same result without re-verifying/re-recording.
    cur.execute("""
    CREATE TABLE IF NOT EXISTS commit_responses(
        evaluation_id TEXT PRIMARY KEY,
        receipts_fingerprint TEXT NOT NULL,
        response_json TEXT NOT NULL
    )
    """)

    conn.commit()
    conn.close()


# ---------------------------------------------------
# Evaluation
# ---------------------------------------------------

def save_evaluation(
    evaluation_id: str,
    input_digest: str,
    public_key: str,
    response: dict,
):
    conn = get_db()

    conn.execute(
        """
        INSERT INTO evaluations
        VALUES(?,?,?,?,0)
        """,
        (
            evaluation_id,
            input_digest,
            public_key,
            json.dumps(response),
        ),
    )

    conn.commit()
    conn.close()


def get_evaluation(evaluation_id: str):

    conn = get_db()

    row = conn.execute(
        """
        SELECT *
        FROM evaluations
        WHERE evaluation_id=?
        """,
        (evaluation_id,),
    ).fetchone()

    conn.close()

    return row


def mark_committed(evaluation_id: str):

    conn = get_db()

    conn.execute(
        """
        UPDATE evaluations
        SET committed=1
        WHERE evaluation_id=?
        """,
        (evaluation_id,),
    )

    conn.commit()
    conn.close()


# ---------------------------------------------------
# Proposal cache (by canonical dossier content -- cross-evaluation)
# ---------------------------------------------------

def cache_proposal(dossier_hash: str, proposal: dict):

    conn = get_db()

    conn.execute(
        """
        INSERT OR REPLACE INTO proposal_cache
        VALUES (?,?)
        """,
        (
            dossier_hash,
            json.dumps(proposal),
        ),
    )

    conn.commit()
    conn.close()


def get_cached_proposal(dossier_hash: str):

    conn = get_db()

    row = conn.execute(
        """
        SELECT proposal_json
        FROM proposal_cache
        WHERE dossier_hash=?
        """,
        (dossier_hash,),
    ).fetchone()

    conn.close()

    if row is None:
        return None

    return json.loads(row["proposal_json"])


# ---------------------------------------------------
# Per-evaluation proposals (for commit-time receipt scoping)
# ---------------------------------------------------

def save_proposal_for_evaluation(evaluation_id: str, proposal: dict):

    conn = get_db()

    conn.execute(
        """
        INSERT OR REPLACE INTO evaluation_proposals
        VALUES (?,?,?,?)
        """,
        (
            evaluation_id,
            proposal["dossierId"],
            proposal["callId"],
            json.dumps(proposal),
        ),
    )

    conn.commit()
    conn.close()


def get_proposals_for_evaluation(evaluation_id: str):

    conn = get_db()

    rows = conn.execute(
        """
        SELECT proposal_json
        FROM evaluation_proposals
        WHERE evaluation_id=?
        """,
        (evaluation_id,),
    ).fetchall()

    conn.close()

    return [json.loads(r["proposal_json"]) for r in rows]


# ---------------------------------------------------
# Receipts
# ---------------------------------------------------

def save_receipt(evaluation_id: str, receipt: dict):

    conn = get_db()

    conn.execute(
        """
        INSERT OR REPLACE INTO receipts
        VALUES (?,?,?)
        """,
        (
            receipt["receiptId"],
            evaluation_id,
            json.dumps(receipt),
        ),
    )

    conn.commit()
    conn.close()


def get_receipt(receipt_id: str):

    conn = get_db()

    row = conn.execute(
        """
        SELECT receipt_json
        FROM receipts
        WHERE receipt_id=?
        """,
        (receipt_id,),
    ).fetchone()

    conn.close()

    if row is None:
        return None

    return json.loads(row["receipt_json"])


# ---------------------------------------------------
# Commit responses (idempotent commit replay)
# ---------------------------------------------------

def save_commit_response(
    evaluation_id: str,
    receipts_fingerprint: str,
    response: dict,
):
    conn = get_db()

    conn.execute(
        """
        INSERT OR REPLACE INTO commit_responses
        VALUES (?,?,?)
        """,
        (
            evaluation_id,
            receipts_fingerprint,
            json.dumps(response),
        ),
    )

    conn.commit()
    conn.close()


def get_commit_response(evaluation_id: str) -> Optional[dict]:

    conn = get_db()

    row = conn.execute(
        """
        SELECT receipts_fingerprint, response_json
        FROM commit_responses
        WHERE evaluation_id=?
        """,
        (evaluation_id,),
    ).fetchone()

    conn.close()

    if row is None:
        return None

    return {
        "receipts_fingerprint": row["receipts_fingerprint"],
        "response": json.loads(row["response_json"]),
    }
