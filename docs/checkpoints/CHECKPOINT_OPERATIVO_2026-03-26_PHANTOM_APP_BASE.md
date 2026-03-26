# CHECKPOINT OPERATIVO - Phantom App Base (2026-03-26)

## Objetivo
Crear mini proyecto Android independiente "Phantom App" para operar el panel web en LAN, detectando servidor disponible y conservando sesion en WebView.

## Cambios realizados
- Se creo estructura Android standalone en carpeta `Phantom App`.
- Se agrego `.gitignore` local para excluir artefactos Android/Gradle del versionado.
- Se agrego modulo `app` con:
  - Activity principal con WebView y controles de descubrir/recargar.
  - Descubrimiento LAN por hostnames locales y sondeo de vecinos en la subred.
  - Validacion de candidatos contra `GET /api/health`.
  - Seleccion de mejor candidato por latencia con preferencia por servidor previo.
  - Persistencia local cifrada (fallback seguro) para URL de servidor y ultimo usuario.
- Se agregaron pruebas unitarias para:
  - Seleccionador de servidor.
  - Planeador de candidatos de subred.

## Archivos principales
- `Phantom App/app/src/main/java/com/phantom/app/MainActivity.kt`
- `Phantom App/app/src/main/java/com/phantom/app/discovery/PhantomDiscoveryManager.kt`
- `Phantom App/app/src/main/java/com/phantom/app/discovery/ServerSelector.kt`
- `Phantom App/app/src/main/java/com/phantom/app/discovery/LanSubnetPlanner.kt`
- `Phantom App/app/src/main/java/com/phantom/app/session/SessionStore.kt`
- `Phantom App/app/src/test/java/com/phantom/app/discovery/ServerSelectorTest.kt`
- `Phantom App/app/src/test/java/com/phantom/app/discovery/LanSubnetPlannerTest.kt`

## Validacion ejecutada
- Validacion de errores del workspace: sin errores reportados para la carpeta `Phantom App`.
- Intento de ejecucion de pruebas con Gradle CLI: no disponible en el entorno actual (`gradle` no instalado y sin wrapper generado).

## Riesgos / pendientes
- Falta generar Gradle Wrapper (`gradlew`) para compilacion reproducible sin dependencia de Gradle global.
- Descubrimiento actual no usa NSD/mDNS nativo; usa estrategia robusta por hostnames conocidos + sondeo de subred.
- En produccion se recomienda HTTPS y pinning de certificado para reducir riesgo MITM en LAN.
