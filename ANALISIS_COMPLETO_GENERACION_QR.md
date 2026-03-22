# 📊 ANÁLISIS EXHAUSTIVO: GENERACIÓN DE QR EN CREACIÓN DE AGENTES

## Resumen Ejecutivo
La generación de QR cuando se crea un agente **NO ocurre automáticamente** en la creación. Es un proceso **en dos pasos**:
1. **Paso 1**: Crear el agente con el endpoint `POST /api/qr/agentes/manual`
2. **Paso 2**: Generar el QR bajo demanda cuando el usuario marca la opción "Generar QR al crear"

---

## 1️⃣ PUNTO 1: Donde se genera el QR

### A. Flujo de Generación de QR

El QR se genera en el **endpoint GET `/api/qr/agente/{agente_id}/qr`** ubicado en:
- **Archivo**: `backend/app/api/qr.py`
- **Línea**: 1067-1103

```python
@router.get("/agente/{agente_id}/qr")
async def obtener_qr_agente(
    agente_id: int,
    request: Request,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Obtener payload y URL pública del QR independiente de un agente."""
    agente = db.query(DatoImportado).filter(
        DatoImportado.id == agente_id,
        DatoImportado.es_activo.is_(True)
    ).first()
    
    # Construye URL pública
    public_base_url = config.get_public_base_url(request)
    public_url = f"{public_base_url}/api/qr/public/verify/{agente.uuid}"
    
    # Obtiene información de líneas asignadas
    lineas_agente = _agent_active_lines(db, agente.id)
    
    # Construye payload del QR
    payload = {
        "agente_id": agente.id,
        "uuid": agente.uuid,
        "nombre": agente.nombre,
        "telefono": agente.telefono,
        "numero_voip": _extract_voip(agente),
        "tiene_asignacion": _has_assignment(agente) or bool(lineas_agente),
        "lineas": lineas_agente,
        "public_url": public_url,
    }

    # ⭐ GENERACIÓN DE QR AQUÍ
    generator = QRGenerator()
    filename = f"agente_{agente.id}_{agente.uuid}.png"
    filepath = generator.generate_qr_from_text(public_url, filename)
    
    # Almacena metadata en la base de datos
    agente.qr_filename = filename
    agente.contenido_qr = json.dumps(payload, ensure_ascii=False)
    db.add(agente)
    db.commit()

    return {"status": "success", "data": {**payload, "qr_filename": filename, "qr_path": filepath}}
```

### B. Clase Generadora de QR

**Archivo**: `backend/app/qr/qr_generator.py`
**Clase**: `QRGenerator`

#### Métodos disponibles:

1. **`generate_qr_from_text(text, filename=None)`**
   - Genera QR desde texto simpl
   - Configura: `version=1`, `error_correction=ERROR_CORRECT_L`, `box_size=10`, `border=4`
   - Guarda en PNG en la carpeta configurada
   - Retorna: ruta del archivo

2. **`generate_qr_from_data(data_dict, filename=None)`**
   - Genera QR desde diccionario JSON
   - Serializa a JSON y llama a `generate_qr_from_text()`

3. **`generate_qr_batch(data_list, prefix="qr")`**
   - Genera múltiples QR en lote
   - Útil para importaciones masivas (currently no utilizado en agentes)

#### Código de generación base:

```python
qr = qrcode.QRCode(
    version=1,
    error_correction=qrcode.constants.ERROR_CORRECT_L,
    box_size=10,
    border=4,
)
qr.add_data(text)        # Agrega la URL pública
qr.make(fit=True)
img = qr.make_image(fill_color="black", back_color="white")
filepath = os.path.join(self.output_folder, filename)
img.save(filepath)
```

### C. Descarga de QR

El usuario puede descargar el QR generado mediante:
- **Endpoint**: `GET /api/qr/agente/{agente_id}/qr/download`
- **Ubicación**: `backend/app/api/qr.py`, línea 1107

```python
@router.get("/agente/{agente_id}/qr/download")
async def descargar_qr_agente(
    agente_id: int,
    request: Request,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Descargar PNG del QR individual del agente."""
    result = await obtener_qr_agente(agente_id, request=request, current_user=current_user, db=db)
    path = (result.get("data") or {}).get("qr_path")
    if not path:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="QR no disponible")
    return FileResponse(path, media_type="image/png", filename=os.path.basename(path))
```

---

## 2️⃣ PUNTO 2: Código del formulario frontend (Altas de Agentes)

### A. HTML del Formulario

**Archivo**: `web/index.html`
**Líneas**: 235-351

```html
<section id="altasAgentesSection" class="panel" style="display: none;">
    <h1>Altas de Agentes</h1>
    <p class="hint">Usa esta pantalla para onboarding: crea catálogo de ladas, 
    da de alta al agente, asigna línea y genera su QR inicial sin mezclarlo 
    con verificación o cobros.</p>

    <!-- Sección 1: Catálogo de Ladas -->
    <h3 style="margin-top: 22px;">Catálogo de Ladas</h3>
    <form onsubmit="crearLadaCatalogo(event)">
        <div class="search-bar">
            <input type="text" id="ladaCodigoInput" placeholder="Lada (ej: 332, 55)" required>
            <input type="text" id="ladaRegionInput" placeholder="Región opcional (ej: Guadalajara)">
            <button type="submit" class="btn btn-secondary">Crear / Reactivar Lada</button>
        </div>
    </form>

    <!-- Sección 2: Alta Manual de Agente ⭐ -->
    <h3 style="margin-top: 22px;">Alta Manual de Agente</h3>
    <form onsubmit="crearAgenteManual(event)">
        <div class="search-bar">
            <input type="text" id="agenteNombreInput" placeholder="Nombre" required>
            <input type="text" id="agenteAliasInput" placeholder="Alias">
            <input type="text" id="agenteUbicacionInput" placeholder="Ubicación">
            <input type="text" id="agenteTelefonoInput" placeholder="Teléfono">
        </div>
        <div class="search-bar" style="margin-top:8px;">
            <input type="text" id="agenteFpInput" placeholder="FP">
            <input type="text" id="agenteFcInput" placeholder="FC">
            <input type="text" id="agenteGrupoInput" placeholder="Grupo">
            <input type="text" id="agenteEmpresaInput" placeholder="Empresa">
        </div>
        <div class="search-bar" style="margin-top:8px;">
            <select id="agenteModoAsignacion" onchange="cambiarModoAsignacionAgente()">
                <option value="ninguna">Sin asignación inicial</option>
                <option value="auto">Asignación automática</option>
                <option value="manual">Asignación manual</option>
            </select>
            <select id="agenteLadaObjetivoSelect">
                <option value="">-- Lada preferida (opcional) --</option>
            </select>
            <select id="agenteLineaManualSelect" style="display:none;">
                <option value="">-- Línea manual existente --</option>
            </select>
            <input type="text" id="agenteLineaManualInput" style="display:none;" 
                   placeholder="Número de línea manual (si no existe)">
        </div>
        
        <!-- ⭐ CHECKBOX CLAVE: Generar QR al crear -->
        <div class="search-bar" style="margin-top:8px;">
            <label class="live-control" style="align-items:center;">
                <input type="checkbox" id="agenteGenerarQrAlCrear" checked>
                <span>Generar QR al crear</span>
            </label>
            <button type="submit" class="btn">Crear Agente</button>
        </div>
    </form>

    <!-- Resultado de QR -->
    <div id="altaAgenteQrResult" style="margin-top: 12px;"></div>
    <div id="altaAgenteQrContainer" style="margin-top: 18px; text-align: center;"></div>

    <!-- Sección 3: Líneas y Asignación -->
    <h3 style="margin-top: 22px;">Líneas y Asignación</h3>
    <!-- ... resto de formularios ... -->
</section>
```

**Elementos clave del formulario:**
- ✅ Checkbox `agenteGenerarQrAlCrear` (marcado por defecto)
- ✅ Textarea para visualizar QR generado: `altaAgenteQrContainer`
- ✅ Div para mensajes de resultado: `altaAgenteQrResult`

### B. JavaScript de Creación de Agente

**Archivo**: `web/js/main.js`
**Líneas**: 1356-1430

```javascript
async function crearAgenteManual(e) {
    e.preventDefault();
    const modo = document.getElementById('agenteModoAsignacion')?.value || 'ninguna';
    const payload = {
        nombre: document.getElementById('agenteNombreInput')?.value.trim(),
        alias: document.getElementById('agenteAliasInput')?.value.trim() || null,
        ubicacion: document.getElementById('agenteUbicacionInput')?.value.trim() || null,
        telefono: document.getElementById('agenteTelefonoInput')?.value.trim() || null,
        fp: document.getElementById('agenteFpInput')?.value.trim() || null,
        fc: document.getElementById('agenteFcInput')?.value.trim() || null,
        grupo: document.getElementById('agenteGrupoInput')?.value.trim() || null,
        empresa: document.getElementById('agenteEmpresaInput')?.value.trim() || null,
        modo_asignacion: modo,
        lada_objetivo: document.getElementById('agenteLadaObjetivoSelect')?.value || null
    };

    if (!payload.nombre) {
        alert('El nombre del agente es obligatorio.');
        return;
    }

    if (modo === 'manual') {
        payload.linea_id = Number(document.getElementById('agenteLineaManualSelect')?.value || 0) || null;
        payload.numero_linea_manual = document.getElementById('agenteLineaManualInput')?.value.trim() || null;
        if (!payload.linea_id && !payload.numero_linea_manual) {
            alert('Para modo manual selecciona una línea o escribe un número nuevo.');
            return;
        }
    }

    try {
        // ✅ PASO 1: Crear el agente
        const result = await apiClient.crearAgenteManual(payload);
        const data = result.data || {};
        
        document.getElementById('qrAgenteId').value = data.agente_id || '';
        document.getElementById('qrTelefono').value = payload.telefono || '';
        
        const asignacion = data.asignacion || {};
        const lineaText = asignacion.asignada ? `Línea ${asignacion.linea_numero} asignada.` : 'Sin asignación inicial.';
        alert(`Agente creado (ID ${data.agente_id}). ${lineaText}`);

        // Limpiar formulario
        [
            'agenteNombreInput',
            'agenteAliasInput',
            'agenteUbicacionInput',
            'agenteTelefonoInput',
            'agenteFpInput',
            'agenteFcInput',
            'agenteGrupoInput',
            'agenteEmpresaInput',
            'agenteLineaManualInput'
        ].forEach(id => {
            const el = document.getElementById(id);
            if (el) el.value = '';
        });
        document.getElementById('agenteModoAsignacion').value = 'ninguna';
        document.getElementById('agenteLadaObjetivoSelect').value = '';
        document.getElementById('agenteLineaManualSelect').value = '';
        cambiarModoAsignacionAgente();

        await cargarLineasYAgentes();
        await cargarAgentesGestion(false);
        
        // ✅ PASO 2: Generar QR si checkbox está marcado
        if (document.getElementById('agenteGenerarQrAlCrear')?.checked && data.agente_id) {
            await previsualizarQrAlta(data.agente_id);
        }
    } catch (error) {
        console.error('Error:', error);
        alert('Error creando agente manual: ' + error.message);
    }
}
```

---

## 3️⃣ PUNTO 3: Endpoint Backend que recibe creación de agentes

### A. Endpoint POST `/api/qr/agentes/manual`

**Archivo**: `backend/app/api/qr.py`
**Línea**: 558-656

```python
@router.post("/agentes/manual")
async def crear_agente_manual(
    payload: dict,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Crear agente manualmente y asignar linea de forma opcional."""
    
    # ✅ Validaciones
    nombre = str((payload or {}).get("nombre") or "").strip()
    if not nombre:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Nombre es requerido")

    telefono = str((payload or {}).get("telefono") or "").strip() or None
    email = str((payload or {}).get("email") or "").strip() or None
    empresa = str((payload or {}).get("empresa") or "").strip() or None
    ciudad = str((payload or {}).get("ciudad") or "").strip() or None
    pais = str((payload or {}).get("pais") or "").strip() or None

    # ✅ Datos adicionales (metadatos)
    datos_adicionales = {
        "alias": str((payload or {}).get("alias") or "").strip() or None,
        "ubicacion": str((payload or {}).get("ubicacion") or "").strip() or None,
        "fp": str((payload or {}).get("fp") or "").strip() or None,
        "fc": str((payload or {}).get("fc") or "").strip() or None,
        "grupo": str((payload or {}).get("grupo") or "").strip() or None,
        "numero_voip": str((payload or {}).get("numero_voip") or "").strip() or None,
    }
    datos_adicionales = {k: v for k, v in datos_adicionales.items() if v not in (None, "")}

    # ✅ Modo de asignación (ninguna, manual, auto)
    modo = str((payload or {}).get("modo_asignacion") or "ninguna").strip().lower()
    if modo not in {"ninguna", "manual", "auto"}:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="modo_asignacion invalido")

    lada_objetivo = str((payload or {}).get("lada_objetivo") or "").strip() or None
    if lada_objetivo:
        lada_objetivo = _normalize_lada(lada_objetivo)

    # ✅ Crear agente en base de datos
    agente = DatoImportado(
        nombre=nombre,
        email=email,
        telefono=telefono,
        empresa=empresa,
        ciudad=ciudad,
        pais=pais,
        datos_adicionales=json.dumps(datos_adicionales, ensure_ascii=False) if datos_adicionales else None,
        creado_por=current_user.get("id"),
        es_activo=True,
    )
    db.add(agente)
    db.flush()

    asignacion_resumen = {"modo": modo, "asignada": False}

    # ✅ Manejar asignación de línea según modo
    if modo == "manual":
        linea = _resolve_or_create_line_for_manual_assignment(db, payload)
        current = db.query(AgenteLineaAsignacion).filter(
            AgenteLineaAsignacion.linea_id == linea.id,
            AgenteLineaAsignacion.es_activa.is_(True),
        ).first()
        if current and current.agente_id != agente.id:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="La linea seleccionada ya esta ocupada")
        if not current:
            db.add(AgenteLineaAsignacion(agente_id=agente.id, linea_id=linea.id, es_activa=True))
        asignacion_resumen = {
            "modo": modo,
            "asignada": True,
            "linea_id": linea.id,
            "linea_numero": linea.numero,
        }

    if modo == "auto":
        linea = _choose_free_line_automatically(db, lada_objetivo)
        if linea:
            db.add(AgenteLineaAsignacion(agente_id=agente.id, linea_id=linea.id, es_activa=True))
            asignacion_resumen = {
                "modo": modo,
                "asignada": True,
                "linea_id": linea.id,
                "linea_numero": linea.numero,
            }
        else:
            asignacion_resumen = {
                "modo": modo,
                "asignada": False,
                "reason": "No hay lineas libres para asignar",
            }

    _set_agent_lada_preference(db, agente.id, lada_objetivo)

    # ✅ Commit final
    db.commit()
    db.refresh(agente)

    # ✅ Retorna agente creado (SIN generar QR aquí)
    return {
        "status": "success",
        "data": {
            "agente_id": agente.id,
            "uuid": agente.uuid,
            "nombre": agente.nombre,
            "telefono": agente.telefono,
            "modo_asignacion": modo,
            "asignacion": asignacion_resumen,
            "lineas": _agent_active_lines(db, agente.id),
        },
    }
```

**Punto clave**: Este endpoint **NO genera QR**. Solo crea el agente en la BD. La generación de QR es un proceso separado que ocurre después.

---

## 4️⃣ PUNTO 4: Bibliotecas de QR importadas y configuración

### A. Dependencia en requirements.txt

**Archivo**: `backend/requirements.txt`
**Línea**: 8

```
qrcode[pil]==7.4.2
```

**Desglose**:
- **Paquete**: `qrcode[pil]` - QR Code Generator con soporte PIL/Pillow
- **Versión**: `7.4.2`
- **Descripción**: Librería popularde Python para generar códigos QR

### B. Importaciones en el Código

#### En `backend/app/api/qr.py` (línea 26):
```python
from app.qr import QRGenerator
```

#### En `backend/app/api/importacion.py` (línea 17):
```python
from app.qr import QRGenerator
```

#### En `backend/app/qr/qr_generator.py` (línea 1-2):
```python
import qrcode
import logging
```

### C. Configuración de Directorios

**Archivo**: `backend/app/config.py`
**Líneas**: 58-65

```python
# Archivos
UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), "..", "uploads")
QR_FOLDER = os.path.join(os.path.dirname(__file__), "..", "qr_codes")  # ✅ Carpeta de QR
BACKUP_FOLDER = os.path.join(os.path.dirname(__file__), "..", "backups")

@classmethod
def create_directories(cls):
    """Crear directorios necesarios."""
    os.makedirs(cls.UPLOAD_FOLDER, exist_ok=True)
    os.makedirs(cls.QR_FOLDER, exist_ok=True)  # ✅ Crea carpeta si no existe
    os.makedirs(cls.BACKUP_FOLDER, exist_ok=True)
```

### D. Configuración de URL Pública

**Archivo**: `backend/app/config.py`
**Líneas**: 28-46

```python
API_HOST = os.getenv("API_HOST", "0.0.0.0")
API_PORT = int(os.getenv("API_PORT", 8000))
API_DEBUG = os.getenv("API_DEBUG", "True").lower() == "true"
PUBLIC_BASE_URL = (os.getenv("PUBLIC_BASE_URL", "") or "").strip().rstrip("/")
LOCAL_HOSTNAME = (os.getenv("LOCAL_HOSTNAME", "") or "").strip()

@classmethod
def get_public_base_url(cls, request=None) -> str:
    """Resolver URL pública base para enlaces QR y acceso desde red."""
    if cls.PUBLIC_BASE_URL:
        return cls.PUBLIC_BASE_URL

    if request is not None:
        forwarded_proto = request.headers.get("x-forwarded-proto")
        forwarded_host = request.headers.get("x-forwarded-host")
        if forwarded_proto and forwarded_host:
            return f"{forwarded_proto}://{forwarded_host}".rstrip("/")
        return str(request.base_url).rstrip("/")

    if cls.LOCAL_HOSTNAME:
        return f"http://{cls.LOCAL_HOSTNAME}:{cls.API_PORT}"

    return f"http://localhost:{cls.API_PORT}"
```

---

## 5️⃣ FLUJO COMPLETO RESUMIDO

```
┌─────────────────────────────────────────────────────────────────┐
│ 1. USUARIO llena formulario en "Altas de Agentes"                │
│    - Nombre, alias, ubicación, teléfono, etc.                   │
│    - Selecciona modo de asignación                              │
│    - ✅ CHECKBOX "Generar QR al crear" (checked por defecto)    │
└──────────────────────────┬──────────────────────────────────────┘
                           ↓
┌─────────────────────────────────────────────────────────────────┐
│ 2. JavaScript: crearAgenteManual()                              │
│    - Recopila datos del formulario                              │
│    - Valida campos requeridos                                   │
│    - Llama: apiClient.crearAgenteManual(payload)               │
└──────────────────────────┬──────────────────────────────────────┘
                           ↓
┌─────────────────────────────────────────────────────────────────┐
│ 3. API Cliente JS: apiClient.crearAgenteManual()                │
│    - Endpoint: POST /api/qr/agentes/manual                      │
│    - Envía payload al backend                                   │
└──────────────────────────┬──────────────────────────────────────┘
                           ↓
┌─────────────────────────────────────────────────────────────────┐
│ 4. Backend: crear_agente_manual()                               │
│    - Valida nombre (requerido)                                  │
│    - Crea record DatoImportado en BD                           │
│    - Maneja asignación de línea según modo                      │
│    - Retorna: agente_id, uuid, información de asignación       │
│    - ❌ NO genera QR aquí                                       │
└──────────────────────────┬──────────────────────────────────────┘
                           ↓
┌─────────────────────────────────────────────────────────────────┐
│ 5. JavaScript: Verifica checkbox "agenteGenerarQrAlCrear"       │
│    - Si checked: llama previsualizarQrAlta(agente_id)           │
│    - Si no checked: termina aquí                                │
└──────────────────────────┬──────────────────────────────────────┘
                           ↓
┌─────────────────────────────────────────────────────────────────┐
│ 6. JavaScript: previsualizarQrAlta() → generarQrIndividual()    │
│    - Llama: apiClient.getQrAgente(agenteId)                    │
│    - Endpoint: GET /api/qr/agente/{agente_id}/qr              │
└──────────────────────────┬──────────────────────────────────────┘
                           ↓
┌─────────────────────────────────────────────────────────────────┐
│ 7. Backend: obtener_qr_agente()                                 │
│    - Obtiene agente de BD                                       │
│    - Construye URL pública: /api/qr/public/verify/{uuid}       │
│    - Obtiene líneas asignadas del agente                        │
│    - ✅ Crea instancia de QRGenerator()                         │
│    - ✅ Llama: generator.generate_qr_from_text(public_url)      │
│    - ✅ Guarda PNG en: backend/qr_codes/agente_{id}_{uuid}.png │
│    - Almacena metadata en BD:                                   │
│        - qr_filename                                            │
│        - contenido_qr (JSON payload)                            │
│    - Retorna: payload + ruta del archivo PNG                    │
└──────────────────────────┬──────────────────────────────────────┘
                           ↓
┌─────────────────────────────────────────────────────────────────┐
│ 8. JavaScript: renderSimpleQR()                                 │
│    - Renderiza QR visualmente usando qrcode.min.js              │
│    - Muestra URL pública para verificación                      │
│    - Botón para descargar PNG                                   │
│    - Botón para copiar URL al portapapeles                      │
└─────────────────────────────────────────────────────────────────┘
```

---

## 6️⃣ DATOS QUE CONTIENE EL QR

El QR codifica una **URL pública**, no directamente los datos:

```
URL: https://[dominio]/api/qr/public/verify/[uuid-del-agente]
```

**Cuando se escanea el QR**, la URL lleva al endpoint `GET /api/qr/public/verify/{uuid}` que renderiza una página HTML con:

```javascript
{
  "agente_id": 123,
  "uuid": "abc123-def456",
  "nombre": "Juan Pérez",
  "telefono": "555-1234",
  "numero_voip": "1001",
  "tiene_asignacion": true,
  "lineas": [
    {
      "id": 1,
      "numero": "525511223344",
      "tipo": "VOIP"
    }
  ],
  "public_url": "https://dominio/api/qr/public/verify/abc123-def456"
}
```

---

## 7️⃣ PUNTOS DONDE SE TOCA LA GENERACIÓN DE QR

### ✅ Generación de QR:
1. **Endpoint GET `/api/qr/agente/{agente_id}/qr`** - Única fuente de generación
2. **Clase `QRGenerator.generate_qr_from_text()`** - Método que crea el código

### ✅ Descarga de QR:
3. **Endpoint GET `/api/qr/agente/{agente_id}/qr/download`** - Descarga el PNG

### ✅ Verificación de QR:
4. **Endpoint GET `/api/qr/public/verify/{uuid}`** - Página pública de verificación

### ✅ Escaneo de QR:
5. **Endpoint POST `/api/qr/scan/verify`** - Valida contenido escaneado (QR o barcode)

### ✅ Generación de QR masiva (en importación):
6. **Archivo `backend/app/api/importacion.py`** - Importa `QRGenerator` pero no lo usa actualmente

---

## 8️⃣ CONFIGURACIÓN y VARIABLES DE ENTORNO

### .env necesario:

```bash
# URL pública base (para generar URLs en QR)
PUBLIC_BASE_URL=https://mi-dominio.com

# O usar LOCAL_HOSTNAME para desarrollo local
LOCAL_HOSTNAME=192.168.1.100

# API Puerto
API_PORT=8000
```

### Rutas de archivos (configuradas automáticamente):

```
backend/
  qr_codes/                    # Carpeta donde se guardan los PNG
    agente_1_abc123.png
    agente_2_def456.png
```

---

## 9️⃣ POSIBLES PROBLEMAS y SOLUCIONES

### Problema 1: QR no se genera
**Causa**: Lacheckbox "Generar QR al crear" no estáctivada
**Solución**: Verificar que esté marcada en el formulario

### Problema 2: Librería qrcode no instalada
**Causa**: requirements.txt no satisfecho
**Solución**: 
```bash
pip install qrcode[pil]==7.4.2
```

### Problema 3: Carpeta qr_codes no existe
**Causa**: `config.create_directories()` no fue llamado
**Solución**: Verificar que se llame en `main.py`:
```python
from app.config import config
config.create_directories()
```

### Problema 4: URL pública incorrecta en QR
**Causa**: `PUBLIC_BASE_URL` no configurado
**Solución**: Establecer variable de entorno

### Problema 5: Conexión entre API y cliente rota
**Causa**: CORS no configurado o rutas incorrectas
**Solución**: Revisar URL en `apiClient.getQrAgente()`

---

## 🔟 RESUMEN de DEPENDENCIAS

| Componente | Archivo | Propósito |
|-----------|---------|-----------|
| QRGenerator | `backend/app/qr/qr_generator.py` | Genera códigos QR |
| qrcode library | `requirements.txt` | Librería de QR (v7.4.2) |
| Pillow | `requirements.txt` | Procesamiento de imágenes |
| Endpoint generador | `backend/app/api/qr.py:1067` | GET `/api/qr/agente/{id}/qr` |
| Endpoint descarga | `backend/app/api/qr.py:1107` | GET `/api/qr/agente/{id}/qr/download` |
| Formulario | `web/index.html:235` | UI "Altas de Agentes" |
| Handler JS | `web/js/main.js:1356` | Validación y envío de datos |
| Cliente API | `web/js/api-client.js:301` | Llamadas HTTP |

---

## 📋 CHECKLIST: Verificar que todo funciona

- [ ] `pip install qrcode[pil]==7.4.2` instalado
- [ ] Carpeta `backend/qr_codes/` existe (o se crea automáticamente)
- [ ] `config.create_directories()` se llama en `backend/main.py`
- [ ] `PUBLIC_BASE_URL` configurado en `.env` (o `LOCAL_HOSTNAME`)
- [ ] Formulario "Altas de Agentes" visible
- [ ] Checkbox "Generar QR al crear" apareceactívado
- [ ] Crear un agente de prueba
- [ ] Ver que aparece el QR generado
- [ ] Descargar PNG verificando que no sea vacío
- [ ] Escanear QR con celular/lector

---

**Generado**: 2026-03-21
**Analista**: GitHub Copilot
