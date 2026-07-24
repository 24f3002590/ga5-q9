import base64
import json

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey


def b64url_decode(data: str) -> bytes:
    """
    Decode Base64URL string.
    """

    padding = "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(data + padding)


def load_public_key(jwk: dict) -> Ed25519PublicKey:
    """
    Convert OKP JWK into an Ed25519 public key.
    """

    if jwk.get("kty") != "OKP":
        raise ValueError("Unsupported key type")

    if jwk.get("crv") != "Ed25519":
        raise ValueError("Unsupported curve")

    raw = b64url_decode(jwk["x"])

    return Ed25519PublicKey.from_public_bytes(raw)


def canonical_json(obj) -> bytes:
    """
    Canonical JSON bytes.
    """

    return json.dumps(
        obj,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")


def verify_signature(
    jwk: dict,
    message: dict,
    signature_b64: str,
) -> bool:
    """
    Verify an Ed25519 signature.

    Returns True/False.
    """

    try:

        public_key = load_public_key(jwk)

        signature = base64.b64decode(signature_b64)

        public_key.verify(
            signature,
            canonical_json(message),
        )

        return True

    except Exception:
        return False
