# Estado de seguridad — registro vivo

Qué se revisó, qué se corrigió (con su PR) y qué falta. **Se actualiza al cerrar cada sesión
que toque seguridad, dependencias o infraestructura**; el modelo técnico (cómo funciona cada
control) vive en [`SECURITY_MODEL.md`](SECURITY_MODEL.md).

Última actualización: **23/oct/2026**.

---

## 1. Revisión de seguridad oct/2026 (primera revisión completa)

Alcance: backend, frontend, base, historial de git, dependencias. Método: lectura de los 40+
routers, `gitleaks` sobre todo el historial, `npm audit` / `pip-audit`, consultas de solo lectura
en producción para verificar que no hubo aprovechamiento.

| Tema | Estado | Dónde |
|---|---|---|
| Aislamiento entre organizaciones (endpoints que aceptaban IDs de otra org) | ✅ Corregido, sin rastros de uso en prod | PR #254 · `tests/test_seguridad_multitenant.py` |
| Rate limiting por IP real (detrás del proxy de Render) + cupo diario de IA por organización en la base | ✅ | PR #255 · `tests/test_limites.py` |
| Usuario demo activo en Org A | ✅ Desactivado en prod (auditoría `DESACTIVAR_SEGURIDAD`) | — |
| Dependencias del backend con versión y hash fijos + pip 26.2.2 + Python 3.11.17 | ✅ | PR #259 |
| python-jose → PyJWT, dependencias al día, `npm audit fix` | ✅ | PR #261 |
| Sesiones: cambio/reset de contraseña cierra sesiones; email en `/me` pide contraseña | ✅ | PR #261 · `tests/test_seguridad_auth.py` |
| Login: usuario inactivo no entra, Google valida mail verificado y pasa por 2FA, 2FA con topes y falla cerrado, PBKDF2 600k | ✅ | PR #261 |
| Revisor de solo lectura en toda ruta que escribe + meta-test que lo vigila | ✅ | PR #261 · `tests/test_seguridad_permisos.py` |
| Auditoría separada por organización | ✅ | PR #261 (migración 035) |
| Excel/CSV sin fórmulas inyectadas, subidas con tope y anti zip-bomb, PDFs escapados, sin `document.write` | ✅ | PR #261 · `tests/test_seguridad_entradas.py` |
| Claves que estuvieron en el historial (Render, Vercel, GitHub) | ✅ Verificado: ya no existen en las cuentas | — |

## 2. Pendiente

### Decisiones abiertas (de la operadora)
- **Contraseña del superadmin**: se re-hashea desde `SUPERADMIN_PASSWORD` en cada arranque, así
  que un cambio desde `/perfil` no dura. Opción: setearla solo si el usuario no existe.
- **Fusionar clientes** pide `reconcile`; borra el cliente origen. ¿Pasar a `delete_records`?
- **Exports TXT Tango/Holistor** sin sanear fórmulas (formato fijo; el apóstrofo se vería en la
  descripción importada).
- **Neon**: limitar conexiones por IP (si el plan lo permite) y habilitar `pg_stat_statements`.

### Técnico (bajo riesgo, para un próximo lote)
- CORS: la regex de previews de Vercel acepta un hostname que otra cuenta podría reproducir
  (sin credenciales, riesgo bajo). Cierre total: listar previews en `EXTRA_CORS_ORIGINS`.
- `POST /push/subscribe` no reasigna un endpoint que ya es de otro usuario.
- `GET /caja/arqueo/hoy` crea el arqueo del día si falta (escritura en un GET).
- `backup_service.py` y `reset_operativo.py` siguen filtrando auditoría por la org del usuario.
- Revisar que el frontend oculte las acciones que el revisor ya no puede hacer.
- Frontend: `react-router-dom` 6 (aviso moderado) → react-router 7 en un PR aparte.
- Frontend: saltos mayores (Vite 8, React 19, Tailwind 4, Vitest 5) **armados y verificados, sin
  subir**: falta decidir el soporte de navegadores viejos (Tailwind 4 exige iOS 16.4+).

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
