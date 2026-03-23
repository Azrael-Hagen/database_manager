# Checkpoint Operativo Launcher + Guia Altas (2026-03-22)

## Objetivo del bloque
- Permitir arranque simplificado para usuarios no tecnicos en la misma maquina.
- Abrir automaticamente la UI al iniciar servidor.
- Habilitar creacion de accesos directos en escritorio (Iniciar/Detener).
- Incorporar visita guiada para usuarios de insercion (rol capture/admin) en Altas de Agentes.

## Cambios implementados
- Launcher simplificado:
  - `start.bat` en raiz como script oficial de arranque del servidor.
  - `start_easy.bat` en raiz como wrapper UX de un clic que abre la UI y delega al script oficial.
- Accesos directos de escritorio:
  - `scripts/create-desktop-shortcuts.ps1` crea:
    - `Database Manager - Iniciar.lnk`
    - `Database Manager - Detener.lnk`
  - `create_desktop_shortcuts.bat` como wrapper simple para ejecutar el script anterior.
- Guia de Altas:
  - Botones UI en `Altas de Agentes`: `Visita Guiada de Altas` y `Reiniciar Guía`.
  - Overlay con pasos secuenciales y resaltado de campos clave para crear agente y asignar linea.
  - Disparo automatico una sola vez por usuario (localStorage) para roles capture/admin.

## Validacion ejecutada
- Errores de editor: sin errores en archivos modificados.
- Script de accesos directos: ejecutado correctamente, accesos creados en escritorio.
- Script de inicio facil:
  - probado localmente; inicia en ventana separada y abre URL automaticamente cuando detecta puerto.
  - timeout de espera incrementado para primer arranque lento.

## Notas operativas
- Este bloque no modifica permisos backend: usuarios capture ya pueden hacer altas y asignaciones dentro de su seccion.
- Se mantiene separado del flujo admin (QR/pagos/cambios/bajas) por reglas de rol ya existentes.
