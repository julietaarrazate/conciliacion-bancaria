# Mapa del sistema — Cuadra

> Índice navegable "dónde está cada cosa". Una tabla por módulo funcional que
> mapea **Módulo → Router(s) → Service(s) → Modelo(s) → Página(s) frontend**.
> Para la visión de capas y topología ver [ARCHITECTURE.md](./ARCHITECTURE.md);
> para entidades y relaciones ver [DOMAIN_MODEL.md](./DOMAIN_MODEL.md).

Rutas de referencia:
- Routers: `backend/app/routers/`
- Services: `backend/app/services/`
- Modelos: `backend/app/models/`
- Páginas: `frontend/src/pages/`

Todos los routers se montan en `backend/app/main.py` (`app.include_router(...)`).

---

## Índice de prefixes de routers

| Router | Prefix | Sub-routers incluidos |
|---|---|---|
| `auth.py` | `/auth` | — |
| `google_auth.py` | `/auth` | — |
| `me.py` | *(sin prefix)* | — |
| `extractos.py` | `/extractos` | + `conciliaciones_router` (`/conciliaciones`) |
| `planillas.py` | `/planillas` | — |
| `historial.py` | `/historial` | — |
| `auditoria.py` | `/auditoria` | — |
| `admin.py` | `/admin` | — |
| `clientes_dir.py` | `/clientes` | — |
| `organizaciones.py` | `/admin/organizaciones` | — |
| `liquidaciones.py` | `/liquidaciones` | — |
| `caja.py` | `/caja` | — |
| `contabilidad.py` | `/contabilidad` | + `ctb_plan`, `ctb_libro`, `ctb_clientes`, `ctb_ctas_corrientes` (+ `ctb_common` helpers) |
| `cheques.py` | `/cheques` | + `cheques_reportes`, `cheques_crud`, `cheques_acreditacion` (+ `cheques_common`) |
| `pagos.py` | `/pagos` | — |
| `papelera.py` | `/admin/papelera` | — |
| `backup_admin.py` | `/admin/backup` | — |
| `analisis.py` | `/analisis` | — |
| `search.py` | `/search` | — |
| `public_router.py` | `/public` | — |
| `push_router.py` | `/push` | — |
| `agente.py` | `/agente` | — |
| `tarjetas.py` | `/tarjetas` | — |
| `iva.py` | `/iva` | — |
| `monotributo.py` | `/monotributo` | — |
| `iibb.py` | `/iibb` | — |
| `sueldos.py` | `/sueldos` | — |
| `arca.py` | `/arca` | — |

> Las rutas públicas sin auth (`/p/:token`, `/privacidad`, `/terminos`) son
> servidas por `public_router.py` (`/public`) + páginas frontend dedicadas.

---

## 1. Conciliación bancaria (núcleo)

| Aspecto | Ubicación |
|---|---|
| Routers | `extractos.py` (`/extractos`) · `conciliaciones_router` (`/conciliaciones`) · `planillas.py` (`/planillas`) · `historial.py` (`/historial`) |
| Services | `conciliacion.py` (motor de scoring) · `excel_parser.py` (detección de banco + parseo) · `extracto_merger.py` (merge de UM sin duplicar) · `aprendizaje.py` (IA Nivel 2) · `excel_export.py` · `pdf_export.py` |
| Modelos | `ExtractoBancario`, `MovimientoBanco` (`extracto.py`) · `Planilla`, `PlanillaRow` (`planilla.py`) · `Cliente` (`cliente.py`) · `PatronAprendido` (`patron_aprendido.py`) |
| Páginas | `Dashboard.tsx` · `Bulk.tsx` (carga masiva) · `ExtractosArchivo.tsx` · `Movimientos.tsx` · `Conciliaciones.tsx` · `Historial.tsx` · `Revision.tsx` |

## 2. Clientes (directorio)

| Aspecto | Ubicación |
|---|---|
| Router | `clientes_dir.py` (`/clientes`) |
| Modelo | `Cliente` (`cliente.py`) — incluye `cuenta_contable_id` (cuenta corriente 2-1-2-X) y porcentajes de comisión |
| Página | `Clientes.tsx` |

## 3. Cheques

| Aspecto | Ubicación |
|---|---|
| Routers | `cheques.py` (`/cheques`) agregador → `cheques_crud.py` (alta/edición/OCR) · `cheques_acreditacion.py` (depósito/acreditación/rechazo) · `cheques_reportes.py` (reportes Excel) · `cheques_common.py` (helpers) |
| Services | OCR vía Gemini (en `cheques_crud.py`) · `motor_contable.registrar_cheque` |
| Modelos | `Cheque` (`cheque.py`) · `Portador` (`portador.py`) |
| Página | `Cheques.tsx` |

## 4. Pagos y Gastos (egresos)

| Aspecto | Ubicación |
|---|---|
| Router | `pagos.py` (`/pagos`) |
| Services | `storage.py` (foto del comprobante a R2/base64) · OCR Gemini · `motor_contable.registrar_egreso` |
| Modelos | `Egreso`, `CategoriaEgreso` (`egreso.py`) — `tipo` ∈ {proveedor, gasto, pago_cliente}, `forma_pago` ∈ {banco, efectivo} |
| Página | `Pagos.tsx` |

## 5. Caja (arqueo de efectivo)

| Aspecto | Ubicación |
|---|---|
| Router | `caja.py` (`/caja`) |
| Service | `motor_contable.registrar_ingreso_efectivo` |
| Modelos | `ArqueoDiario` (`caja.py`) — vinculado a `Egreso.arqueo_id` para salidas en efectivo |
| Página | `Caja.tsx` |

## 6. Liquidaciones (comisiones por cliente)

| Aspecto | Ubicación |
|---|---|
| Router | `liquidaciones.py` (`/liquidaciones`) |
| Services | `cierre_periodo.py` · `motor_contable.registrar_liquidacion_aprobacion` |
| Modelos | `Liquidacion`, `LiquidacionDetalle`, `CierrePeriodo` (`liquidacion.py`) |
| Página | `Liquidaciones.tsx` |

## 7. Contabilidad (partida doble)

| Aspecto | Ubicación |
|---|---|
| Routers | `contabilidad.py` (`/contabilidad`) agregador → `ctb_plan.py` (plan de cuentas) · `ctb_libro.py` (libro diario / mayor) · `ctb_clientes.py` · `ctb_ctas_corrientes.py` (cuentas corrientes) · `ctb_common.py` (helpers) |
| Services | `motor_contable.py` (genera asientos) · `seed_contable.py` (siembra plan + reglas) · `export_contable.py` (export) · `reportes_service.py` |
| Modelos | `PlanCuenta`, `ReglaContable`, `Asiento`, `AsientoDetalle` (`contabilidad.py`) |
| Páginas | `Contabilidad.tsx` · `EstadoCuenta.tsx` · `Resumen.tsx` |

> Detalle del motor de partida doble en [ACCOUNTING_ENGINE.md](./ACCOUNTING_ENGINE.md).

## 8. Impuestos — IVA (Proyección y DDJJ)

| Aspecto | Ubicación |
|---|---|
| Router | `iva.py` (`/iva`) |
| Service | `iva_service.py` |
| Modelos | `ProyeccionIva` (`proyeccion_iva.py`) · `PlanCuenta.tasa_iva` |
| Página | `Iva.tsx` |

## 9. Impuestos — Monotributo (Control Semestral)

| Aspecto | Ubicación |
|---|---|
| Router | `monotributo.py` (`/monotributo`) |
| Service | `monotributo_service.py` (incluye `seed_monotributo_categorias` y `_LIMITES_VIGENTES`) |
| Modelos | `CategoriaMonotributo`, `MonotributoConfig`, `ControlMonotributo` (`monotributo.py`) |
| Página | `Monotributo.tsx` |

## 10. Impuestos — Ingresos Brutos (IIBB) y Convenio Multilateral

| Aspecto | Ubicación |
|---|---|
| Router | `iibb.py` (`/iibb`) |
| Service | `iibb_service.py` (incluye `seed_iibb_jurisdiccion`) |
| Modelos | `JurisdiccionIIBB`, `IIBBConfig`, `ProyeccionIIBB` (`iibb.py`) |
| Página | `IngresosBrutos.tsx` |

## 11. Impuestos — Sueldos y F931

| Aspecto | Ubicación |
|---|---|
| Router | `sueldos.py` (`/sueldos`) |
| Services | `sueldos_service.py` (incluye `seed_config_sueldos`) · `sicoss_export.py` (export SICOSS / F931) · `motor_contable.registrar_liquidacion_sueldos` |
| Modelos | `ConvenioColectivo`, `CategoriaConvenio`, `Empleado`, `ConfigSueldos`, `EscalaGanancias`, `LiquidacionSueldoPeriodo`, `DetalleLiquidacionEmpleado` (`sueldos.py`) |
| Página | `Sueldos.tsx` |

## 12. Tarjetas (liquidaciones Visa/Mastercard/Amex)

| Aspecto | Ubicación |
|---|---|
| Router | `tarjetas.py` (`/tarjetas`) |
| Services | `tarjeta_parser.py` · `motor_contable.registrar_liquidacion_tarjeta` |
| Modelo | `LiquidacionTarjeta` (`liquidacion_tarjeta.py`) |
| Página | `Tarjetas.tsx` |

## 13. ARCA (facturación electrónica WSFEv1) — opt-in, desactivado

| Aspecto | Ubicación |
|---|---|
| Router | `arca.py` (`/arca`) |
| Services | `arca_crypto.py` (cifrado Fernet del certificado) · `arca_wsaa.py` (autenticación WSAA) · `arca_wsfe.py` (emisión WSFEv1 / CAE) · `motor_contable.registrar_factura_arca` |
| Modelos | `ArcaConfig`, `ComprobanteArca` (`arca.py`) |
| Página | `Arca.tsx` |

## 14. Asistente IA (Gemini)

| Aspecto | Ubicación |
|---|---|
| Router | `agente.py` (`/agente`) |
| Uso de IA | También OCR en `cheques_crud.py` y `pagos.py`; transcripción de voz |
| Páginas | integrado en la UI (asistente / proactividad). Ver [../ai/AI_GUIDE.md](../ai/AI_GUIDE.md) |

## 15. Análisis y reportes

| Aspecto | Ubicación |
|---|---|
| Router | `analisis.py` (`/analisis`) |
| Service | `reportes_service.py` |
| Páginas | `FlujoCaja.tsx` · `Resumen.tsx` · `Actividad.tsx` |

## 16. Auditoría

| Aspecto | Ubicación |
|---|---|
| Router | `auditoria.py` (`/auditoria`) |
| Service | `auditoria.py` → `registrar_log(...)` |
| Modelo | `AuditoriaLog` (`auditoria.py`) |
| Página | `Auditoria.tsx` |

> Qué acciones disparan logs de auditoría: ver [EVENTS.md](./EVENTS.md) §auditoría.

## 17. Administración, usuarios y organizaciones

| Aspecto | Ubicación |
|---|---|
| Routers | `admin.py` (`/admin`) · `organizaciones.py` (`/admin/organizaciones`) · `papelera.py` (`/admin/papelera`, restore/purge soft delete) · `backup_admin.py` (`/admin/backup`) |
| Services | `backup_service.py` · `backup_scheduler.py` |
| Modelos | `User` (`user.py`) · `Organizacion` (`organizacion.py`) |
| Páginas | `Usuarios.tsx` · `Organizaciones.tsx` · `Papelera.tsx` · `Perfil.tsx` |

## 18. Auth, sesión y seguridad

| Aspecto | Ubicación |
|---|---|
| Routers | `auth.py` (`/auth`, login/JWT/2FA/reset) · `google_auth.py` (`/auth`, login Google) · `me.py` (perfil propio) · `push_router.py` (`/push`, suscripciones) |
| Services | `auth.py` (hash/JWT) · `password_reset.py` · `email_sender.py` · `push_service.py` |
| Middleware | `backend/app/middleware/auth.py` (`get_current_user`, `require_superadmin`, `require_permission`) |
| Modelos | `RevokedToken`, `LoginApproval`, `TwofaCode`, `PasswordResetToken`, `PushSubscription` |
| Páginas | `Login.tsx` · `RecuperarPassword.tsx` · `RestablecerPassword.tsx` · `Aprobaciones.tsx` |

> Detalle de roles, permisos y flujo de aprobación de login en
> [../security/SECURITY_MODEL.md](../security/SECURITY_MODEL.md).

## 19. Páginas públicas / compartir

| Aspecto | Ubicación |
|---|---|
| Router | `public_router.py` (`/public`) · `search.py` (`/search`, ⌘K) |
| Páginas | `PaginaPublica.tsx` (`/p/:token`) · `Compartir.tsx` · `Privacidad.tsx` · `Terminos.tsx` · `Landing.tsx` |

---

## Servicios transversales (no atados a un módulo)

| Service | Rol |
|---|---|
| `tz.py` | Timezone ART (`hoy_art`, etc.) |
| `decimal_utils.py` | Helpers de `Decimal` para montos |
| `storage.py` | Foto a R2 (S3) o base64 fallback |
| `email_sender.py` | Envío de email centralizado (Resend) |
| `backup_service.py` / `backup_scheduler.py` | Backup completo + schedulers |
| `push_service.py` | Web Push (VAPID) |

---

## Pendiente de revisar

- `me.py` se monta **sin `prefix`**: sus rutas cuelgan de la raíz. Verificar el
  path real de cada endpoint (probablemente `/me`) abriendo el archivo.
- `auth.py` y `google_auth.py` comparten el prefix `/auth`. Confirmar que no haya
  colisión de paths entre ambos.
- El asistente IA (`agente.py`) y los detalles de OCR/voz dependen de
  [../ai/AI_GUIDE.md](../ai/AI_GUIDE.md) (puede no estar escrito todavía).
- La página `EstadoCuenta.tsx` se ubicó tentativamente bajo Contabilidad/Cuentas
  corrientes; confirmar a qué endpoint consume.
