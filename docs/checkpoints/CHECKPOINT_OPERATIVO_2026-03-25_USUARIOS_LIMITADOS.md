## Checkpoint Técnico 2026-03-25

### Alcance previo al cambio

- El rol `viewer` existe en backend y frontend, pero actualmente puede ver secciones operativas (`dashboard`, `datos`, `alertas`) en la UI.
- El registro público (`/api/auth/registrar`) crea usuarios `viewer` normales, no temporales.
- La gestión de usuarios temporales existe en backend (`/api/usuarios/temporales`, renovaciones, solicitudes), pero depende de creación por administrador.
- La UI de usuarios tiene un bug funcional: `crearUsuarioTemporal()` usa `tempUsername`, pero el formulario HTML no tiene ese campo.
- La edición de usuario usa `rol` y `es_admin`, pero no hay cobertura de prueba suficiente para asegurar el cambio de rol end-to-end.
- No existe un portal de autoservicio limitado para que un usuario temporal/consulta vea solo su propio nombre y adeudo.

### Riesgos identificados

- Exposición indebida de datos operativos a usuarios `viewer`.
- Alta pública creando cuentas normales en vez de temporales cuando se requiere acceso restringido.
- Falta de vínculo autoservicio entre `usuarios` y `datos_importados` para consultar adeudo propio.
- Solicitudes de permisos temporales limitadas a `capture/admin`, no al caso solicitado de promoción a usuario normal limitado.

### Objetivo del siguiente bloque

- Convertir `viewer` en experiencia limitada de autoservicio.
- Habilitar registro temporal desde login.
- Permitir solicitud de promoción a usuario normal limitado.
- Corregir funcionalidad real de roles en gestión de usuarios.
- Validar con pruebas backend y frontend estático.