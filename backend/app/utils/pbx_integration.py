"""Utility functions for integrating PBX extensions from external database."""

import logging
import json
from typing import List, Dict, Optional
from datetime import datetime

from sqlalchemy import text
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


async def get_pbx_extensions(
    db: Session,
    pbx_db_name: str = "asterisk",
    search: Optional[str] = None,
    limit: int = 100
) -> List[Dict]:
    """
    Fetch extension numbers from PBX extensions table.
    
    Args:
        db: Database session
        pbx_db_name: PBX database name (default: asterisk)
        search: Optional search term
        limit: Result limit
    
    Returns:
        List of extension objects
    """
    try:
        db.execute(text(f"USE `{pbx_db_name}`"))
        
        # Determine table name (common patterns: extensions, extensions_pbx, ps_aors)
        result = db.execute(text("SHOW TABLES LIKE '%extension%'"))
        tables = [row[0] for row in result.fetchall()]
        
        if not tables:
            logger.warning(f"No extension tables found in {pbx_db_name}")
            return []
        
        extension_table = tables[0]
        logger.info(f"Found extension table: {extension_table}")
        
        # Build query (handle different column names)
        column_query = f"SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_SCHEMA = '{pbx_db_name}' AND TABLE_NAME = '{extension_table}'"
        result = db.execute(text(column_query))
        columns = [row[0].lower() for row in result.fetchall()]
        
        logger.info(f"Available columns: {columns}")
        
        # Map common column names
        ext_col = "extension" if "extension" in columns else "exten" if "exten" in columns else "id"
        name_col = "name" if "name" in columns else "displayname" if "displayname" in columns else None
        context_col = "context" if "context" in columns else None
        
        select_cols = [f"`{ext_col}` as extension"]
        if name_col:
            select_cols.append(f"`{name_col}` as name")
        if context_col:
            select_cols.append(f"`{context_col}` as context")
        
        select_sql = ", ".join(select_cols)
        where_clause = f"WHERE `{ext_col}` LIKE '%{search}%'" if search else ""
        
        query = f"SELECT {select_sql} FROM `{extension_table}` {where_clause} LIMIT {limit}"
        
        result = db.execute(text(query))
        extensions = []
        
        for row in result.fetchall():
            ext_dict = dict(row._mapping) if hasattr(row, '_mapping') else dict(zip(
                [col.split(" as ")[-1] for col in select_cols],
                row
            ))
            if ext_dict.get('extension'):
                extensions.append(ext_dict)
        
        logger.info(f"Retrieved {len(extensions)} extensions from {extension_table}")
        return extensions
    
    except Exception as e:
        logger.error(f"Error fetching PBX extensions: {e}")
        return []


def get_available_ringing_extensions(
    db: Session,
    pbx_db_name: str = "asterisk"
) -> List[str]:
    """Get list of active/available extensions that could be assigned to agents."""
    try:
        extensions = get_pbx_extensions(db, pbx_db_name)
        return [ext.get('extension', '') for ext in extensions if ext.get('extension')]
    except Exception as e:
        logger.error(f"Error getting available extensions: {e}")
        return []


def sync_extensions_to_line_catalog(
    db: Session,
    pbx_db_name: str = "asterisk"
) -> Dict[str, int]:
    """
    Sync PBX extensions into the lineas_telefonicas table.
    
    Returns:
        Dict with counts: {created, updated, skipped, errors}
    """
    from app.models import LineaTelefonica
    
    try:
        extensions = get_pbx_extensions(db, pbx_db_name, limit=999)
        
        result = {"created": 0, "updated": 0, "skipped": 0, "errors": 0}
        
        for ext in extensions:
            try:
                number = str(ext.get('extension', ''))
                if not number or len(number) < 2:
                    result["skipped"] += 1
                    continue
                
                existing = db.query(LineaTelefonica).filter(
                    LineaTelefonica.numero == number
                ).first()
                
                if existing:
                    existing.es_activa = True
                    if ext.get('name'):
                        existing.descripcion = f"PBX Extension: {ext['name']}"
                    result["updated"] += 1
                else:
                    name_info = f" ({ext['name']})" if ext.get('name') else ""
                    nueva_linea = LineaTelefonica(
                        numero=number,
                        tipo="VOIP",
                        descripcion=f"Extension PBX{name_info}",
                        es_activa=True,
                    )
                    db.add(nueva_linea)
                    result["created"] += 1
            
            except Exception as e:
                logger.error(f"Error syncing extension {ext}: {e}")
                result["errors"] += 1
        
        db.commit()
        logger.info(f"Extensions sync result: {result}")
        return result
    
    except Exception as e:
        logger.error(f"Error syncing extensions: {e}")
        return {"created": 0, "updated": 0, "skipped": 0, "errors": 999}
