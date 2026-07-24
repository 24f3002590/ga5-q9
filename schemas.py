from typing import List, Optional, Literal, Dict, Any
from pydantic import BaseModel


# ---------- Common ----------

class Line(BaseModel):
    lineId: str
    text: str


class Source(BaseModel):
    sourceId: str
    kind: str
    provenance: str
    title: str
    lines: List[Line]


class Dossier(BaseModel):
    dossierId: str
    partition: Literal["stable_core", "fresh_audit"]
    receivedAt: str
    mailbox: str
    objective: str
    sources: List[Source]


class ReceiptVerifier(BaseModel):
    algorithm: str
    publicKeyJwk: Dict[str, Any]


class Corpus(BaseModel):
    coreId: str
    auditId: str
    stableCount: int
    freshCount: int


# ---------- Propose ----------

class ProposeRequest(BaseModel):
    profile: str
    operation: Literal["propose"]
    evaluationId: str
    receiptVerifier: ReceiptVerifier
    corpus: Corpus
    allowedActions: List[str]
    dossiers: List[Dossier]


class Target(BaseModel):
    kind: str
    id: str


class Proposal(BaseModel):
    dossierId: str
    callId: str
    action: str
    target: Optional[Target] = None
    payload: Dict[str, Any]
    evidence: List[str]


class ProposeResponse(BaseModel):
    profile: str
    evaluationId: str
    status: str
    inputDigest: str
    proposals: List[Proposal]


# ---------- Commit ----------

class Receipt(BaseModel):
    dossierId: str
    callId: str
    action: str
    accepted: bool
    proposalDigest: str
    receiptId: str
    receiptSignature: str


class CommitRequest(BaseModel):
    profile: str
    operation: Literal["commit"]
    evaluationId: str
    inputDigest: str
    receipts: List[Receipt]


class Outcome(BaseModel):
    dossierId: str
    callId: str
    action: str
    proposalDigest: str
    receiptId: str
    status: Literal["executed", "rejected"]


class CommitResponse(BaseModel):
    profile: str
    evaluationId: str
    status: str
    inputDigest: str
    outcomes: List[Outcome]
