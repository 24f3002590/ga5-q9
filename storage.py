import sqlite3
import json
from typing import Optional


DB_NAME = "database.db"


def get_conn():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_conn()
    cur = conn.cursor()

    # Stores every evaluation request
    cur.execute("""
    CREATE TABLE IF NOT EXISTS evaluations (
        evaluation_id TEXT PRIMARY KEY,
        input_digest TEXT NOT NULL,
        public_key TEXT NOT NULL,
        propose_response TEXT NOT NULL
    )
    """)

    # Cache proposals by dossier fingerprint
    cur.execute("""
    CREATE TABLE IF NOT EXISTS proposal_cache (
        dossier_hash TEXT PRIMARY KEY,
        proposal TEXT NOT NULL
    )
    """)

    # Receipts
    cur.execute("""
    CREATE TABLE IF NOT EXISTS receipts (
        receipt_id TEXT PRIMARY KEY,
        evaluation_id TEXT NOT NULL,
        dossier_id TEXT NOT NULL,
        call_id TEXT NOT NULL,
        proposal_digest TEXT NOT NULL,
        accepted INTEGER NOT NULL,
        receipt_json TEXT NOT NULL
    )
    """)

    conn.commit()
    conn.close()


# --------------------------
# Evaluation Storage
# --------------------------

def save_evaluation(
    evaluation_id: str,
    input_digest: str,
    public_key: str,
    propose_response: dict
):
    conn = get_conn()

    conn.execute(
        """
        INSERT INTO evaluations
        VALUES (?, ?, ?, ?)
        """,
        (
            evaluation_id,
            input_digest,
            public_key,
            json.dumps(propose_response),
        ),
    )

    conn.commit()
    conn.close()


def get_evaluation(evaluation_id: str):

    conn = get_conn()

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


# --------------------------
# Proposal Cache
# --------------------------

def cache_proposal(
    dossier_hash: str,
    proposal: dict,
):

    conn = get_conn()

    conn.execute(
        """
        INSERT OR REPLACE INTO proposal_cache
        VALUES (?, ?)
        """,
        (
            dossier_hash,
            json.dumps(proposal),
        ),
    )

    conn.commit()
    conn.close()


def get_cached_proposal(
    dossier_hash: str,
) -> Optional[dict]:

    conn = get_conn()

    row = conn.execute(
        """
        SELECT proposal
        FROM proposal_cache
        WHERE dossier_hash=?
        """,
        (dossier_hash,),
    ).fetchone()

    conn.close()

    if row is None:
        return None

    return json.loads(row["proposal"])


# --------------------------
# Receipts
# --------------------------

def save_receipt(
    receipt: dict,
):

    conn = get_conn()

    conn.execute(
        """
        INSERT OR REPLACE INTO receipts
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            receipt["receiptId"],
            receipt["evaluationId"],
            receipt["dossierId"],
            receipt["callId"],
            receipt["proposalDigest"],
            int(receipt["accepted"]),
            json.dumps(receipt),
        ),
    )

    conn.commit()
    conn.close()


def receipt_exists(receipt_id: str):

    conn = get_conn()

    row = conn.execute(
        """
        SELECT 1
        FROM receipts
        WHERE receipt_id=?
        """,
        (receipt_id,),
    ).fetchone()

    conn.close()

    return row is not None
