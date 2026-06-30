# Checklist — Seguridad

Basado en [`docs/security/SECURITY_MODEL.md`](../../docs/security/SECURITY_MODEL.md) y
[`docs/api/API_RULES.md`](../../docs/api/API_RULES.md). Recorrer al tocar auth, endpoints,
uploads o datos sensibles.

## Autenticación

- [ ] Endpoint protegido depende de `get_current_user` (o wrapper). Públicos solo en routers
      dedicados (`public_router`, parte de `auth`, `google_auth`).
- [ ] No se loguean tokens, contraseñas ni secretos.

## Autorización — 3 capas

- [ ] Capa 1 (rol→permiso): `require_permission("<permiso>")` en acciones que mutan o son
      sensibles; `require_superadmin` para lo exclusivo del superadmin.
- [ ] Permiso correcto según la matriz (`upload_files`, `reconcile`, `manage_users`, `view_audit`,
      `view_accounting`, `manage_finance`, `admin_accounting`, `delete_records`, `view_results`).
- [ ] Capa 3 (frontend): UI gateada por rol — es UX, no seguridad; el backend revalida siempre.

## Aislamiento multi-tenant

- [ ] Toda query de negocio filtra por `organizacion_id`; `org_id` validado con `can_switch_org`.
- [ ] Recurso de otra org → 404 (no 403, para no filtrar existencia entre tenants).
- [ ] Org A (`organizacion_id=1`): solo cambios aditivos.

## Secretos

- [ ] Sin keys/tokens/credenciales en código ni en el repo (Render/Vercel/GitHub).
- [ ] `SECRET_KEY` real en prod (no el default de desarrollo).

## Rate limiting

- [ ] Endpoints sensibles (login, register, 2FA, forgot/reset, uploads) con `@limiter.limit(...)`
      y `request: Request` en la firma. Cuotas de IA propias en `agente.py` si aplica.

## Validación de inputs / uploads

- [ ] Uploads validan extensión + tamaño (`max_file_size`) + **magic bytes** (anti-renombrado).
- [ ] Temporales escritos a `NamedTemporaryFile` y borrados en `finally`.
- [ ] Validación semántica tras parsear (rechazar sin movimientos / montos todo-cero).

## Datos y errores

- [ ] Montos en `Decimal` (un `float` mal comparado puede romper validaciones de negocio).
- [ ] Sin `except Exception` genérico que enmascare la causa real.
- [ ] Auditoría (`registrar_log`) en escrituras relevantes.

## Headers / CORS

- [ ] CORS cerrado al dominio de Vercel + previews + dev; headers de seguridad presentes
      (los aplica `main.py`, no aflojarlos).
