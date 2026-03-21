# Guía Rápida de Inicio

## 1. Preparación Inicial

### Windows PowerShell
```powershell
# Navegar a la carpeta del proyecto
cd "c:\Users\Azrael\OneDrive\Documentos\Herramientas\database_manager"

# Copiar archivo de configuración
Copy-Item ".env.example" ".env"
```

### Editar `.env` con tus datos de MariaDB
```
DB_HOST=localhost
DB_USER=root
DB_PASSWORD=tu_contraseña
DB_NAME=database_manager
DB_PORT=3306
```

## 2. Configurar Backend

```powershell
cd backend

# Crear entorno virtual (opcional pero recomendado)
python -m venv venv
.\venv\Scripts\Activate

# Instalar dependencias
pip install -r requirements.txt

# Crear base de datos
python init_db.py

# Iniciar servidor
python main.py
```

El servidor estará en: **http://localhost:8000**

## 3. Prueba la API

```powershell
# En otra ventana de PowerShell
Invoke-WebRequest -Uri "http://localhost:8000/api/health"
```

Deberías ver:
```json
{"status": "ok"}
```

## 4. Acceder al Panel Web

En tu navegador: `http://localhost:8000`

## 5. Iniciar Frontend Desktop (opcional)

```powershell
cd ..\frontend

# Entorno virtual
python -m venv venv
.\venv\Scripts\Activate

# Instalar dependencias
pip install -r requirements.txt

# Ejecutar
python main.py
```

## Estructura Creada

```
database_manager/
├── backend/                    # API y lógica
│   ├── app/
│   │   ├── config.py          # Configuración
│   │   ├── database/          # Conexión BD
│   │   ├── importers/         # CSV, Excel, TXT
│   │   ├── qr/                # Generador QR
│   │   ├── api/               # Rutas REST
│   │   └── utils/             # Utilidades
│   ├── main.py                # Punto de entrada
│   ├── init_db.py             # Inicializar BD
│   └── requirements.txt
│
├── frontend/                   # GUI Desktop (PyQt5)
│   ├── ui/                    # Interfaz gráfica
│   ├── services/              # Cliente API
│   ├── main.py                # Punto de entrada
│   └── requirements.txt
│
├── web/                        # Front web (HTML/JS)
│   ├── index.html
│   ├── css/style.css
│   └── js/main.js
│
├── tests/                      # Tests
├── docs/                       # Documentación
├── .env                        # Configuración (crear)
└── README.md
```

## Features Implementados

✅ **Backend:**
- API REST con FastAPI
- Importadores (CSV, Excel, TXT/DAT)
- Generador de códigos QR
- Conexión a MariaDB
- Validación de datos

✅ **Frontend Desktop:**
- Interfaz con PyQt5
- Importador de archivos
- Visor de datos
- Cliente API

✅ **Frontend Web:**
- Panel HTML moderno
- Visualización de datos
- Generador de QR
- Responsive design

## Próximos Pasos

1. **Testing**
   ```powershell
   pytest tests/
   ```

2. **Importar datos**
   - Prepare un archivo CSV/Excel
   - Suba a través de la interfaz web o desktop

3. **Generar QR**
   - Acceda a la sección de QR
   - Genere códigos para cada dato

4. **Expandir**
   - Autenticación de usuarios
   - Exportación de reportes
   - Estadísticas avanzadas

## Troubleshooting

**Error: "No module named mysql.connector"**
```powershell
pip install mysql-connector-python
```

**Error: "Cannot connect to database"**
```
- Verificar que MariaDB/MySQL está ejecutándose
- Revisar credenciales en .env
- Verificar puerto 3306 disponible
```

**Puerto 8000 en uso**
```powershell
netstat -ano | findstr :8000
# Cambiar puerto en .env: API_PORT=8001
```

## Contacto y Soporte

Documentación completa en:
- [SETUP.md](docs/SETUP.md) - Instalación detallada
- [API.md](docs/API.md) - Documentación de API
- [ARCHITECTURE.md](docs/ARCHITECTURE.md) - Arquitectura del proyecto
