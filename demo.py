"""Script de demostración de funcionalidades."""

import sys
import time
import tempfile
import os

# Para demostración sin dependencias complejas
print("=" * 60)
print("DATABASE MANAGER - Demo de Funcionalidades")
print("=" * 60)


def demo_importers():
    """Demostración de importadores."""
    print("\n[1] IMPORTADORES DE ARCHIVOS")
    print("-" * 40)
    
    from app.importers import CSVImporter, TextImporter
    
    # Demo CSV
    with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
        f.write("nombre,email,telefono\n")
        f.write("Juan,juan@email.com,1234567890\n")
        f.write("María,maria@email.com,0987654321\n")
        f.write("Carlos,carlos@email.com,5555555555\n")
        temp_csv = f.name
    
    try:
        print("\n📄 Importando archivo CSV...")
        csv_importer = CSVImporter(temp_csv, "usuarios", delimiter=",")
        
        if csv_importer.read_file():
            print(f"  ✓ Archivo leído: {len(csv_importer.data)} registros")
            
            if csv_importer.validate_data():
                print(f"  ✓ Datos validados correctamente")
                print("\n  Primeros registros:")
                for i, row in enumerate(csv_importer.data[:2]):
                    print(f"    {i+1}. {row['nombre']} - {row['email']}")
            else:
                print(f"  ✗ Errores de validación: {csv_importer.errors}")
    finally:
        os.unlink(temp_csv)
    
    # Demo TXT
    with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
        f.write("producto\tprecio\tstock\n")
        f.write("Laptop\t1000\t5\n")
        f.write("Mouse\t25\t50\n")
        f.write("Teclado\t75\t30\n")
        temp_txt = f.name
    
    try:
        print("\n📄 Importando archivo TXT...")
        txt_importer = TextImporter(temp_txt, "productos", delimiter="\t")
        
        if txt_importer.read_file():
            print(f"  ✓ Archivo leído: {len(txt_importer.data)} registros")
            print("\n  Registros cargados:")
            for i, row in enumerate(txt_importer.data):
                print(f"    {i+1}. {row['producto']} - ${row['precio']}")
    finally:
        os.unlink(temp_txt)


def demo_qr_generator():
    """Demostración de generador de QR."""
    print("\n[2] GENERADOR DE CÓDIGOS QR")
    print("-" * 40)
    
    from app.qr import QRGenerator
    
    with tempfile.TemporaryDirectory() as temp_dir:
        qr_gen = QRGenerator(output_folder=temp_dir)
        
        # QR desde texto
        print("\n🔳 Generando QR desde texto...")
        filepath = qr_gen.generate_qr_from_text(
            "https://www.example.com/datos/001",
            "qr_ejemplo.png"
        )
        
        if filepath and os.path.exists(filepath):
            print(f"  ✓ QR generado: {os.path.basename(filepath)}")
        
        # QR desde datos
        print("\n🔳 Generando QR desde datos JSON...")
        data = {
            "id": 1,
            "nombre": "Juan Pérez",
            "email": "juan@example.com",
            "empresa": "TechCorp"
        }
        
        filepath = qr_gen.generate_qr_from_data(data, "qr_registro.png")
        
        if filepath and os.path.exists(filepath):
            print(f"  ✓ QR generado: {os.path.basename(filepath)}")
            print(f"  ✓ Contiene datos JSON en el código")
        
        # Batch de QR
        print("\n🔳 Generando múltiples QR (batch)...")
        datos_batch = [
            "Usuario_001",
            "Usuario_002",
            "Usuario_003"
        ]
        
        qr_files = qr_gen.generate_qr_batch(datos_batch, prefix="usuario")
        print(f"  ✓ {len(qr_files)} códigos QR generados")


def demo_api_endpoints():
    """Información sobre endpoints de API."""
    print("\n[3] ENDPOINTS DE API REST")
    print("-" * 40)
    
    endpoints = [
        ("GET", "/api/health", "Verificar estado del servidor"),
        ("POST", "/api/import/csv", "Importar archivo CSV"),
        ("POST", "/api/import/excel", "Importar archivo Excel"),
        ("POST", "/api/qr/generate", "Generar código QR"),
        ("GET", "/api/data/{table}", "Obtener datos de tabla"),
    ]
    
    for method, path, description in endpoints:
        print(f"\n  {method:6} {path:25} - {description}")


def demo_database_models():
    """Información sobre modelos de base de datos."""
    print("\n[4] MODELOS DE BASE DE DATOS")
    print("-" * 40)
    
    models = {
        "datos_importados": [
            ("id", "INT AUTO_INCREMENT PRIMARY KEY"),
            ("nombre", "VARCHAR(255)"),
            ("email", "VARCHAR(255)"),
            ("telefono", "VARCHAR(20)"),
            ("empresa", "VARCHAR(255)"),
            ("ciudad", "VARCHAR(100)"),
            ("pais", "VARCHAR(100)"),
            ("qr_code", "LONGBLOB"),
            ("fecha_creacion", "TIMESTAMP"),
        ],
        "import_logs": [
            ("id", "INT AUTO_INCREMENT PRIMARY KEY"),
            ("archivo", "VARCHAR(255)"),
            ("tabla_destino", "VARCHAR(255)"),
            ("registros_importados", "INT"),
            ("estado", "VARCHAR(20)"),
            ("fecha_importacion", "TIMESTAMP"),
        ]
    }
    
    for tabla, campos in models.items():
        print(f"\n  📊 Tabla: {tabla}")
        for campo, tipo in campos:
            print(f"      {campo:20} - {tipo}")


def demo_features():
    """Mostrar features implementados."""
    print("\n[5] FEATURES IMPLEMENTADOS")
    print("-" * 40)
    
    features = {
        "Importadores": [
            "✓ CSV con delimitadores personalizables",
            "✓ Excel (.xlsx) con selección de hoja",
            "✓ TXT y DAT con delimitadores personalizados",
            "✓ Validación de datos antes de importar",
        ],
        "Generador QR": [
            "✓ QR desde texto simple",
            "✓ QR desde datos JSON",
            "✓ Generación batch de múltiples QR",
            "✓ Guardado como imagen PNG",
        ],
        "Base de Datos": [
            "✓ Conexión a MariaDB/MySQL",
            "✓ Singleton pattern para conexión",
            "✓ Métodos CRUD básicos",
            "✓ Manejo de transacciones",
        ],
        "API REST": [
            "✓ Endpoints para importación",
            "✓ Endpoints para generación de QR",
            "✓ Endpoints para consultar datos",
            "✓ CORS habilitado para acceso remoto",
        ],
        "Frontend Desktop": [
            "✓ Interfaz gráfica con PyQt5",
            "✓ Gestor de importación interactivo",
            "✓ Visor de datos en tabla",
            "✓ Cliente HTTP para conectar al backend",
        ],
        "Frontend Web": [
            "✓ Panel HTML responsive",
            "✓ Visualización de datos",
            "✓ Generador de QR en web",
            "✓ Diseño moderno con CSS",
        ],
    }
    
    for categoria, items in features.items():
        print(f"\n  {categoria}:")
        for item in items:
            print(f"    {item}")


def main():
    """Función principal."""
    try:
        # Demo sin conexión a BD (no requiere mariadb)
        demo_importers()
        demo_qr_generator()
        demo_api_endpoints()
        demo_database_models()
        demo_features()
        
        print("\n" + "=" * 60)
        print("CONFIGURACIÓN COMPLETADA")
        print("=" * 60)
        print("\n📖 Documentación:")
        print("  • QUICKSTART.md - Guía rápida de inicio")
        print("  • docs/SETUP.md - Instalación detallada")
        print("  • docs/API.md - Documentación de API")
        print("  • docs/ARCHITECTURE.md - Arquitectura del proyecto")
        print("\n✨ Para iniciar:")
        print("  1. Configurar credentials en .env")
        print("  2. cd backend && pip install -r requirements.txt")
        print("  3. python init_db.py (crear tablas)")
        print("  4. python main.py (iniciar servidor)")
        print("  5. Acceder a http://localhost:8000")
        print("\n")
        
    except ImportError as e:
        print(f"\n⚠️  Error: {e}")
        print("\nNota: Ejecuta primero:")
        print("  pip install -r backend/requirements.txt")
        return 1
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
