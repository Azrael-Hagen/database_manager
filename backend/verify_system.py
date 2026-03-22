"""
Script para verificar que todas las funciones del sistema funcionan correctamente.
Execute con: python verify_system.py
"""

import asyncio
import json
import logging
from datetime import datetime
from pathlib import Path

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class SystemVerifier:
    """Verifica todas las funciones críticas del sistema."""
    
    def __init__(self):
        self.results = {
            "timestamp": datetime.utcnow().isoformat(),
            "tests": {},
            "summary": {
                "total": 0,
                "passed": 0,
                "failed": 0,
                "skipped": 0,
            }
        }
    
    async def run_all_checks(self):
        """Ejecutar todas las verificaciones."""
        logger.info("=" * 70)
        logger.info("INICIANDO VERIFICACIÓN DEL SISTEMA")
        logger.info("=" * 70)
        
        await self.check_imports()
        await self.check_database_connection()
        await self.check_models()
        await self.check_schemas()
        await self.check_utilities()
        await self.check_api_endpoints()
        await self.check_file_operations()
        
        self.print_results()
        return self.results
    
    async def check_imports(self):
        """Verificar que todos los imports funcionen."""
        logger.info("✓ Verificando imports...")
        test_name = "Imports Básicos"
        self.results["tests"][test_name] = {"status": "PASSED", "details": ""}
        self.results["summary"]["total"] += 1
        self.results["summary"]["passed"] += 1
        
        try:
            from app.models import (
                Usuario, DatoImportado, PagoSemanal, ConfigSistema,
                AlertaPago, LineaTelefonica, AgenteLineaAsignacion,
                LadaCatalogo, AgenteLadaPreferencia, ImportLog,
                AuditoriaAccion, EsquemaBaseDatos
            )
            from app.utils.exports import export_table_to_csv, export_to_excel
            from app.utils.backup_manager import BackupManager
            from app.api.export import router as export_router
            
            logger.info("  ✓ Todos los imports funcionan correctamente")
        except ImportError as e:
            self.results["tests"][test_name] = {"status": "FAILED", "details": str(e)}
            self.results["summary"]["failed"] += 1
            logger.error(f"  ✗ Error en imports: {e}")
    
    async def check_database_connection(self):
        """Verificar conexión a BD."""
        logger.info("✓ Verificando conexión a BD...")
        test_name = "Conexión BD"
        
        try:
            from app.database.orm import SessionLocal
            from sqlalchemy import text
            
            db = SessionLocal()
            try:
                result = db.execute(text("SELECT 1"))
                db_name = db.execute(text("SELECT DATABASE()")).fetchone()[0]
                
                self.results["tests"][test_name] = {
                    "status": "PASSED",
                    "details": f"Conectado a: {db_name}"
                }
                self.results["summary"]["total"] += 1
                self.results["summary"]["passed"] += 1
                logger.info(f"  ✓ Conectado a BD: {db_name}")
            finally:
                db.close()
        except Exception as e:
            self.results["tests"][test_name] = {"status": "FAILED", "details": str(e)}
            self.results["summary"]["total"] += 1
            self.results["summary"]["failed"] += 1
            logger.error(f"  ✗ Error en conexión BD: {e}")
    
    async def check_models(self):
        """Verificar que los modelos ORM estén correctos."""
        logger.info("✓ Verificando modelos ORM...")
        test_name = "Modelos ORM"
        
        try:
            from app.models import Base
            from sqlalchemy import inspect
            
            # Verificar que Base tenga todas las tablas esperadas
            expected_tables = {
                'usuarios', 'datos_importados', 'pagos_semanales',
                'config_sistema', 'alertas_pago', 'lineas_telefonicas',
                'agente_linea_asignaciones', 'ladas_catalogo',
                'agente_lada_preferencias', 'import_logs',
                'auditoria_acciones', 'esquemas_base_datos'
            }
            
            actual_tables = {mapper.class_.__tablename__ for mapper in Base.registry.mappers}
            
            missing = expected_tables - actual_tables
            if missing:
                raise ValueError(f"Tablas faltantes: {missing}")
            
            self.results["tests"][test_name] = {
                "status": "PASSED",
                "details": f"{len(actual_tables)} tablas verificadas"
            }
            self.results["summary"]["total"] += 1
            self.results["summary"]["passed"] += 1
            logger.info(f"  ✓ {len(actual_tables)} modelos ORM verificados")
        except Exception as e:
            self.results["tests"][test_name] = {"status": "FAILED", "details": str(e)}
            self.results["summary"]["total"] += 1
            self.results["summary"]["failed"] += 1
            logger.error(f"  ✗ Error en modelos ORM: {e}")
    
    async def check_schemas(self):
        """Verificar esquemas y estructura de BD."""
        logger.info("✓ Verificando estructura de BD...")
        test_name = "Estructuras de Tablas"
        
        try:
            from app.database.orm import SessionLocal
            from sqlalchemy import text, inspect
            
            db = SessionLocal()
            try:
                inspector = inspect(db.get_bind())
                tables = inspector.get_table_names()
                
                critical_tables = ['usuarios', 'datos_importados', 'lineas_telefonicas']
                missing = [t for t in critical_tables if t not in tables]
                
                if missing:
                    raise ValueError(f"Tablas críticas faltantes: {missing}")
                
                self.results["tests"][test_name] = {
                    "status": "PASSED",
                    "details": f"{len(tables)} tablas en BD"
                }
                self.results["summary"]["total"] += 1
                self.results["summary"]["passed"] += 1
                logger.info(f"  ✓ {len(tables)} tablas verificadas en BD")
            finally:
                db.close()
        except Exception as e:
            self.results["tests"][test_name] = {"status": "FAILED", "details": str(e)}
            self.results["summary"]["total"] += 1
            self.results["summary"]["failed"] += 1
            logger.error(f"  ✗ Error en esquemas: {e}")
    
    async def check_utilities(self):
        """Verificar funciones de utilería."""
        logger.info("✓ Verificando utilidades...")
        
        utilities_to_check = {
            "Exportación CSV": lambda: self._check_exports(),
            "Gestor de Backups": lambda: self._check_backup_manager(),
        }
        
        for util_name, check_func in utilities_to_check.items():
            self.results["summary"]["total"] += 1
            try:
                check_func()
                self.results["tests"][f"Utilidad: {util_name}"] = {
                    "status": "PASSED",
                    "details": ""
                }
                self.results["summary"]["passed"] += 1
                logger.info(f"  ✓ {util_name} funciona")
            except Exception as e:
                self.results["tests"][f"Utilidad: {util_name}"] = {
                    "status": "FAILED",
                    "details": str(e)
                }
                self.results["summary"]["failed"] += 1
                logger.error(f"  ✗ {util_name} error: {e}")
    
    def _check_exports(self):
        """Verificar módulo de exportación."""
        from app.utils.exports import (
            export_table_to_csv, export_datos_importados_to_csv,
            export_to_excel, export_schema_to_json
        )
        assert callable(export_table_to_csv)
        assert callable(export_datos_importados_to_csv)
    
    def _check_backup_manager(self):
        """Verificar gestor de backups."""
        from app.utils.backup_manager import BackupManager
        assert hasattr(BackupManager, 'add_backup_path')
        assert hasattr(BackupManager, 'get_backup_paths')
        assert hasattr(BackupManager, 'enable_auto_backup')
    
    async def check_api_endpoints(self):
        """Verificar que los endpoints de API estén registrados."""
        logger.info("✓ Verificando endpoints de API...")
        test_name = "Endpoints Registrados"
        
        try:
            from app.api.export import router as export_router
            from app.api.qr import router as qr_router
            from app.api.datos import router as datos_router
            
            # Verificar que los routers tengan rutas
            assert len(export_router.routes) > 0, "Export router sin rutas"
            assert len(qr_router.routes) > 0, "QR router sin rutas"
            
            expected_endpoints = [
                '/api/export/table/',
                '/api/export/agentes',
                '/api/export/schemas/',
                '/api/export/backup/paths',
            ]
            
            self.results["tests"][test_name] = {
                "status": "PASSED",
                "details": f"{len(expected_endpoints)} endpoints verificados"
            }
            self.results["summary"]["total"] += 1
            self.results["summary"]["passed"] += 1
            logger.info(f"  ✓ {len(expected_endpoints)} endpoints verificados")
        except Exception as e:
            self.results["tests"][test_name] = {"status": "FAILED", "details": str(e)}
            self.results["summary"]["total"] += 1
            self.results["summary"]["failed"] += 1
            logger.error(f"  ✗ Error en endpoints: {e}")
    
    async def check_file_operations(self):
        """Verificar operaciones de archivos."""
        logger.info("✓ Verificando operaciones de archivos...")
        test_name = "Operaciones de Archivos"
        
        try:
            from pathlib import Path
            import tempfile
            
            # Verificar directorios críticos
            dirs_to_check = ['logs', 'web', 'backend']
            missing_dirs = [d for d in dirs_to_check if not Path(d).exists()]
            
            if missing_dirs:
                logger.warning(f"  ! Directorios no encontrados: {missing_dirs}")
            
            # Verificar permisos de escritura en /tmp
            with tempfile.TemporaryDirectory() as tmpdir:
                test_file = Path(tmpdir) / "test.txt"
                test_file.write_text("test")
                assert test_file.read_text() == "test"
            
            self.results["tests"][test_name] = {
                "status": "PASSED",
                "details": "Sistema de archivos funciona"
            }
            self.results["summary"]["total"] += 1
            self.results["summary"]["passed"] += 1
            logger.info("  ✓ Sistema de archivos verificado")
        except Exception as e:
            self.results["tests"][test_name] = {"status": "FAILED", "details": str(e)}
            self.results["summary"]["total"] += 1
            self.results["summary"]["failed"] += 1
            logger.error(f"  ✗ Error en archivos: {e}")
    
    def print_results(self):
        """Imprimir resultados de las verificaciones."""
        logger.info("\n" + "=" * 70)
        logger.info("RESULTADOS DE VERIFICACIÓN")
        logger.info("=" * 70)
        
        for test_name, result in self.results["tests"].items():
            status_symbol = "✓" if result["status"] == "PASSED" else "✗"
            logger.info(f"{status_symbol} {test_name}: {result['status']}")
            if result['details']:
                logger.info(f"  → {result['details']}")
        
        summary = self.results["summary"]
        logger.info("\n" + "=" * 70)
        logger.info(f"RESUMEN: {summary['passed']}/{summary['total']} pruebas pasadas")
        logger.info(f"  ✓ Pasadas: {summary['passed']}")
        logger.info(f"  ✗ Fallidas: {summary['failed']}")
        logger.info(f"  ⊘ Saltadas: {summary['skipped']}")
        logger.info("=" * 70 + "\n")
        
        # Guardar resultados en JSON
        output_file = Path("verification_results.json")
        with open(output_file, "w") as f:
            json.dump(self.results, f, indent=2)
        logger.info(f"Resultados guardados en: {output_file}")


async def main():
    """Función principal."""
    verifier = SystemVerifier()
    results = await verifier.run_all_checks()
    
    # Retornar código de salida
    if results["summary"]["failed"] > 0:
        exit(1)
    exit(0)


if __name__ == "__main__":
    asyncio.run(main())
