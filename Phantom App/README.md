# Phantom App

Miniapp Android para operar Database Manager desde red local con:
- Descubrimiento de servidor en LAN (hostnames locales + sondeo de subred)
- Seleccion y persistencia de servidor encontrado
- WebView con sesion persistente (cookies + storage del WebView)
- Punto de entrada rapido al panel existente

## Objetivo
Permitir que los operadores usen el sistema desde celular en LAN sin capturar IP manual en cada inicio.

## Estado del mini proyecto
- Scaffold Android (Kotlin)
- Resolucion y ranking de candidatos por nombre/puerto/latencia
- Verificacion basica de salud (`/api/health`)
- Persistencia local cifrada para ultimo servidor y usuario recordado

## Requisitos
- Android Studio Iguana o superior
- Android SDK 34
- Min SDK 26

## Ejecucion
1. Abrir la carpeta `Phantom App` en Android Studio.
2. Sincronizar Gradle.
3. Ejecutar en dispositivo Android dentro de la misma LAN del servidor.
4. Pulsar `Detectar servidor LAN`.
5. La app intentara resolver el mejor endpoint y cargarlo en WebView.

## Seguridad recomendada para produccion
- Habilitar HTTPS y pinning de certificado.
- Implementar refresh token por dispositivo en backend.
- Habilitar cierre remoto de sesion por dispositivo.

## Nota de sesion persistente
La miniapp mantiene cookies y almacenamiento WebView entre reinicios. Esto reduce cierres de sesion por recarga de app, pero la expiracion final depende de la politica de tokens del backend.
