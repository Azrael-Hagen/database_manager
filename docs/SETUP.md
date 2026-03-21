# Guía de Instalación y Configuración

## Requisitos Previos

- **Python 3.9+** - [Descargar](https://www.python.org/downloads/)
- **MariaDB/MySQL** - [Descargar](https://mariadb.org/download/)
- **Git** (opcional) - [Descargar](https://git-scm.com/)

## Paso 1: Configurar Base de Datos

### 1.1 Crear base de datos
```sql
CREATE DATABASE database_manager CHARACTER SET utf8mb4;
USE database_manager;
```

### 1.2 Crear tabla de ejemplo
```sql
CREATE TABLE datos_importados (
    id INT AUTO_INCREMENT PRIMARY KEY,
    nombre VARCHAR(255) NOT NULL,
    email VARCHAR(255),
    telefono VARCHAR(20),
    fecha_creacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

## Paso 2: Instalar Dependencias del Backend

```bash
cd backend
pip install -r requirements.txt
```

## Paso 3: Configurar Variables de Entorno

Copiar `.env.example` a `.env` y actualizar valores:

```bash
cp .env.example .env
```

Editar `.env` con tus credenciales de base de datos:
```
DB_HOST=localhost
DB_USER=root
DB_PASSWORD=tu_contraseña
DB_NAME=database_manager
DB_PORT=3306
```

## Paso 4: Iniciar el Backend

```bash
cd backend
python main.py
```

El servidor estará disponible en: `http://localhost:8000`

### Verificar API
- Health Check: `http://localhost:8000/api/health`
- Panel Web: `http://localhost:8000`

## Paso 5: Instalar Dependencias del Frontend

```bash
cd frontend
pip install -r requirements.txt
```

## Paso 6: Iniciar el Frontend Desktop

```bash
cd frontend
python main.py
```

## Estructura de Archivos Importantes

```
database_manager/
├── backend/
│   ├── main.py           # Punto de entrada del backend
│   ├── app/
│   │   ├── config.py     # Configuración de la app
│   │   ├── importers/    # Módulos de importación
│   │   ├── qr/           # Generador de QR
│   │   ├── database/     # Conexión a BD
│   │   └── api/          # Rutas de la API
│   └── requirements.txt  # Dependencias Python
├── frontend/
│   ├── main.py          # Punto de entrada GUI
│   ├── ui/              # Componentes de la interfaz
│   ├── services/        # Cliente API
│   └── requirements.txt  # Dependencias Python
└── .env                 # Variables de entorno
```

## Puertos por Defecto

- **Backend API**: 8000
- **Base de Datos**: 3306
- **Frontend Web**: 3000 (servido desde backend)

## Troubleshooting

### Error de conexión a base de datos
- Verificar que MariaDB/MySQL está corriendo
- Verificar credenciales en `.env`
- Verificar que la base de datos existe

### Error al importar módulos
```bash
pip install --upgrade pip
pip install -r requirements.txt --force-reinstall
```

### Puerto 8000 en uso
```bash
netstat -ano | findstr :8000  # Windows
lsof -i :8000                  # Linux/Mac
```

## Próximos Pasos

1. Revisar [Documentación de API](API.md)
2. Revisar [Arquitectura del Proyecto](ARCHITECTURE.md)
3. Implementar features completas
