# API_RULES — Convenciones de la API REST (FastAPI)

Reglas obligatorias para todo endpoint nuevo o modificado del backend (`backend/app`).
Basado en el código real de `middleware/auth.py` y los routers `extractos.py`, `ctb_plan.py`,
`historial.py`, `auth.py`, `agente.py`, y la configuración de `main.py`.

Documentos relacionados:
- Modelo de seguridad y matriz de roles → [../security/SECURITY_MODEL.md](../security/SECURITY_MODEL.md)
- Aislamiento por organización a nivel datos → [../database/DATABASE_RULES.md](../database/DATABASE_RULES.md)
- Receta paso a paso para crear un endpoint → [../playbooks/NEW_API_ENDPOINT.md](../playbooks/NEW_API_ENDPOINT.md)

---

## 1. Autenticación: JWT Bearer

Todo endpoint protegido depende de `get_current_user` (o de un wrapper que lo use, como
`require_permission` o `require_superadmin`). El cliente envía el JWT en el header
`Authorization: Bearer <token>`.

```python
from app.middleware.auth import get_current_user
from app.models.user import User

@router.get("/algo")
def listar(db: Session = Depends(get_db),
           current_user: User = Depends(get_current_user)):
    ...
```

- El token se valida en `get_current_user` (`backend/app/middleware/auth.py`): decodifica,
  chequea revocación (`jti` en `revoked_tokens`) y que el usuario exista y esté activo.
- Endpoints públicos (sin auth) viven en routers dedicados (`public_router`, parte de `auth`,
  `google_auth`) y NO usan `get_current_user`.
- Detalle del ciclo de vida del token, expiración (8h) y revocación: ver
  [SECURITY_MODEL](../security/SECURITY_MODEL.md).

---

## 2. Multi-tenant: `org_id` query param + `can_switch_org` (OBLIGATORIO)

Este es el patrón central de la API. **Toda lectura y escritura sobre datos de negocio debe
estar aislada por organización.** El patrón estándar usa el query param opcional `org_id`
combinado con `can_switch_org`.

### Patrón de referencia (de `historial.py` / `extractos.py`)

```python
from app.middleware.auth import get_current_user, can_switch_org

@router.get("/planillas")
def list_planillas(org_id: Optional[int] = Query(None),
                   db: Session = Depends(get_db),
                   current_user: User = Depends(get_current_user)):
    q = db.query(Planilla).filter(Planilla.deleted_at.is_(None))

    # Aislamiento por org — patrón obligatorio
    if can_switch_org(current_user, org_id) and org_id:
        q = q.filter(Planilla.organizacion_id == org_id)
    elif not current_user.is_superadmin:
        q = q.filter(Planilla.organizacion_id == (current_user.organizacion_id or 1))
    ...
```

Semántica:
- Si el usuario pidió un `org_id` y tiene permiso para operar ahí (`can_switch_org` →
  superadmin siempre, contador si está en `allowed_org_ids`), se filtra por esa org.
- Si NO es superadmin y no pidió un `org_id` válido, se fuerza el filtro a su propia org
  (`current_user.organizacion_id or 1`). Un usuario normal **nunca** ve datos de otra org.
- El superadmin sin `org_id` ve todas las organizaciones (no se aplica filtro de org).

### `can_switch_org` (definida en `middleware/auth.py`)

```python
def can_switch_org(user: User, org_id: int) -> bool:
    if user.is_superadmin:
        return True
    allowed = user.allowed_org_ids or []
    return org_id in allowed
```

### Override en memoria desde `get_current_user`

`get_current_user` también soporta `?org_id=` directamente: si el usuario es superadmin o el
org pedido está en su `allowed_org_ids`, hace `db.expunge(user)` y reasigna
`user.organizacion_id` **en memoria, sin persistir** (el expunge evita que el commit del
endpoint guarde el cambio). Por eso muchos endpoints que solo leen `current_user.organizacion_id`
(p. ej. `agente.py`, `ctb_plan.py` vía el helper `_org_id`) quedan correctamente scopeados sin
escribir el bloque `can_switch_org` explícito — el scoping ya viene resuelto en el usuario.

> Regla práctica: si el endpoint construye su query a partir de un `org_id` query param,
> usá el bloque `can_switch_org` explícito. Si solo lee `current_user.organizacion_id`,
> confiá en el override de `get_current_user`. En ambos casos el filtro por
> `organizacion_id` en la query **nunca es opcional**.

### Resolución de un objeto puntual

Para traer un recurso por id con aislamiento, el patrón es un helper que devuelve 404 (no 403)
cuando el recurso es de otra org — así no se filtra la existencia de IDs ajenos. Ejemplo real
`_extracto_for_user` en `extractos.py`:

```python
def _extracto_for_user(db, extracto_id, current_user, include_deleted=False):
    q = db.query(ExtractoBancario).filter(ExtractoBancario.id == extracto_id)
    if not include_deleted:
        q = q.filter(ExtractoBancario.deleted_at.is_(None))
    if not current_user.is_superadmin:
        q = q.filter(ExtractoBancario.organizacion_id == current_user.organizacion_id)
    extracto = q.first()
    if not extracto:
        raise HTTPException(404, "Extracto no encontrado")
    return extracto
```

Detalle de los modelos `organizacion_id` y constraints de DB: ver
[DATABASE_RULES](../database/DATABASE_RULES.md).

---

## 3. Permisos en 3 capas

La autorización se aplica en tres niveles independientes. Una capa NO reemplaza a la otra.

| Capa | Dónde | Cómo |
|------|-------|------|
| 1. Router/endpoint (rol→permiso) | `Depends(require_permission("..."))` | Bloquea por permiso de rol |
| 2. Endpoint (scope de datos) | `can_switch_org` / filtro `organizacion_id` | Bloquea por organización |
| 3. Frontend (UI) | gating en React | Oculta acciones que el backend igual rechazaría |

### Capa 1 — `require_permission`

```python
from app.middleware.auth import require_permission

@router.delete("/{extracto_id}")
def delete_extracto(extracto_id: int, db: Session = Depends(get_db),
                    current_user: User = Depends(require_permission("delete_records"))):
    ...
```

`require_permission(permission)` (en `middleware/auth.py`) verifica que el rol del usuario
incluya ese permiso. El superadmin pasa siempre. Para acciones exclusivas del superadmin existe
`require_superadmin`. La matriz exacta de roles→permisos está en
[SECURITY_MODEL](../security/SECURITY_MODEL.md).

> Endpoints que no llevan `require_permission` (solo `get_current_user`) son de lectura general
> disponible para cualquier usuario autenticado de la org. Las acciones destructivas
> (`delete_records`) o de gestión (`manage_users`, `admin_accounting`) **deben** llevar el
> permiso explícito.

### Capa 2 — Scope de organización

Ya descripta en §2. Es obligatoria aunque la capa 1 ya haya filtrado por rol: el permiso dice
*qué puede hacer*, el scope dice *sobre qué datos*.

### Capa 3 — Frontend

El frontend oculta/inhabilita botones según el rol (ver [../security/SECURITY_MODEL.md](../security/SECURITY_MODEL.md)
y los stores en `frontend/src/store`). Es UX, **no** seguridad: el backend siempre revalida.

---

## 4. Paginación: `skip`/`offset` + `limit`, respuesta `{items|total}`

Los endpoints de listado paginan con dos enteros y devuelven el total para que el frontend
arme la paginación. Hay dos nombres de offset conviviendo en el código:

- `skip` (la mayoría: `extractos.py`, `historial.py`)
- `offset` (módulo contabilidad: `ctb_plan.py`)

Forma de respuesta estándar — un dict con `total` e `items`:

```python
@router.get("/plan-cuentas")
def get_plan_cuentas(limit: int = Query(1000, ge=1, le=5000),
                     offset: int = Query(0, ge=0), ...):
    q = db.query(PlanCuenta).filter(...).order_by(PlanCuenta.codigo)
    total = q.count()
    cuentas = q.offset(offset).limit(limit).all()
    return {"items": [...], "total": total}
```

Reglas:
- Calcular `total` con `q.count()` **antes** de aplicar `offset/limit`.
- Aplicar `order_by` determinístico antes de paginar (si no, el orden entre páginas es inestable).
- Acotar `limit` con `Query(default, ge=..., le=...)` donde el volumen pueda crecer
  (ver `ctb_plan.py`, `le=5000`). Algunos listados aceptan `limit=0` como "sin límite"
  (ver `listar_movimientos` en `extractos.py`) — usar con cuidado.
- En endpoints existentes que devuelven `{"total", "items"}`, mantené esa forma; no inventes
  otra envoltura.

---

## 5. Manejo de errores: `HTTPException`, sin `except` genérico que enmascare

- Errores esperados → `raise HTTPException(status_code, detail)` con mensaje claro en español.
  Los códigos usados en el repo: `400` (input inválido), `401` (auth), `403` (permiso),
  `404` (no existe / de otra org), `409` (conflicto, p. ej. período cerrado o solicitud ya
  resuelta), `413` (archivo muy grande), `429` (rate limit / cuota), `503` (feature opt-in no
  configurada).
- **No capturar `Exception` de forma amplia para devolver un mensaje genérico**: enmascara la
  causa real y dificulta el diagnóstico (es un anti-patrón documentado, emparentado con los
  bugs `Decimal vs float` de [../../BUGS.md](../../BUGS.md), donde un `except` ancho ocultaba un
  `TypeError` de tipos). El patrón correcto cuando hace falta un `try/except` amplio (p. ej.
  procesar un archivo subido por el usuario) es:
  1. Re-lanzar las `HTTPException` ya específicas **antes** de la captura genérica.
  2. `db.rollback()` si hubo escritura.
  3. Loguear el error real (`logger.error("upload error: %s", e)`) — nunca silenciarlo.
  4. Devolver un mensaje accionable al usuario.

  Patrón de referencia (`upload_extracto` en `extractos.py`):

  ```python
  try:
      ...  # puede hacer raise HTTPException(400, "...") específicos
  except HTTPException:
      raise                          # 1. preserva el error específico
  except Exception as e:
      db.rollback()                  # 2. revierte
      logger.error("upload error: %s", e)   # 3. loguea la causa real
      raise HTTPException(400, "Error al procesar el archivo. Verificá el formato...")  # 4
  finally:
      if tmp_path and os.path.exists(tmp_path):
          os.remove(tmp_path)        # limpieza de temporales siempre
  ```

- Operaciones secundarias que no deben tumbar la principal (p. ej. registrar un asiento contable
  tras importar movimientos) van en su propio `try/except` *fault-tolerant*: se loguean y se
  reportan con un flag (`contabilidad_ok`) en la respuesta, en lugar de propagar — ver
  `agregar_ultimos_movimientos` en `extractos.py`. Nunca quedan silenciosas.

---

## 6. Rate limiting (slowapi)

`slowapi` está montado en `main.py` (`app.state.limiter`, handler de `RateLimitExceeded`).
La clave es la IP remota (`get_remote_address`). Se aplica por endpoint con el decorador
`@limiter.limit(...)`. El handler responde `429` cuando se supera el límite.

Requisito: un endpoint con `@limiter.limit` debe recibir `request: Request` como parámetro
(slowapi lo necesita para leer la IP).

```python
from slowapi import Limiter
from slowapi.util import get_remote_address
limiter = Limiter(key_func=get_remote_address)

@router.post("/upload")
@limiter.limit("10/minute")          # uploads de extracto
async def upload_extracto(request: Request, file: UploadFile = File(...), ...):
    ...
```

Límites reales en el código (orientativos para endpoints nuevos del mismo tipo):

| Endpoint | Límite | Archivo |
|----------|--------|---------|
| `POST /extractos/upload` | `10/minute` | `extractos.py` |
| `POST /extractos/{id}/agregar-um` | `20/minute` | `extractos.py` |
| `POST /auth/login` | `10/minute` | `auth.py` |
| `POST /auth/register` | `5/minute` | `auth.py` |
| `POST /auth/verify-2fa` | `3/minute` | `auth.py` |
| `POST /auth/forgot-password` | `3/hour` | `auth.py` |
| `POST /auth/reset-password` | `10/hour` | `auth.py` |
| `GET /auth/login-approval/{id}` | `120/minute` (polling) | `auth.py` |

Cuotas de IA: el router `agente.py` además implementa **cuota diaria propia** (no slowapi):
contadores en memoria por día ART para OCR (`OCR_DAILY_LIMIT`, default 150) y chat
(`CHAT_DAILY_LIMIT`, default 200), que también responden `429`. Detalle en
[../ai/AI_GUIDE.md](../ai/AI_GUIDE.md).

---

## 7. Validación de archivos en upload

Los endpoints que reciben archivos validan en este orden (ver `upload_extracto` y
`agregar_ultimos_movimientos` en `extractos.py`):

1. **Extensión**: solo `.xlsx`, `.xls`, `.csv` → si no, `HTTPException(400)`.
2. **Tamaño**: `len(content) > settings.max_file_size` (50 MB) → `HTTPException(413)`.
3. **Magic bytes** (anti-renombrado): el contenido real debe coincidir con la extensión.
   Un atacante no puede renombrar un binario a `.xlsx` para colarlo.

   ```python
   _XLSX_MAGIC = b'PK\x03\x04'        # XLSX = ZIP/OOXML
   _XLS_MAGIC  = b'\xd0\xcf\x11\xe0'  # XLS = OLE2
   header = content[:8]
   if ext == '.xlsx' and not header.startswith(_XLSX_MAGIC):
       raise HTTPException(400, "El archivo no es un Excel válido (.xlsx debe ser ZIP/OOXML)")
   if ext == '.xls' and not header.startswith(_XLS_MAGIC):
       raise HTTPException(400, "El archivo no es un Excel válido (.xls debe ser formato OLE2)")
   ```

4. **Temporales**: escribir a `NamedTemporaryFile` y **siempre** borrar en `finally`.
5. **Validación semántica**: tras parsear, rechazar si no hay movimientos reconocibles o si todos
   los montos son cero (`HTTPException(400)` con mensaje accionable).

Imágenes/audio del asistente IA (`agente.py`) llegan como base64 o `UploadFile` y se validan por
no-vacío; el procesamiento real lo hace Gemini. Ver [../ai/AI_GUIDE.md](../ai/AI_GUIDE.md).

---

## 8. Auditoría

Las escrituras relevantes registran un log con `registrar_log(db, user_id, tabla, registro_id,
accion, payload)` (ver llamadas en `extractos.py` y `auth.py`). Toda acción que crea, modifica o
borra datos de negocio debería dejar rastro de auditoría.

---

## 9. CORS y headers (contexto)

`main.py` cierra CORS al dominio de producción de Vercel + previews + dev local, con
`allow_credentials=False` y métodos `GET/POST/PUT/DELETE/PATCH/OPTIONS`. Cada respuesta lleva
headers de seguridad y el header de latencia `X-Process-Time`; las requests por encima de
`SLOW_REQUEST_MS` se loguean como `SLOW ...`. Detalle en
[../security/SECURITY_MODEL.md](../security/SECURITY_MODEL.md).

---

## Pendiente de revisar

- **Nombre del offset inconsistente**: la mayoría de routers usan `skip`, pero el módulo
  contabilidad (`ctb_plan.py`) usa `offset`. No es un bug, pero conviene saberlo al consumir la API
  o unificar a futuro.
- **`limit=0` = sin límite** en `listar_movimientos` (`extractos.py`): difiere de otros listados
  donde `limit` siempre acota. Verificar el comportamiento esperado antes de copiar el patrón.
- **`can_switch_org` con `org_id=None`**: el bloque `if can_switch_org(...) and org_id` exige
  `org_id` truthy, así que `org_id=0` se trataría como ausente. No hay org 0 en el sistema, pero
  es un borde a tener presente.
- El playbook [../playbooks/NEW_API_ENDPOINT.md](../playbooks/NEW_API_ENDPOINT.md) referenciado
  aquí puede no existir todavía al momento de leer esto.
