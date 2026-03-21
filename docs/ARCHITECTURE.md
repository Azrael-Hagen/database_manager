# Arquitectura del Proyecto

## Visión General

Database Manager es una aplicación modular en tres capas:

```
┌─────────────────────────────────────────────────────────────┐
│                   Frontend Web (HTML/JS)                     │
│                   Frontend Desktop (PyQt5)                   │
└─────────────────────────────────────────────────────────────┘
                            ↓ HTTP/REST
┌─────────────────────────────────────────────────────────────┐
│                                                               │
│                     Backend (FastAPI)                        │
│  ┌──────────┬──────────────┬──────────┬──────────────┐      │
│  │   API    │  Importers   │    QR    │  Database    │      │
│  │ Routes   │  (CSV/Excel) │ Generator│  Connection  │      │
│  └──────────┴──────────────┴──────────┴──────────────┘      │
│                                                               │
└─────────────────────────────────────────────────────────────┘
                            ↓ MySQL Protocol
┌─────────────────────────────────────────────────────────────┐
│                   MariaDB/MySQL Server                       │
└─────────────────────────────────────────────────────────────┘
```

## Componentes

### Backend (Python + FastAPI)

#### `app/config.py`
- Gestión centralizada de configuración
- Carga variables de entorno
- Configuración de base de datos, servidor, logging

#### `app/database/`
- **connection.py**: Singleton pattern para conexión a BD
- Métodos CRUD: `execute_query()`, `fetch_all()`, `fetch_one()`
- Manejo de errores y logging

#### `app/importers/`
- **base_importer.py**: Clase abstracta para todos los importadores
- **csv_importer.py**: Importar archivos CSV con delimitadores personalizados
- **excel_importer.py**: Importar hojas de Excel con pandas
- **text_importer.py**: Importar archivos TXT/DAT

Flujo de importación:
```
Archivo → read_file() → validate_data() → insert_to_database()
```

#### `app/qr/`
- **qr_generator.py**: Generar códigos QR
- Métodos:
  - `generate_qr_from_text()`: QR desde texto simple
  - `generate_qr_from_data()`: QR desde diccionario JSON
  - `generate_qr_batch()`: Generar múltiples QR

#### `app/api/`
- **routes.py**: Endpoints REST
  - `POST /api/import/csv` - Importar CSV
  - `POST /api/import/excel` - Importar Excel
  - `POST /api/qr/generate` - Generar QR
  - `GET /api/data/{table}` - Obtener datos de tabla
  - `GET /api/health` - Health check

### Frontend Desktop (Python + PyQt5)

#### `ui/main_window.py`
- Ventana principal de la aplicación
- Barra de menú con opciones
- Sistema de pestañas

#### `ui/import_dialog.py`
- Interfaz para importar archivos
- Selector de delimitadores
- Vista previa de datos
- Barra de progreso

#### `ui/data_viewer.py`
- Tabla para visualizar datos
- Selector de tablas
- Botones de actualizar/exportar

#### `services/api_client.py`
- Cliente HTTP basado en `requests`
- Conexión con la API del backend
- Manejo de autenticación (future)

### Frontend Web (HTML/CSS/JavaScript)

#### `index.html`
- Estructura base de la página
- Navegación
- Áreas de contenido

#### `css/style.css`
- Estilos responsivos
- Tema moderno con gradientes
- Componentes (buttons, forms, tables)

#### `js/main.js`
- Funciones para cargar contenido dinámicamente
- Llamadas a la API
- Manejo de eventos

## Patrones de Diseño

### 1. Singleton Pattern
```python
# En DatabaseConnection
class DatabaseConnection:
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
```

### 2. Factory Pattern (en importadores)
```python
# Crear importer basado en tipo de archivo
if file_type == 'csv':
    importer = CSVImporter(file_path, table)
elif file_type == 'excel':
    importer = ExcelImporter(file_path, table)
```

### 3. Template Method Pattern
```python
# BaseImporter define estructura
# Subclases implementan read_file() y validate_data()
class BaseImporter(ABC):
    @abstractmethod
    def read_file(self): pass
    
    @abstractmethod
    def validate_data(self): pass
```

## Flujos de Datos

### Importación de Archivo CSV

```
Frontend (seleccionar archivo)
         ↓
API: POST /api/import/csv
         ↓
CSVImporter.read_file()
         ↓
CSVImporter.validate_data()
         ↓
DatabaseConnection.execute_query()
         ↓
MariaDB INSERT
         ↓
Response: {"status": "success", "rows": 100}
         ↓
Frontend (mostrar resultado)
```

### Generación de QR

```
Frontend (ingresar texto)
         ↓
API: POST /api/qr/generate
         ↓
QRGenerator.generate_qr_from_text()
         ↓
qrcode.QRCode.make_image()
         ↓
Guardar PNG en disco
         ↓
Response: {"status": "success", "filepath": "..."}
         ↓
Frontend (mostrar imagen QR)
```

### Visualización de Datos

```
Frontend (seleccionar tabla)
         ↓
API: GET /api/data/{table_name}
         ↓
DatabaseConnection.fetch_all()
         ↓
MariaDB SELECT
         ↓
Response: {"status": "success", "data": [...]}
         ↓
Frontend (renderizar tabla HTML)
```

## Manejo de Errores

Cada componente tiene su propio sistema de logging y manejo de errores:

```
# Configuración centralizada de logging
logging.basicConfig(
    level=config.LOG_LEVEL,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# Cada módulo obtiene su logger
logger = logging.getLogger(__name__)

# Uso
try:
    # operación
except Exception as e:
    logger.error(f"Error: {e}")
    return {"status": "error", "message": str(e)}
```

## Seguridad

### Planeado para futuros:
- Autenticación JWT
- Validación de entrada con Pydantic
- SQL injection prevention (prepared statements)
- CORS configuración restrictiva
- HTTPS en producción
- Rate limiting
- Validación de tipos de archivo

## Escalabilidad

- **Base de Datos**: Soporta múltiples usuarios con conexión única (Singleton)
- **API**: FastAPI permite múltiples workers con uvicorn
- **Frontend**: Puede manejar múltiples usuarios vía web
- **Importación**: Batch processing para archivos grandes

## Próximos Pasos

1. Implementar autenticación
2. Agregar logging persistente
3. Tests unitarios e integración
4. Documentación de API con Swagger
5. Frontend web completo
6. Exportación de datos
7. Estadísticas y reportes
