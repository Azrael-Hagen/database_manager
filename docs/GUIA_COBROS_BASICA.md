# Guia Basica de Cobros (QR y Cobros)

## Objetivo
Estandarizar el flujo operativo para registrar cobros semanales sin inconsistencias entre UI y base de datos.

## Flujo recomendado
1. Entra a la seccion QR y Cobros.
2. En la barra de contexto, busca al agente por nombre, ID o FP.
3. Selecciona el agente correcto y pulsa Cargar Agente.
4. Confirma semana (lunes) y VoIP esperado.
5. Revisa el badge de deuda para validar el estado previo.
6. En Registrar Pago Semanal:
   - Captura monto de abono, o
   - Marca liquidacion total cuando corresponda.
7. Guarda el pago y confirma el resultado en pantalla.
8. Si hay discrepancias, valida en Reporte antes de aplicar ajustes manuales.

## Buenas practicas operativas
- Prioriza buscar por FP cuando este disponible (identificador unico).
- Usa el ID solo cuando tengas certeza del agente.
- Evita ajustes manuales sin evidencia operativa.
- Antes de cierre, valida que el agente y semana coincidan.

## Manejo de excepciones
- Sin resultados en busqueda:
  - Verifica captura de nombre/ID/FP.
  - Prueba otra clave de busqueda (telefono, alias, ID).
- Agente sin VoIP esperado:
  - Revisa datos del agente y lineas asignadas.
- Deuda no esperada:
  - Consulta reporte y movimientos previos antes de ajustar.

## Checklist rapido
- Agente correcto seleccionado.
- Semana correcta.
- Monto validado.
- Confirmacion visual de operacion exitosa.
- Verificacion posterior en reporte cuando aplique.
