# Procesos masivos (v3.36)

Lo que hoy se hace organización por organización, para todas las que ve el usuario de una vez.
Idea tomada del benchmark (Onvio: procesos automáticos multi-empresa). Código:
`services/procesos_masivos.py`, `routers/procesos_masivos.py`, `pages/ProcesosMasivos.tsx`.
Organizaciones alcanzadas: `services/acceso_orgs.orgs_accesibles` (superadmin: todas las
activas; resto: la propia + `allowed_org_ids`) — la misma regla que Vencimientos.

## 1. Calcular para todas

`POST /procesos-masivos/calcular {accion, periodo, org_ids?}` (`manage_finance`). Reusa el
servicio de cada módulo; no duplica cálculos.

| Acción | Servicio | Período | Aplica si |
|---|---|---|---|
| `iva_liquidacion` | `iva_liquidacion_service.calcular_liquidacion` | AAAA-MM | la org usa IVA (`vencimientos.obligaciones_org`) |
| `iva_proyeccion` | `iva_service.guardar_o_actualizar_proyeccion` | AAAA-MM | ídem |
| `iibb_proyeccion` | `iibb_service.guardar_o_actualizar_proyeccion` | AAAA-MM | `IIBBConfig.activo` |
| `monotributo_control` | `monotributo_service.guardar_o_actualizar_control` | AAAA-S1/S2 | `MonotributoConfig.activo` |
| `sueldos_liquidacion` | `sueldos_service.guardar_o_actualizar_liquidacion` | AAAA-MM | `ConfigSueldos.activo` |

Resultado por org: `calculado` · `ya_presentado` (presentado/revisado: no se toca) · `omitido`
(sin el módulo, con motivo) · `error` (mensaje del módulo). **Cada org se commitea sola**: un
error hace rollback de esa org y sigue con la próxima. Auditoría `CALCULAR_MASIVO` por org calculada.

**Liquidación de IVA — lo cargado a mano se conserva.** `calcular_liquidacion` pone en 0 las
retenciones y percepciones que no recibe (hoy se cargan a mano), así que el proceso masivo le
pasa las que ya tenía la liquidación. Los saldos anteriores se heredan del mes previo si existe
su liquidación; si no existe, se conservan los cargados (si no, quedarían en 0).

## 2. Mis Comprobantes de varios clientes

- `POST /procesos-masivos/mis-comprobantes/comparar?direccion=&periodo=` (archivos, hasta 50):
  cada Excel se asigna a su org por el **CUIT del título** ("Mis Comprobantes Recibidos - CUIT
  …", `cuit_del_titulo`) contra el CUIT de cada org accesible (`cuit_organizacion`). Sin CUIT
  en el título, sin org con ese CUIT o con **más de una** org con ese CUIT → error en ese archivo
  (no se adivina). Devuelve por archivo los conteos de `comparar` (§5.5 de BUSINESS_RULES).
  No carga nada.
- `POST /procesos-masivos/mis-comprobantes/importar` (mismos archivos): importa lo que falta de
  cada uno en su org con `comparar_mis_comprobantes.importar_filas` (la misma función que usa la
  importación de IVA). Un lote por org: se deshace con `DELETE /iva/comprobantes/lote/{lote}?org_id=`.
- Para revisar factura por factura (importes distintos, lo que ARCA no tiene) se usa la
  comparación individual de IVA de esa org.

## Pendiente de revisar

- El endpoint individual `POST /iva/liquidacion/calcular` también pone en 0 retenciones y
  percepciones si no las recibe. Revisado (oct 2026): `pages/Iva.tsx` precarga las guardadas y
  las manda, así que solo quedan en 0 si se borra el campo.
- Los procesos corren dentro del request (sin cola): con muchas orgs puede tardar; si crece,
  pasarlo a tarea en segundo plano con progreso.
