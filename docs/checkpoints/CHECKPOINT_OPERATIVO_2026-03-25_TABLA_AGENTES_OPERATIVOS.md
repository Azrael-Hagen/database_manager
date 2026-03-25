## Checkpoint Técnico 2026-03-25

### Cambio solicitado

- La tabla operativa principal fue renombrada manualmente en BD de `datos_importados` a `agentes_operativos`.
- El backend actual sigue apuntando a `datos_importados` en ORM, SQL crudo, vistas y pruebas.

### Riesgo detectado

- Si el servidor inicia con el modelo aún apuntando a `datos_importados`, puede recrear una tabla vacía con ese nombre y leer una fuente incorrecta.
- Hay referencias transversales en QR, dashboard, mantenimiento de BD, exportación inteligente y utilidades de arranque.

### Estrategia del bloque

- Convertir `agentes_operativos` en nombre canónico del backend productivo.
- Ajustar ORM, foreign keys, SQL crudo productivo y pruebas afectadas.
- Mantener continuidad funcional en UI y API sin cambiar el flujo operativo validado.