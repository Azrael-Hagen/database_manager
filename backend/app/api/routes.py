"""API routes."""

from fastapi import APIRouter, UploadFile, File, Form
from typing import Optional
import logging
from app.database import get_connection
from app.qr import QRGenerator
from app.importers import CSVImporter, ExcelImporter, TextImporter

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["api"])


@router.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "ok"}


@router.post("/import/csv")
async def import_csv(
    file: UploadFile = File(...),
    table_name: str = Form(...),
    delimiter: str = Form(default=",")
):
    """Importar archivo CSV."""
    try:
        # Guardar archivo temporalmente
        temp_path = f"temp_{file.filename}"
        with open(temp_path, "wb") as f:
            content = await file.read()
            f.write(content)
        
        # Importar
        importer = CSVImporter(temp_path, table_name, delimiter=delimiter)
        if importer.read_file() and importer.validate_data():
            return {
                "status": "success",
                "message": f"Importados {len(importer.data)} registros",
                "data": importer.data[:10]  # Primeros 10 para preview
            }
        else:
            return {
                "status": "error",
                "message": "Error validando datos",
                "errors": importer.errors
            }
    except Exception as e:
        logger.error(f"Error importando CSV: {e}")
        return {"status": "error", "message": str(e)}


@router.post("/import/excel")
async def import_excel(
    file: UploadFile = File(...),
    table_name: str = Form(...),
    sheet_name: str = Form(default="0")
):
    """Importar archivo Excel."""
    try:
        temp_path = f"temp_{file.filename}"
        with open(temp_path, "wb") as f:
            content = await file.read()
            f.write(content)
        
        importer = ExcelImporter(temp_path, table_name, sheet_name=sheet_name)
        if importer.read_file() and importer.validate_data():
            return {
                "status": "success",
                "message": f"Importados {len(importer.data)} registros",
                "data": importer.data[:10]
            }
        else:
            return {
                "status": "error",
                "message": "Error validando datos",
                "errors": importer.errors
            }
    except Exception as e:
        logger.error(f"Error importando Excel: {e}")
        return {"status": "error", "message": str(e)}


@router.post("/qr/generate")
async def generate_qr(text: str):
    """Generar QR desde texto."""
    try:
        qr_gen = QRGenerator()
        filepath = qr_gen.generate_qr_from_text(text)
        return {
            "status": "success",
            "filepath": filepath
        }
    except Exception as e:
        logger.error(f"Error generando QR: {e}")
        return {"status": "error", "message": str(e)}


@router.get("/data/{table_name}")
async def get_data(table_name: str):
    """Obtener datos de una tabla."""
    try:
        db = get_connection()
        query = f"SELECT * FROM {table_name}"
        data = db.fetch_all(query)
        return {"status": "success", "data": data}
    except Exception as e:
        logger.error(f"Error obteniendo datos: {e}")
        return {"status": "error", "message": str(e)}
