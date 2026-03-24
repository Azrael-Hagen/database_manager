"""Utilidades reutilizables para tokens QR firmados."""

from datetime import UTC, datetime, timedelta
import base64
import hashlib
import hmac
import json
import secrets

from fastapi import HTTPException, status

from app.config import config


def _utcnow() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def _base64url_encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("utf-8").rstrip("=")


def _base64url_decode(raw: str) -> bytes:
    padded = raw + "=" * (-len(raw) % 4)
    return base64.urlsafe_b64decode(padded.encode("utf-8"))


def sign_secure_payload(payload_b64: str) -> str:
    secret = str(config.SECRET_KEY or "change-me-in-production").encode("utf-8")
    digest = hmac.new(secret, payload_b64.encode("utf-8"), hashlib.sha256).digest()
    return _base64url_encode(digest)


def build_secure_qr_token(*, agente_id: int, linea_id: int, linea_numero: str | None) -> str:
    issued_at = _utcnow()
    expires_at = issued_at + timedelta(hours=max(1, int(config.QR_TOKEN_TTL_HOURS or 1)))
    payload = {
        "agente_id": int(agente_id),
        "linea_id": int(linea_id),
        "linea_numero": str(linea_numero or ""),
        "nonce": secrets.token_hex(8),
        "iat": issued_at.isoformat(),
        "exp": expires_at.isoformat(),
    }
    payload_b64 = _base64url_encode(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    signature = sign_secure_payload(payload_b64)
    return f"{payload_b64}.{signature}"


def decode_secure_qr_token(token: str) -> dict:
    raw_token = str(token or "").strip()
    if "." not in raw_token:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Token QR invalido")

    payload_b64, provided_signature = raw_token.split(".", 1)
    expected_signature = sign_secure_payload(payload_b64)
    if not hmac.compare_digest(provided_signature, expected_signature):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Firma QR invalida")

    try:
        payload = json.loads(_base64url_decode(payload_b64).decode("utf-8"))
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Token QR malformado") from exc

    if not isinstance(payload, dict):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Token QR malformado")

    for required in ("agente_id", "linea_id", "exp"):
        if required not in payload:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Token QR incompleto")

    try:
        expires_at = datetime.fromisoformat(str(payload["exp"]))
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Fecha de expiracion invalida") from exc

    if _utcnow() > expires_at:
        raise HTTPException(status_code=status.HTTP_410_GONE, detail="QR expirado")

    return payload
