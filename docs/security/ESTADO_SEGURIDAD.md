# Estado de seguridad — registro vivo

Qué se revisó, qué se corrigió (con su PR) y qué falta. **Se actualiza al cerrar cada sesión
que toque seguridad, dependencias o infraestructura**; el modelo técnico (cómo funciona cada
control) vive en [`SECURITY_MODEL.md`](SECURITY_MODEL.md).

Última actualización: **30/oct/2026**.

---

## 1. Revisión de seguridad oct/2026 (primera revisión completa)

Alcance: backend, frontend, base, historial de git, dependencias. Método: lectura de los 40+
routers, `gitleaks` sobre todo el historial, `npm audit` / `pip-audit`, consultas de solo lectura
en producción para verificar que no hubo aprovechamiento.

| Tema | Estado | Dónde |
|---|---|---|
| Aislamiento entre organizaciones (endpoints que aceptaban IDs de otra org) | ✅ Corregido, sin rastros de uso en prod | PR #254 · `tests/test_seguridad_multitenant.py` |
| Rate limiting por IP real (detrás del proxy de Render) + cupo diario de IA por organización en la base | ✅ | PR #258 · `tests/test_limites.py` |
| Usuario demo activo en Org A | ✅ Desactivado en prod (auditoría `DESACTIVAR_SEGURIDAD`) | — |
| Dependencias del backend con versión y hash fijos + pip 26.2.2 + Python 3.11.17 | ✅ | PR #259 |
| python-jose → PyJWT, dependencias al día, `npm audit fix` | ✅ | PR #261 |
| Sesiones: cambio/reset de contraseña cierra sesiones; email en `/me` pide contraseña | ✅ | PR #261 · `tests/test_seguridad_auth.py` |
| Login: usuario inactivo no entra, Google valida mail verificado y pasa por 2FA, 2FA con topes y falla cerrado, PBKDF2 600k | ✅ | PR #261 |
| Revisor de solo lectura en toda ruta que escribe + meta-test que lo vigila | ✅ | PR #261 · `tests/test_seguridad_permisos.py` |
| Auditoría separada por organización | ✅ | PR #261 (migración 035) |
| Excel/CSV sin fórmulas inyectadas, subidas con tope y anti zip-bomb, PDFs escapados, sin `document.write` | ✅ | PR #261 · `tests/test_seguridad_entradas.py` |
| Claves que estuvieron en el historial (Render, Vercel, GitHub) | ✅ Verificado: ya no existen en las cuentas | — |
| Contraseña del superadmin: `SUPERADMIN_PASSWORD` solo al crearla; un cambio desde `/perfil` dura. Emergencia: `SUPERADMIN_PASSWORD_RESET=1` (pisa una vez, WARNING en el log) | ✅ | PR #266 (lote 4) · `tests/test_seguridad_lote4.py` |
| Fusionar clientes (borra el origen) pide `delete_records` además de `reconcile`: solo admin y superadmin; operador y contador lo pierden a propósito | ✅ | PR #266 (lote 4) |
| `POST /push/subscribe` reasigna al usuario actual un endpoint que era de otro usuario | ✅ | PR #266 (lote 4) |
| `GET /caja/arqueo/hoy` sin escritura: devuelve el borrador; lo crean el `PUT` o un pago en efectivo (los dos con el saldo arrastrado) | ✅ | PR #266 (lote 4) |
| Backup diario y reset operativo filtran la auditoría por la org del log (mismo criterio que `/auditoria`) | ✅ | PR #266 (lote 4) |
| Frontend oculta al revisor las acciones que el backend le rechaza (extractos, movimientos, planillas, clientes, estado de cuenta) | ✅ | PR #266 (lote 4) · `Movimientos.test.tsx` |
| `react-router-dom` 6 (open redirect con `\`) → 7.18.5; `npm audit --omit=dev` sin avisos | ✅ | PR #266 (lote 4) |

## 2. Pendiente

### Decisiones abiertas (de la operadora)
- **Fusionar clientes**: quedó en `delete_records` (lote 4), así que operador y contador ya no
  fusionan. Si la operadora prefiere que el contador sí pueda, habría que darle un permiso
  propio (no `delete_records`, que le abriría todos los borrados).
- **Exports TXT Tango/Holistor** sin sanear fórmulas (formato fijo; el apóstrofo se vería en la
  descripción importada).
- **Neon**: limitar conexiones por IP (si el plan lo permite) y habilitar `pg_stat_statements`.

### Técnico (bajo riesgo, para un próximo lote)
- CORS: la regex de previews de Vercel acepta un hostname que otra cuenta podría reproducir
  (sin credenciales, riesgo bajo). Cierre total: listar previews en `EXTRA_CORS_ORIGINS`.
- El auditor tiene `manage_finance` en el backend (cheques, caja) pero las rutas `/cheques`,
  `/caja` y `/pagos` del frontend piden `reconcile`, así que no las ve. Decidir si se le abren o
  si se le saca el permiso en el backend.

### Tareas de la operadora
- **GitGuardian**: marcar el incidente 38908774 (PR #261, `Perfil.tsx`) como falso positivo.
- **1/nov/2026**: volver privados los repos públicos.

## 3. Mantenimiento periódico

| Qué | Cada cuánto | Cómo |
|---|---|---|
| Python en Render | Cuando python.org publique una 3.11.x nueva | Ver python.org/ftp/python; actualizar la env var `PYTHON_VERSION` en Render (versión exacta) y `backend/runtime.txt`. Hoy: 3.11.17 (1/oct/2026, última de la rama 3.11) |
| Dependencias del backend | Mensual o ante un aviso | `pip-audit -r backend/requirements.txt`; editar `requirements.in` y regenerar con `pip-compile --generate-hashes` |
| Dependencias del frontend | Mensual o ante un aviso | `npm audit`; los saltos mayores, en PRs aparte |
| Secretos en el historial | Ante cada PR | GitGuardian corre en cada PR |
| Revisión completa | Semestral o ante un cambio grande | Repetir la sección 1 y actualizar este archivo |
