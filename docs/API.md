# Documentación de API REST

**URL Base**: `http://localhost:8000/api`

## Endpoints

### Health Check
```
GET /health
```

**Descripción**: Verificar que el servidor está activo y funcionando.

**Respuesta (200)**:
```json
{
    "status": "ok"
}
```

---

### Importar CSV
```
POST /import/csv
```

**Descripción**: Importar datos desde archivo CSV.

**Parámetros**:
- `file` (required): Archivo CSV a importar
- `table_name` (required): Nombre de la tabla destino
- `delimiter` (optional): Delimitador usado (defecto: ",")

**Ejemplo de solicitud**:
```bash
curl -X POST "http://localhost:8000/api/import/csv" \
  -F "file=@datos.csv" \
  -F "table_name=datos_importados" \
  -F "delimiter=,"
```

**Respuesta (200)**:
```json
{
    "status": "success",
    "message": "Importados 100 registros",
    "data": [
        {"nombre": "Juan", "email": "juan@email.com", "telefono": "1234567890"},
        {"nombre": "María", "email": "maria@email.com", "telefono": "0987654321"}
    ]
}
```

**Respuesta de Error (400)**:
```json
{
    "status": "error",
    "message": "Error validando datos",
    "errors": ["Fila 5: número de columnas inconsistente"]
}
```

---

### Importar Excel
```
POST /import/excel
```

**Descripción**: Importar datos desde archivo Excel.

**Parámetros**:
- `file` (required): Archivo Excel a importar
- `table_name` (required): Nombre de la tabla destino
- `sheet_name` (optional): Nombre o índice de la hoja (defecto: 0)

**Ejemplo**:
```bash
curl -X POST "http://localhost:8000/api/import/excel" \
  -F "file=@datos.xlsx" \
  -F "table_name=datos_importados" \
  -F "sheet_name=0"
```

**Respuesta (200)**:
```json
{
    "status": "success",
    "message": "Importados 50 registros",
    "data": [...]
}
```

---

### Generar Código QR
```
POST /qr/generate
```

**Descripción**: Generar un código QR desde un texto.

**Body (JSON)**:
```json
{
    "text": "Contenido del QR"
}
```

**Ejemplo**:
```bash
curl -X POST "http://localhost:8000/api/qr/generate" \
  -H "Content-Type: application/json" \
  -d '{"text": "https://example.com"}'
```

**Respuesta (200)**:
```json
{
    "status": "success",
    "filepath": "C:\\...\\qr_20260321_143022.png"
}
```

---

### Obtener Datos de Tabla
```
GET /data/{table_name}
```

**Descripción**: Obtener todos los registros de una tabla.

**Parámetros de URL**:
- `table_name` (required): Nombre de la tabla

**Ejemplo**:
```bash
curl "http://localhost:8000/api/data/datos_importados"
```

**Respuesta (200)**:
```json
{
    "status": "success",
    "data": [
        {
            "id": 1,
            "nombre": "Juan",
            "email": "juan@email.com",
            "telefono": "1234567890",
            "fecha_creacion": "2026-03-21T14:30:22"
        },
        {
            "id": 2,
            "nombre": "María",
            "email": "maria@email.com",
            "telefono": "0987654321",
            "fecha_creacion": "2026-03-21T14:30:23"
        }
    ]
}
```

---

## Códigos de Estado HTTP

| Código | Descripción |
|--------|-------------|
| 200 | OK - Solicitud exitosa |
| 201 | Created - Recurso creado |
| 400 | Bad Request - Parámetros inválidos |
| 401 | Unauthorized - Autenticación requerida |
| 404 | Not Found - Recurso no encontrado |
| 500 | Internal Server Error - Error del servidor |

---

## Formatos de Archivo Soportados

### CSV
- Delimitadores: coma (,), punto y coma (;), tabulación, pipe (|), espacio
- Codificación: UTF-8
- Ejemplo:
```
nombre,email,telefono
Juan,juan@email.com,1234567890
María,maria@email.com,0987654321
```

### Excel
- Formatos: .xlsx, .xls
- Puede especificar hoja por nombre o índice

### TXT/DAT
- Delimitadores personalizables
- Primera línea como headers
- Ejemplo:
```
nombre	email	telefono
Juan	juan@email.com	1234567890
María	maria@email.com	0987654321
```

---

## Ejemplos de Uso

### Python (requests)
```python
import requests

# Importar CSV
with open('datos.csv', 'rb') as f:
    files = {'file': f}
    data = {'table_name': 'datos_importados', 'delimiter': ','}
    response = requests.post(
        'http://localhost:8000/api/import/csv',
        files=files,
        data=data
    )
    print(response.json())

# Generar QR
response = requests.post(
    'http://localhost:8000/api/qr/generate',
    json={'text': 'Hola Mundo'}
)
print(response.json())

# Obtener datos
response = requests.get(
    'http://localhost:8000/api/data/datos_importados'
)
data = response.json()
for row in data['data']:
    print(row)
```

### JavaScript (fetch)
```javascript
// Importar CSV
const formData = new FormData();
formData.append('file', fileInput.files[0]);
formData.append('table_name', 'datos_importados');
formData.append('delimiter', ',');

fetch('http://localhost:8000/api/import/csv', {
    method: 'POST',
    body: formData
})
.then(res => res.json())
.then(data => console.log(data));

// Generar QR
fetch('http://localhost:8000/api/qr/generate', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({text: 'Hola Mundo'})
})
.then(res => res.json())
.then(data => console.log(data));

// Obtener datos
fetch('http://localhost:8000/api/data/datos_importados')
    .then(res => res.json())
    .then(data => {
        data.data.forEach(row => console.log(row));
    });
```

---

## Documentación Interactiva

Una vez que el backend esté corriendo, puedes acceder a la documentación interactiva en:

- **Swagger UI**: `http://localhost:8000/docs`
- **ReDoc**: `http://localhost:8000/redoc`
