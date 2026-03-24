# Guía: Búsqueda de Agentes en QR y Cobros

## Nueva Funcionalidad
La sección **QR y Cobros** ahora incluye búsqueda inteligente de agentes por **nombre** (además de por ID).

---

## Cómo Usar

### 1. Búsqueda por Nombre
1. Abre la sección **QR y Cobros**
2. En la barra de contexto superior, haz clic en el campo **"Buscar Agente"**
3. Escribe el **nombre del agente** (ej: "Juan", "María")
4. El dropdown automáticamente muestra hasta 8 resultados coincidentes
5. Cada resultado muestra:
   - **Nombre** (en azul, destacado)
   - **Teléfono** (si existe)
   - **Alias** (sobre nombre) (si existe)
   - **ID** de referencia
6. Haz clic en el resultado → se rellena automáticamente

### 2. Búsqueda por ID (Directa)
1. Escribe un **número** en el campo "Buscar Agente"
2. Inmediatamente aparece la opción "ID: {número}" en el dropdown
3. Haz clic → se carga el agente

### 3. Cargar Agente
Después de seleccionar (por nombre o ID):
1. Haz clic en el botón **"🔍 Cargar Agente"**
2. El sistema verifica el agente y sincroniza todos los formularios
3. El **badge** de estado se actualiza automáticamente:
   - ✓ **Al corriente** (verde) — sin deuda
   - ⚠ **Debe $X** (rojo) — hay deuda acumulada
   - **Sin deuda** (azul) — sin registros

---

## Detalles Técnicos

### Performance
- **Debounce**: Espera 250ms después de dejar de escribir antes de hacer búsqueda
- **Resultados**: Máximo 8 agentes mostrados
- **Sincronización**: UI↔BD estricta (solo agentes que existan en BD)

### Campos en Dropdown
| Campo | Fuente | Descripción |
|-------|--------|-------------|
| Nombre | `DatoImportado.nombre` | Nombre del agente |
| Teléfono | `DatoImportado.telefono` | Número de contacto |
| Alias | `DatoImportado.datos_adicionales.alias` | Alias/apodo |
| ID | `DatoImportado.id` | ID único del agente |

### Búsqueda (Backend)
Endpoint: `GET /api/qr/agentes?search={query}`
- Case-insensitive
- Busca en: nombre, teléfono, empresa, datos_adicionales
- Devuelve: sorted by alias → nombre → id

---

## Ejemplo de Uso Completo

```
1. Usuario tipo "Mar" en "Buscar Agente"
   ↓
2. Dropdown muestra:
   - María García (📞 555-0123, 🏷 MG) ID: 42
   - Marco Pérez (📞 555-0456, 🏷 MP) ID: 73
   ↓
3. Click en "María García" → campo se rellena con "María García"
   ID oculto = 42
   ↓
4. Click "🔍 Cargar Agente"
   ↓
5. Sistema verifica:
   - GET /api/qr/verificar/42
   - Retorna estado, deuda, líneas, etc.
   ↓
6. Badge se actualiza:
   - ⚠ Debe $850 (si hay deuda)
   ↓
7. Todos los formularios se sincronizan:
   - Estado del Agente (tab Pago)
   - Reporte Semanal (tab Reporte)
   - Pagos y Deuda (disponibles)
```

---

## Compatibilidad
- ✅ Entrada manual de ID (sigue funcionando)
- ✅ Búsqueda por nombre (nuevo)
- ✅ Búsqueda por número (new, instant)
- ✅ Validación BD (solo agentes existentes)

---

## Troubleshooting

**P: El dropdown no muestra resultados**
- A: Verifica que el nombre esté escrito correctamente (búsqueda case-insensitive en backend)

**P: Quiero buscar por teléfono**
- A: Actualmente la búsqueda está optimizada para nombre. El teléfono se muestra en resultados si deseas copiar manualmente.

**P: ¿Cómo busco por alias?**
- A: Por ahora, busca por nombre. El alias se muestra en resultados para referencia.

---

**Implementación finalizada**: 2026-03-24
