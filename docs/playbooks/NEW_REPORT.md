# Playbook — Agregar un reporte / export

> Cómo sumar una exportación nueva (Excel o PDF) siguiendo los patrones del repo.
> Las convenciones de la API (auth, org_id, errores) están en [API_RULES](../api/API_RULES.md).

Fuentes: `backend/app/services/excel_export.py`, `export_contable.py`, `pdf_export.py`, y routers
que exportan (ej. `cheques_reportes.py`, `historial.py`, `analisis.py`).

## Excel (openpyxl)

Helpers reutilizables en `services/excel_export.py`: `_hdr` (encabezados), `_autosize`,
`_mes_a_int`. Funciones de export existentes como plantilla: `export_movimientos`,
`export_planilla_conciliada`, `export_extracto_contador` (formato banco para el contador),
`export_historial_planillas`, `export_liquidacion_excel`.

Para formatos contables externos (Tango, Holistor, etc.) ver `services/export_contable.py`.

## PDF (reportlab)

`services/pdf_export.py` trae un sistema de componentes: `_header_band`, `_kpi_cards`, `_tabla`,
`_totales_box`, `_section`, `_page_decorator`. Plantilla: `estado_cuenta_pdf(...)`. Reusalos para
mantener identidad visual consistente.

## Cómo se devuelve

El export se sirve como `StreamingResponse` con el `media_type` correcto y `Content-Disposition`
(filename). Patrón en `routers/historial.py` (`/planillas/export`) y `cheques_reportes.py`.

## Reglas

1. **Los exports traen TODO**: no pagines de menos un export (a diferencia de los listados). Si hay
   muchos registros, optimizá con eager loading (`selectinload`/`joinedload`) para evitar N+1 — ver
   `cheques_reportes.py` y `historial.py` y [DATABASE_RULES](../database/DATABASE_RULES.md).
2. **Montos**: formateá desde `Decimal` (es-AR), nunca pierdas precisión por `float`.
3. **Permiso + org**: el endpoint de export respeta permiso y `org_id` igual que cualquier otro
   (ver [API_RULES](../api/API_RULES.md), [SECURITY_MODEL](../security/SECURITY_MODEL.md)).
4. **Auditoría**: si el export es sensible, registralo (`registrar_log`) — ver
   [EVENTS](../architecture/EVENTS.md).

## Checklist

- [ ] Función de armado en `excel_export.py` / `pdf_export.py` reusando helpers
- [ ] Endpoint con `StreamingResponse` + filename + media_type
- [ ] Permiso y `org_id` aplicados
- [ ] Eager loading si itera muchos registros
- [ ] Test del endpoint (status 200 + content-type)

## Pendiente de revisar

- Confirmar la lista vigente de formatos contables soportados en `export_contable.py` al editar.
