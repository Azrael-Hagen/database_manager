"""System metadata endpoints restricted to the server machine."""

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.database.orm import get_db
from app.security import get_current_user, require_server_machine_request
from app.versioning import current_version_payload, load_version_info, read_server_changelog

router = APIRouter(prefix="/api/system", tags=["Sistema"])


@router.get("/version")
async def get_system_version(
    request: Request,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Return current version, revision and server changelog metadata only from the server machine."""
    require_server_machine_request(request, "El registro de version solo es visible desde la maquina servidor")
    _ = db  # Keep dependency explicit for consistent auth/db lifecycle.
    return {
        "status": "success",
        "current": current_version_payload(),
        "history": load_version_info().get("history", []),
        "changelog": read_server_changelog(),
        "viewer": current_user.get("username"),
    }
