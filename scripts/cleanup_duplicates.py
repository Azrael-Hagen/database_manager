#!/usr/bin/env python
"""
Script para desactivar agentes duplicados manteniendo el primero de cada grupo.
USO: python scripts/cleanup_duplicates.py --dry-run    (mostrar qué se haría)
     python scripts/cleanup_duplicates.py --apply      (ejecutar limpieza real)
"""

import sys
import argparse
from pathlib import Path

# Agregar backend a path
sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))

from sqlalchemy import text
from app.database.orm import SessionLocal
from app.models import DatoImportado

def cleanup_duplicates(apply=False):
    """Desactiva agentes duplicados, manteniendo el primero de cada grupo."""
    db = SessionLocal()
    try:
        # Obtener duplicados agrupados
        duplicates_query = """
        SELECT nombre, GROUP_CONCAT(id ORDER BY id) as ids
        FROM database_manager.datos_importados
        WHERE nombre IS NOT NULL AND nombre != ''
        GROUP BY nombre
        HAVING COUNT(*) > 1
        ORDER BY COUNT(*) DESC, nombre
        """
        
        rows = db.execute(text(duplicates_query)).fetchall()
        
        if not rows:
            print("✓ No hay agentes duplicados.")
            return {"status": "ok", "duplicates_found": 0, "deactivated": 0}
        
        total_deactivated = 0
        print(f"\n📊 Se encontraron {len(rows)} nombres duplicados:\n")
        
        for nombre, ids_str in rows:
            ids = [int(id_) for id_ in ids_str.split(',')]
            keep_id = ids[0]  # Mantener el primero
            deactivate_ids = ids[1:]  # Desactivar los demás
            
            print(f"  {nombre:30} | Mantener ID {keep_id:3} | Desactivar: {deactivate_ids}")
            
            if apply:
                for deactivate_id in deactivate_ids:
                    agent = db.query(DatoImportado).filter(DatoImportado.id == deactivate_id).first()
                    if agent and agent.es_activo:
                        agent.es_activo = False
                        total_deactivated += 1
        
        if apply:
            db.commit()
            print(f"\n✓ Se desactivaron {total_deactivated} agentes duplicados.")
        else:
            print(f"\n⚠️  DRY RUN: Se desactivarían {sum(len(ids.split(','))-1 for _, ids in rows)} agentes.")
            print("   Usa --apply para ejecutar la limpieza real.")
        
        return {
            "status": "ok",
            "duplicates_found": len(rows),
            "deactivated": total_deactivated if apply else 0,
            "applied": apply
        }
    
    except Exception as e:
        print(f"❌ Error: {e}")
        db.rollback()
        return {"status": "error", "message": str(e)}
    finally:
        db.close()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Desactiva agentes duplicados manteniendo el primero de cada grupo"
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Ejecutar la limpieza real (sin este flag solo muestra dry-run)"
    )
    args = parser.parse_args()
    
    result = cleanup_duplicates(apply=args.apply)
    sys.exit(0 if result["status"] == "ok" else 1)
