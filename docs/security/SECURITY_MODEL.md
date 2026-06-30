# SECURITY_MODEL — Modelo de seguridad de Cuadra

Modelo de autenticación, autorización, aislamiento multi-tenant y protecciones del backend.
Basado en el código real: `middleware/auth.py`, `services/auth.py`, `routers/auth.py`,
`routers/google_auth.py`, `models/user.py`, `models/twofa_code.py`, `models/revoked_token.py`,
`models/login_approval.py`, `services/arca_crypto.py`, `config.py` y `main.py`.

Documento relacionado: convenciones de API y dónde se aplica cada control →
[../api/API_RULES.md](../api/API_RULES.md).

---

## 1. Autenticación

### JWT (HS256, expira 8h)

- Algoritmo `HS256`, firmado con `SECRET_KEY` (env var; en prod debe sobreescribir el default —
  `main.py` loguea `CRITICAL` si sigue siendo el valor de desarrollo).
- Expiración por defecto: `access_token_expire_minutes = 480` (**8 horas** = jornada laboral),
  definido en `config.py`.
- Cada token incluye un `jti` único (UUID) generado en `create_access_token` (`services/auth.py`),
  que habilita la **revocación individual** (logout). El payload típico:
  `{"sub": email, "user_id": ..., "role": ..., "exp": ..., "jti": ...}`.
- Se envía como header `Authorization: Bearer <token>` y se valida en `get_current_user`.

Variantes de expiración:
- **Contador**: sesión más corta de **4h** (`CONTADOR_SESSION_MINUTES = 240` en `routers/auth.py`),
  generada recién al ser aprobada (ver §6).

### Hashing de contraseñas: `pbkdf2_sha256`

`services/auth.py`:
- Hash con `pbkdf2_hmac("sha256", ...)`, **120.000 iteraciones**, salt aleatorio de 16 bytes.
  Formato almacenado: `pbkdf2_sha256$<iters>$<salt_hex>$<dk_hex>`.
- Verificación con `hmac.compare_digest` (comparación en tiempo constante).
- Compatibilidad legacy: si el hash empieza con `$2`, verifica con `bcrypt` (usuarios viejos).
- Elegido por venir en la stdlib (no compila nada en el deploy de Render).

---

## 2. Matriz de roles → permisos

Roles definidos en `models/user.py` (`RoleEnum`): `admin`, `operador`, `revisor`, `auditor`,
`contador`. Además el flag booleano `is_superadmin` (ortogonal al rol).

La matriz exacta vive en `require_permission` dentro de `middleware/auth.py`:

| Permiso | admin | operador | revisor | auditor | contador | superadmin |
|---------|:-----:|:--------:|:-------:|:-------:|:--------:|:----------:|
| `upload_files`     | ✅ | ✅ | — | — | ✅ | ✅ (todo) |
| `reconcile`        | ✅ | ✅ | — | — | ✅ | ✅ |
| `manage_users`     | ✅ | — | — | — | — | ✅ |
| `view_audit`       | ✅ | — | — | ✅ | ✅ | ✅ |
| `view_accounting`  | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| `manage_finance`   | ✅ | ✅ | — | ✅ | ✅ | ✅ |
| `admin_accounting` | ✅ | — | — | — | — | ✅ |
| `delete_records`   | ✅ | — | — | — | — | ✅ |
| `view_results`     | — | — | ✅ | — | — | ✅ |

Listas literales del código (fuente de verdad — copiar de aquí al documentar features nuevas):

```python
permissions = {
    "admin":    ["upload_files", "reconcile", "manage_users", "view_audit",
                 "view_accounting", "manage_finance", "admin_accounting", "delete_records"],
    "operador": ["upload_files", "reconcile", "manage_finance", "view_accounting"],
    "revisor":  ["view_results", "view_accounting"],
    "auditor":  ["view_audit", "view_accounting", "manage_finance"],
    "contador": ["upload_files", "reconcile", "manage_finance", "view_accounting", "view_audit"],
}
```

Notas (del propio código):
- **superadmin** (`is_superadmin=True`): `require_permission` retorna el usuario antes de mirar la
  matriz → tiene **todos** los permisos, en **todas** las organizaciones. Es Julieta
  (`julietaarrazate@gmail.com`).
- **contador** (rol "de prueba"): opera (sube, concilia, finanzas, liquidaciones) y ve
  contabilidad + auditoría/actividad en solo lectura. **NO** tiene `delete_records` (no borra nada)
  ni `manage_users` (no ve Usuarios/Orgs/Papelera). Su login es por aprobación en vivo (§6).
- Acciones exclusivas del superadmin no usan la matriz sino `require_superadmin` (p. ej.
  `POST /auth/register`, decidir aprobaciones de login, limpieza masiva de extractos).

Las 3 capas donde se aplica esto (router, endpoint, frontend) están descriptas en
[../api/API_RULES.md](../api/API_RULES.md) §3.

---

## 3. Aislamiento multi-tenant

Cada fila de negocio lleva `organizacion_id`. El usuario tiene:
- `organizacion_id`: su organización principal (default 1).
- `is_superadmin`: ve y gestiona todas las orgs.
- `allowed_org_ids` (JSON, solo relevante para `contador`): orgs extra a las que puede cambiar.

Regla central — un usuario normal **solo ve su propia org**. Implementada con `can_switch_org`
(`middleware/auth.py`) y el patrón `org_id` query param documentado en
[../api/API_RULES.md](../api/API_RULES.md) §2:

```python
def can_switch_org(user, org_id):
    if user.is_superadmin:
        return True
    return org_id in (user.allowed_org_ids or [])
```

`get_current_user` aplica un override **en memoria** de la org activa cuando llega `?org_id=` y el
usuario tiene permiso (`db.expunge(user)` para no persistirlo). Org A (`organizacion_id=1`) es la
organización principal y por convención **nunca** se modifican sus datos existentes (solo cambios
aditivos). Detalle de columnas y constraints: ver [../database/DATABASE_RULES.md](../database/DATABASE_RULES.md).

---

## 4. 2FA por email (opt-in admin/superadmin)

`routers/auth.py` + `models/twofa_code.py`. Activo solo si `RESEND_API_KEY` está seteada
(si no, el login es directo — degradación silenciosa).

- Aplica a usuarios con `is_superadmin` o rol `admin`.
- En el login, en vez de devolver el token, se genera un código de **6 dígitos**, se guarda su
  **sha256** (`code_hash`) con expiración de **10 min** (`TWOFA_CODE_TTL_MINUTES`) y se manda por
  email (Resend). La respuesta es `202 {"requires_2fa": true, "email": ...}`.
- El usuario confirma en `POST /auth/verify-2fa` (rate limit `3/minute`). Recién ahí se emite el JWT.
- **Lockout**: `failed_attempts`; tras `TWOFA_MAX_ATTEMPTS = 3` fallos el código se marca `used` y
  hay que pedir uno nuevo reiniciando sesión.
- Códigos expirados se purgan antes de generar uno nuevo. Si falla el envío de email, hay fallback
  a login directo (se loguea el error). El `code_hash` nunca se guarda en claro.

---

## 5. Revocación de tokens (logout)

`models/revoked_token.py` + `POST /auth/logout`:
- `RevokedToken` guarda el `jti`, `user_id` y `expires_at` del token revocado.
- En cada request, `get_current_user` rechaza (`401 "Sesión cerrada"`) si el `jti` del token está
  en la tabla.
- `logout` decodifica el token **sin verificar expiración** (`verify_exp=False`) para que incluso un
  token ya inválido pueda cerrarse, y agrega el `jti`. Tokens viejos sin `jti` pasan derecho
  (backward-compat).
- Limpieza: un job programado purga tokens revocados (03:30 ART, `start_token_cleanup_job` en
  `main.py`) — viven solo hasta su `expires_at`.

---

## 6. Aprobación de login en vivo (rol `contador`)

`models/login_approval.py` + `routers/auth.py`. El contador **no** recibe token al loguearse:

1. Login → se crea un `LoginApproval` en estado `pending` con un `poll_secret` (se guarda su
   **sha256**, `poll_secret_hash`) y un TTL de 10 min (`APPROVAL_REQUEST_TTL_MINUTES`). Respuesta
   `202 {"pending_approval": true, "approval_id", "poll_secret", "expires_at"}`. Se notifica a los
   superadmins por push (best-effort).
2. El cliente del contador hace **polling** a `GET /auth/login-approval/{id}?secret=...`
   (rate limit `120/minute`). El `secret` es obligatorio y se compara por hash — evita que un
   tercero adivine el `approval_id` y robe el token.
3. El superadmin aprueba/rechaza en `POST /auth/login-approval/{id}/decide` (`require_superadmin`).
   Al aprobar se genera el JWT de **4h** y se guarda en `access_token`.
4. El polling entrega el token **una sola vez** (luego se limpia el campo). Pasadas las 4h, repite.

Caducidad: si el superadmin no decide a tiempo, el pedido pasa a `expired`.

---

## 7. Login con Google (OAuth, opt-in)

`routers/google_auth.py`. Activo solo con `GOOGLE_CLIENT_ID` + `GOOGLE_CLIENT_SECRET`
(si faltan → `503`). Flujo auth-code (redirect, sin popups, sirve en mobile):

1. `POST /auth/google` recibe `{code, redirect_uri}`.
2. El backend intercambia el code por tokens contra `oauth2.googleapis.com/token` (con el secret).
3. Verifica el `id_token` contra `tokeninfo`, valida que `aud == GOOGLE_CLIENT_ID` y que el email
   esté verificado (`email_verified`).
4. **Solo usuarios ya registrados**: si el email no existe → `404` (no auto-registra; el alta de
   usuarios la gestiona un admin). Cuenta desactivada → `403`.
5. Emite el JWT de sesión.

> Nota: este token se crea con `create_access_token({"sub": user.email})` sin `user_id`/`role` en
> el payload — ver "Pendiente de revisar".

---

## 8. Cifrado de certificados ARCA (Fernet, en reposo)

`services/arca_crypto.py`. Cada organización sube su certificado X.509 + clave privada (par emitido
por ARCA para facturar bajo su CUIT) — el material más sensible que maneja el sistema.

- Se cifran con **Fernet** (AES-128-CBC + HMAC) usando `ARCA_ENCRYPTION_KEY` (env var Render, nunca
  en el repo). Se guardan cifrados en las columnas `*_enc` de `arca_config` (ver `main.py`).
- Sin la key seteada, el módulo **rechaza explícitamente** cargar certificados (`ArcaCryptoError`).
  A diferencia de otros módulos opt-in, acá NO hay fallback en claro: degradar silenciosamente
  significaría guardar una clave privada sin cifrar. Nunca se loguean ni se devuelven en claro.
- El módulo ARCA está construido pero **desactivado a propósito** en producción (ver CLAUDE.md).

---

## 9. Rate limiting (brute force)

`slowapi` con clave = IP remota (`main.py`, `app.state.limiter`). Protege login y endpoints
sensibles. Tabla de límites por endpoint en [../api/API_RULES.md](../api/API_RULES.md) §6.
Relevantes para seguridad: `login` `10/minute`, `verify-2fa` `3/minute`, `forgot-password`
`3/hour`, `register` `5/minute`.

Defensas adicionales en auth:
- `forgot-password` responde **siempre 200** con el mismo mensaje (exista o no el email) → no se
  puede usar para enumerar usuarios registrados.
- `reset-password` devuelve errores genéricos (no revela si el token existía).
- Logins fallidos se loguean (`LOGIN_FAILED email=... ip=...`).

---

## 10. Headers de seguridad y CORS

Middleware `security_headers` en `main.py` agrega a cada respuesta:

| Header | Valor |
|--------|-------|
| `Strict-Transport-Security` | `max-age=63072000; includeSubDomains` (HSTS, 2 años) |
| `X-Content-Type-Options` | `nosniff` |
| `X-Frame-Options` | `DENY` |
| `Referrer-Policy` | `strict-origin-when-cross-origin` |
| `Permissions-Policy` | `geolocation=(), microphone=(self), camera=(self), payment=()` |
| `X-Process-Time` | latencia del request en ms (observabilidad) |

CORS (`CORSMiddleware`): allowlist cerrada al dominio de producción de Vercel + regex de previews
de Vercel + `localhost:3000/5173`. `allow_credentials=False`; métodos `GET/POST/PUT/DELETE/PATCH/
OPTIONS`; headers `Authorization, Content-Type, Accept`. Orígenes extra solo vía
`EXTRA_CORS_ORIGINS`.

Observabilidad: requests por encima de `SLOW_REQUEST_MS` (default 1500) se loguean como
`SLOW <método> <path> → <status> en <ms>`; Sentry opt-in vía `SENTRY_DSN` (5% de tracing,
`send_default_pii=False`).

---

## Pendiente de revisar

- **Payload del token de Google login**: `google_auth.py` usa
  `create_access_token({"sub": user.email})` sin `user_id` ni `role`, mientras que el login normal
  y el de contador sí los incluyen. `get_current_user` solo necesita `sub`, pero conviene confirmar
  que ningún consumidor del token dependa de `role`/`user_id` en el payload tras un login Google.
- **2FA solo para admin/superadmin**: el rol `contador` (que tiene flujo de aprobación propio) y los
  demás roles no tienen 2FA. Es intencional según el código, pero documentado aquí por las dudas.
- **Validación de fuerza de contraseña**: `reset-password` exige `min_length=6` (schema), pero no
  hay política de complejidad. Revisar si se quiere endurecer.
- La matriz de §2 debe mantenerse sincronizada con `require_permission` en `middleware/auth.py` si
  se agregan permisos o roles nuevos — esa función es la única fuente de verdad.
