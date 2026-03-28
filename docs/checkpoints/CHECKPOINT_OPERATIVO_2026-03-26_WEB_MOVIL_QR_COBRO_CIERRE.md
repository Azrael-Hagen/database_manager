# Checkpoint Operativo — Web Movil QR y Cobro Cierre

Fecha: 2026-03-26
Estado: Completado

## Objetivo cumplido
- La vista movil ahora expone un flujo operativo real para cobrar desde QR.
- Se agrego acceso visible a descarga del APK desde la interfaz movil.
- Se mantuvo compatibilidad con backend existente y sin alterar contratos validados.

## Cambios implementados
- `web/m/index.html`
  - Se agrego tarjeta de descarga de app Android en dashboard.
  - Se agregaron controles de camara web en seccion QR:
    - selector de camara
    - boton iniciar/detener camara
    - actualizacion de camaras
    - contenedor de escaner
  - Se agrego accion directa `Cobrar este agente` tras verificacion QR.
  - Se agrego tarjeta de resumen de pago en vista de Pagos.
  - Se incluyo libreria `html5-qrcode` para escaneo web.
- `web/m/mobile.css`
  - Se incorporo estilo para selector, contenedor de escaner y botones enlace.
  - Se ajustaron componentes para lectura/cobro rapido en pantalla movil.
- `web/m/mobile.js`
  - Se incorporo flujo de camara web con `Html5Qrcode`.
  - Se conserva fallback de escaneo nativo Android si existe puente `PhantomAndroid`.
  - Al leer un QR se realiza:
    - verificacion real contra backend
    - precarga de agente y monto en pagos
    - consulta de resumen real de pagos por agente
    - opcion de salto directo a cobro
  - Se agrego carga de disponibilidad del APK desde `/api/download/phantom-app/info`.
- `tests/test_api.py`
  - Se agrego prueba de ruta `/m` para validar presencia de controles clave de QR y descarga.

## Validacion realizada
- Sin errores estaticos en:
  - `web/m/index.html`
  - `web/m/mobile.css`
  - `web/m/mobile.js`
  - `tests/test_api.py`
- Prueba ejecutada correctamente:
  - `pytest ../tests/test_api.py -k mobile_route_exposes_qr_and_download_controls`
  - Resultado: `1 passed`

## Consideraciones operativas
- El escaneo por camara web sigue sujeto a restricciones del navegador: HTTPS o localhost para acceso a `mediaDevices`.
- En Android, el boton de escaneo nativo sigue siendo la opcion mas robusta cuando la app esta instalada.
- La UI movil ahora sirve tanto para flujo web puro como para flujo hibrido con app.

## Siguiente validacion recomendada
- Prueba manual E2E en telefono real:
  - abrir `/m`
  - iniciar camara web
  - leer QR
  - revisar resumen de deuda/pago
  - registrar abono o liquidacion
  - validar persistencia inmediata en backend
