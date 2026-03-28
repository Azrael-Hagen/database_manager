# CHECKPOINT TECNICO — 2026-03-28 — QR Layout Densidad Real (PRE)

## Objetivo
- Corregir desperdicio visual real observado en PDF oficio (espacio lateral y entre bloques).
- Incrementar cantidad de etiquetas por pagina sin comprometer lectura de QR.
- Validar exportacion con prueba E2E del endpoint PDF.

## Hallazgo en evidencia visual
- En `oficio`, cada celda usa ancho amplio pero el contenido util (QR+texto) se renderiza en caja angosta centrada.
- Esto deja franjas en blanco significativas que no aportan a la impresion operativa.

## Estrategia
1. Densificar malla por defecto para `oficio` y `sheet` (mas columnas/filas con limites seguros de QR).
2. Eliminar reduccion excesiva de ancho util por etiqueta (contenido ocupa mayor porcentaje de celda).
3. Ajustar presets frontend para que el perfil por defecto use densidad real.
4. Ejecutar E2E de `/api/qr/agentes/export/pdf` y prueba unitaria de layout.

## Riesgos
- QR demasiado pequeno en impresoras de baja calidad.
- Recorte de texto largo en alias.

## Mitigacion
- Definir minimos de tamano QR y conservar truncado de texto.
- Mantener perfil alterno menos denso para contingencia operativa.
