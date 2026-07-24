import sqlite3
import json
from typing import Optional

DB = "database.db"


def get_db():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()
    cur = conn.cursor()

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

    cur.execute("""
    CREATE TABLE IF NOT EXISTS receipts(
        receipt_id TEXT PRIMARY KEY,
        evaluation_id TEXT NOT NULL,
        receipt_json TEXT NOT NULL
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
# Proposal cache
# ---------------------------------------------------

def cache_proposal(
    dossier_hash: str,
    proposal: dict,
):

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


def get_cached_proposal(
    dossier_hash: str,
):

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
# Receipts
# ---------------------------------------------------

def save_receipt(
    evaluation_id: str,
    receipt: dict,
):

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
