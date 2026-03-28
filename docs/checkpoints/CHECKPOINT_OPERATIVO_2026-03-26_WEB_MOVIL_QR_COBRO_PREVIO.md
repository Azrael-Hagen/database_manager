# Checkpoint Operativo — Web Movil QR y Cobro Previo

Fecha: 2026-03-26
Estado: Previo a cambios

## Objetivo
- Corregir el flujo movil para que el modulo QR sea util en operacion real.
- Permitir escaneo por camara desde la web movil cuando el navegador lo soporte.
- Integrar el escaneo con el cobro rapido para reducir pasos entre lectura y registro de pago.
- Exponer descarga de la app Android desde la misma vista movil.

## Alcance previsto
- Ajuste de `web/m/index.html` para controles QR/camara y descarga APK.
- Ajuste de `web/m/mobile.css` para layout del escaner y tarjetas de cobro rapido.
- Ajuste de `web/m/mobile.js` para:
  - inicializar lector QR web,
  - recibir lecturas nativas/web,
  - precargar pago desde verificacion,
  - consultar resumen real de pago por agente,
  - navegar rapido a la vista de pagos.
- Prueba minima de ruta movil en `tests/test_api.py`.

## Restricciones
- No alterar contratos backend ya validados.
- No mostrar datos no persistidos ni simulados.
- No introducir campo Empresa en flujo movil.

## Riesgos y mitigacion
- Riesgo: la camara web siga bloqueada en HTTP inseguro.
  Mitigacion: mensaje operativo claro y mantenimiento de escaneo nativo Android como fallback.
- Riesgo: QR valide agente pero no deje claro el siguiente paso.
  Mitigacion: autocompletar pago, mostrar resumen real y habilitar salto directo a cobro.
- Riesgo: regresion de la ruta movil.
  Mitigacion: agregar prueba HTTP sobre `/m` con asserts de controles clave.