"""Endpoints de auditoría."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from app.database.orm import get_db
from app.models import AuditoriaAccion
from app.security import get_current_user

router = APIRouter(prefix="/api/auditoria", tags=["Auditoría"])


@router.get("/")
async def listar_auditoria(
    limit: int = Query(100, ge=1, le=500),
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Listar auditoría reciente (solo admin)."""
    if not current_user.get("es_admin", False):
        return []

    registros = (
        db.query(AuditoriaAccion)
        .order_by(AuditoriaAccion.fecha.desc())
        .limit(limit)
        .all()
    )

    return [
        {
            "id": r.id,
            "usuario_id": r.usuario_id,
            "tipo_accion": r.tipo_accion,
            "tabla": r.tabla,
            "descripcion": r.descripcion,
            "resultado": r.resultado,
            "ip_origen": r.ip_origen,
            "fecha": r.fecha,
        }
        for r in registros
    ]
