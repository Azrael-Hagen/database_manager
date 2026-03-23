# CHECKPOINT OPERATIVO 2026-03-22 - UI DEPURADA QR + AUTOSTART WINDOWS

## Objetivo
Eliminar redundancias en UI de escaneo QR y dejar clara la operacion de inicio automatico de Windows.

## Cambios principales
- Escaneo QR queda centralizado en una sola seccion: `Escaneo QR`.
- Se elimino bloque duplicado de escaneo en la seccion `QR` (pagos/reportes).
- Se agrego tarjeta en Dashboard para gestionar autostart Windows con comandos guiados:
  - `manage_autostart.bat install logon`
  - `manage_autostart.bat install startup`
  - `manage_autostart.bat remove`
  - `manage_autostart.bat status`
- Se optimizo frontend con helper de copiado reutilizable para evitar duplicidad de logica.

## Archivos impactados
- `web/index.html`
- `web/js/main.js`
- `web/css/style.css`

## Validacion esperada
- Solo existe una zona para escaneo QR en UI.
- Botones de autostart copian comandos correctamente.
- Seccion QR se mantiene enfocada en verificacion/pagos/reportes.
