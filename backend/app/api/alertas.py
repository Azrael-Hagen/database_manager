"""Endpoints para envío y consulta de alertas del sistema (super admin)."""

from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, status, Query, Request
from sqlalchemy.orm import Session
from app.database.orm import get_db
from app.models import AlertaSistema, Usuario
from app.security import (
    get_current_user,
    require_super_admin_role,
    require_server_machine_request,
    require_admin_role,
)
import json
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/alertas", tags=["Alertas Sistema"])

_NIVELES = {"info", "warning", "danger"}


def _parse_leida_por(leida_por_json: str | None) -> list[int]:
    if not leida_por_json:
        return []
    try:
        parsed = json.loads(leida_por_json)
        return [int(uid) for uid in parsed if isinstance(uid, (int, float, str)) and str(uid).isdigit()]
    except Exception:
        return []


def _alerta_to_dict(alerta: AlertaSistema, current_user_id: int) -> dict:
    leida_por = _parse_leida_por(alerta.leida_por_json)
    return {
        "id": alerta.id,
        "titulo": alerta.titulo,
        "mensaje": alerta.mensaje,
        "nivel": alerta.nivel,
        "enviado_por": alerta.enviado_por,
        "remitente_username": alerta.remitente.username if alerta.remitente else None,
        "fecha_envio": alerta.fecha_envio.isoformat() if alerta.fecha_envio else None,
        "es_activa": alerta.es_activa,
        "leida": current_user_id in leida_por,
        "leida_por_count": len(leida_por),
    }


@router.post("/enviar", status_code=status.HTTP_201_CREATED)
async def enviar_alerta(
    request: Request,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
    titulo: str = Query(..., min_length=3, max_length=255),
    mensaje: str = Query(..., min_length=1),
    nivel: str = Query("warning"),
):
    """Enviar alerta a todos los usuarios. Solo super_admin desde la máquina servidor."""
    require_super_admin_role(current_user, "Solo el super administrador puede enviar alertas")
    require_server_machine_request(request, "El envío de alertas solo se permite desde la máquina servidor")

    nivel_normalizado = nivel.lower() if nivel.lower() in _NIVELES else "warning"

    alerta = AlertaSistema(
        titulo=titulo.strip(),
        mensaje=mensaje.strip(),
        nivel=nivel_normalizado,
        enviado_por=current_user["id"],
        leida_por_json="[]",
    )
    db.add(alerta)
    db.commit()
    db.refresh(alerta)

    logger.info("Alerta sistema enviada por %s: [%s] %s", current_user["username"], nivel_normalizado, titulo)
    return _alerta_to_dict(alerta, current_user["id"])


@router.post("/enviar-json")
async def enviar_alerta_json(
    request: Request,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Enviar alerta con body JSON. Solo super_admin desde la máquina servidor."""
    require_super_admin_role(current_user, "Solo el super administrador puede enviar alertas")
    require_server_machine_request(request, "El envío de alertas solo se permite desde la máquina servidor")

    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="JSON inválido")

    titulo = str(body.get("titulo", "")).strip()
    mensaje = str(body.get("mensaje", "")).strip()
    nivel = str(body.get("nivel", "warning")).lower()

    if not titulo or len(titulo) < 3:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="El título debe tener al menos 3 caracteres")
    if not mensaje:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="El mensaje no puede estar vacío")

    nivel_normalizado = nivel if nivel in _NIVELES else "warning"

    alerta = AlertaSistema(
        titulo=titulo,
        mensaje=mensaje,
        nivel=nivel_normalizado,
        enviado_por=current_user["id"],
        leida_por_json="[]",
    )
    db.add(alerta)
    db.commit()
    db.refresh(alerta)

    logger.info("Alerta sistema enviada por %s: [%s] %s", current_user["username"], nivel_normalizado, titulo)
    return _alerta_to_dict(alerta, current_user["id"])


@router.get("/")
async def listar_alertas(
    solo_activas: bool = Query(True),
    limit: int = Query(50, ge=1, le=200),
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Listar alertas del sistema (admin y super_admin)."""
    require_admin_role(current_user, "Solo administradores pueden ver alertas del sistema")

    query = db.query(AlertaSistema)
    if solo_activas:
        query = query.filter(AlertaSistema.es_activa.is_(True))
    alertas = query.order_by(AlertaSistema.fecha_envio.desc()).limit(limit).all()

    uid = int(current_user.get("id") or 0)
    return {
        "status": "ok",
        "total": len(alertas),
        "items": [_alerta_to_dict(a, uid) for a in alertas],
    }


@router.post("/{alerta_id}/leer")
async def marcar_alerta_leida(
    alerta_id: int,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Marcar alerta como leída por el usuario actual."""
    require_admin_role(current_user, "Solo administradores pueden marcar alertas")

    alerta = db.query(AlertaSistema).filter(AlertaSistema.id == alerta_id).first()
    if not alerta:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Alerta no encontrada")

    uid = int(current_user.get("id") or 0)
    leida_por = _parse_leida_por(alerta.leida_por_json)
    if uid not in leida_por:
        leida_por.append(uid)
        alerta.leida_por_json = json.dumps(leida_por)
        db.commit()

    return {"status": "ok", "leida": True}


@router.delete("/{alerta_id}")
async def desactivar_alerta(
    request: Request,
    alerta_id: int,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Desactivar una alerta (solo super_admin desde el servidor)."""
    require_super_admin_role(current_user, "Solo el super administrador puede desactivar alertas")
    require_server_machine_request(request, "Acción permitida solo desde la máquina servidor")

    alerta = db.query(AlertaSistema).filter(AlertaSistema.id == alerta_id).first()
    if not alerta:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Alerta no encontrada")

    alerta.es_activa = False
    db.commit()
    return {"status": "ok", "mensaje": "Alerta desactivada"}
