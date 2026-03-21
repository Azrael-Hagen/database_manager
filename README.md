# Database Manager - Gestor de Base de Datos

Aplicación modular para gestionar bases de datos MariaDB/MySQL con importación de archivos (CSV, Excel, TXT, DAT), generación de códigos QR y acceso web.

## Características

✅ **Importación de Datos**
- Importar CSV, Excel, TXT y archivos DAT
- Selección de delimitadores personalizados
- Validación de datos antes de importar

✅ **Generación de QR**
- Generar códigos QR para cada registro
- Almacenar información codificada en QR
- Exportar QR como imagen

✅ **Interfaz Local**
- GUI de escritorio con PyQt5
- Visualización y edición de datos
- Gestor de base de datos integrado

✅ **Servidor Web**
- API REST con FastAPI
- Panel web para visualizar datos
- Acceso remoto para múltiples usuarios

## Requisitos

- Python 3.9+
- MariaDB/MySQL server
- pip (gestor de paquetes)

## Instalación

### 1. Backend
```bash
cd backend
pip install -r requirements.txt
python main.py
```

### 2. Frontend Desktop
```bash
cd frontend
pip install -r requirements.txt
python main.py
```

### 3. Servidor Web
Accede a `http://localhost:8000` cuando el backend esté corriendo

## Estructura del Proyecto

```
database_manager/
├── backend/          # Servidor API y lógica de negocio
├── frontend/         # Aplicación de escritorio
├── web/             # Frontend web
├── tests/           # Tests automatizados
└── docs/            # Documentación
```

## Documentación Adicional

- [Guía de Setup](docs/SETUP.md)
- [Documentación de API](docs/API.md)
- [Arquitectura del Proyecto](docs/ARCHITECTURE.md)

## Licencia

MIT
