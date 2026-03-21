"""Script de verificación de la estructura del proyecto."""

import os
import sys


def check_project_structure():
    """Verificar que todos los archivos están en su lugar."""
    
    print("=" * 70)
    print("VERIFICANDO ESTRUCTURA DEL PROYECTO")
    print("=" * 70)
    
    base_path = os.path.dirname(os.path.abspath(__file__))
    
    required_files = {
        "Backend": [
            "backend/main.py",
            "backend/init_db.py",
            "backend/requirements.txt",
            "backend/app/config.py",
            "backend/app/__init__.py",
            "backend/app/database/connection.py",
            "backend/app/importers/base_importer.py",
            "backend/app/importers/csv_importer.py",
            "backend/app/importers/excel_importer.py",
            "backend/app/importers/text_importer.py",
            "backend/app/qr/qr_generator.py",
            "backend/app/utils/validators.py",
            "backend/app/api/routes.py",
        ],
        "Frontend Desktop": [
            "frontend/main.py",
            "frontend/requirements.txt",
            "frontend/ui/main_window.py",
            "frontend/ui/import_dialog.py",
            "frontend/ui/data_viewer.py",
            "frontend/services/api_client.py",
        ],
        "Frontend Web": [
            "web/index.html",
            "web/css/style.css",
            "web/js/main.js",
        ],
        "Tests": [
            "tests/test_importers.py",
            "tests/test_qr_generator.py",
            "tests/test_database.py",
        ],
        "Documentación": [
            "README.md",
            "QUICKSTART.md",
            "docs/SETUP.md",
            "docs/ARCHITECTURE.md",
            "docs/API.md",
            ".env.example",
            ".gitignore",
            "pytest.ini",
            "demo.py",
        ]
    }
    
    all_ok = True
    total_files = 0
    found_files = 0
    
    for category, files in required_files.items():
        print(f"\n✓ {category}")
        for file in files:
            filepath = os.path.join(base_path, file)
            total_files += 1
            
            if os.path.exists(filepath):
                found_files += 1
                print(f"  ✓ {file}")
            else:
                print(f"  ✗ {file} - FALTA")
                all_ok = False
    
    print("\n" + "=" * 70)
    print(f"RESULTADO: {found_files}/{total_files} archivos encontrados")
    print("=" * 70)
    
    if all_ok:
        print("\n✓ ¡Estructura completa! El proyecto está listo para usar.\n")
        return 0
    else:
        print("\n✗ Faltan algunos archivos. Revisa la estructura.\n")
        return 1


def check_directories():
    """Verificar que todos los directorios existen."""
    
    print("\nVERIFICANDO DIRECTORIOS")
    print("-" * 70)
    
    base_path = os.path.dirname(os.path.abspath(__file__))
    
    directories = [
        "backend/app",
        "backend/app/api",
        "backend/app/database",
        "backend/app/importers",
        "backend/app/qr",
        "backend/app/utils",
        "frontend/ui",
        "frontend/services",
        "web/css",
        "web/js",
        "tests",
        "docs",
    ]
    
    all_ok = True
    
    for directory in directories:
        dirpath = os.path.join(base_path, directory)
        if os.path.isdir(dirpath):
            print(f"✓ {directory}")
        else:
            print(f"✗ {directory} - NO EXISTE")
            all_ok = False
    
    return 0 if all_ok else 1


def main():
    """Función principal."""
    result1 = check_directories()
    result2 = check_project_structure()
    
    print("\nPRÓXIMOS PASOS:")
    print("-" * 70)
    print("1. Editar .env con tus credenciales de MariaDB")
    print("2. cd backend && pip install -r requirements.txt")
    print("3. python init_db.py")
    print("4. python main.py")
    print("5. Acceder a http://localhost:8000")
    print("\nDocumentación:")
    print("  • Lee QUICKSTART.md para instrucciones rápidas")
    print("  • Lee docs/SETUP.md para instalación detallada")
    print("  • Lee docs/API.md para documentación de endpoints")
    print("=" * 70 + "\n")
    
    return result1 or result2


if __name__ == "__main__":
    sys.exit(main())
