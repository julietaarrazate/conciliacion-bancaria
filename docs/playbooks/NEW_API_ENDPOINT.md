# Playbook — Agregar un endpoint REST nuevo

Guía paso a paso para agregar un endpoint a la API de Cuadra respetando las
convenciones del repo: aislamiento multi-tenant, permisos, paginación, schemas
Pydantic y manejo de errores.

> **Reglas de fondo (no se duplican acá):** las reglas generales de la API
> (formato de respuesta, query params, paginación, códigos de error) viven en
> [`../api/API_RULES.md`](../api/API_RULES.md). El modelo de permisos y el
> aislamiento por organización están en
> [`../security/SECURITY_MODEL.md`](../security/SECURITY_MODEL.md). Este playbook
> es el "cómo" mecánico; esos dos documentos son el "qué" y el "por qué".

**Plantillas de referencia (código real):**
- Router CRUD + export + multi-tenant: `backend/app/routers/extractos.py`
- Router de solo lectura con paginación: `backend/app/routers/ctb_plan.py`
- Helpers compartidos por módulo: `backend/app/routers/ctb_common.py`,
  `backend/app/routers/cheques_common.py`

---

## Checklist rápido

- [ ] Defino el router (o reutilizo uno existente del módulo) con `prefix` y `tags`.
- [ ] Acepto `org_id: Optional[int] = Query(None)` y resuelvo la org destino.
- [ ] Aplico el aislamiento multi-tenant en TODA query (filtro por `organizacion_id`).
- [ ] Aplico el permiso en la capa correcta si la acción no es solo-lectura.
- [ ] Si lista, devuelvo `{"items": [...], "total": N}` con `limit`/`offset`.
- [ ] Defino schema Pydantic de respuesta (o `response_model`) cuando aplique.
- [ ] No uso `except Exception` genérico que enmascare el error real (ver BUGS.md).
- [ ] Registro auditoría en operaciones que mutan datos (`registrar_log`).
- [ ] Trato montos como `Decimal`, nunca `float` (ver `../../BUGS.md`).
- [ ] Agrego test (caso feliz + aislamiento de otra org + 403 sin permiso).

---

## 1. Elegir/crear el router

Cada módulo monta un `APIRouter` con `prefix` y `tags`. Reutilizá el router del
módulo si ya existe; solo creás uno nuevo para un dominio nuevo.

```python
from fastapi import APIRouter, Depends, Query
router = APIRouter(prefix="/mi-modulo", tags=["mi-modulo"])
```

Ejemplo real: `extractos.py:46` (`APIRouter(prefix="/extractos", tags=["extractos"])`).
Los módulos grandes se parten en varios archivos que comparten un mismo prefix
montado por el padre (ver el comentario de cabecera en `ctb_plan.py:1-7`).

## 2. Recibir `org_id` y resolver la organización destino

Todo endpoint multi-tenant acepta `org_id` por query y NUNCA confía en él a
ciegas: se valida con `can_switch_org` (`middleware/auth.py:61`). Hay dos patrones
en el repo, ambos válidos:

**Patrón A — helper `_org_id` (recomendado para módulos nuevos).** Resuelve la org
en una línea. Ver `ctb_common.py:36-39`:

```python
from .ctb_common import _org_id  # o el _org_id del módulo

oid = _org_id(current_user, org_id)
q = db.query(MiModelo).filter(MiModelo.organizacion_id == oid)
```

**Patrón B — inline (como en `extractos.py:92-97`).** Útil cuando superadmin sin
`org_id` debe ver todo:

```python
if can_switch_org(current_user, org_id) and org_id:
    q = q.filter(MiModelo.organizacion_id == org_id)
elif not current_user.is_superadmin:
    q = q.filter(MiModelo.organizacion_id == (current_user.organizacion_id or 1))
```

> El override de org se aplica en memoria en `get_current_user`
> (`middleware/auth.py:48-57`): si el request trae `?org_id=` y el usuario lo
> tiene permitido, `current_user.organizacion_id` ya viene apuntando ahí (con
> `db.expunge` para no persistirlo). Aun así, **filtrá explícitamente por
> `organizacion_id` en cada query** — no asumas que el override solo alcanza.

## 3. Aislamiento multi-tenant en cada query

Toda lectura o escritura va filtrada por `organizacion_id`. Para resolver una
entidad puntual por id, usá el patrón de "resolver con aislamiento" de
`extractos.py:30-42` (`_extracto_for_user`): si no existe **o es de otra org**,
devuelve `404` (no `403`, para no filtrar existencia entre tenants).

```python
def _entidad_for_user(db, entidad_id, current_user):
    q = db.query(MiModelo).filter(MiModelo.id == entidad_id)
    if not current_user.is_superadmin:
        q = q.filter(MiModelo.organizacion_id == current_user.organizacion_id)
    obj = q.first()
    if not obj:
        raise HTTPException(404, "No encontrado")
    return obj
```

> **Org A (`organizacion_id=1`) es intocable:** solo cambios aditivos, nunca
> modificar datos existentes (ver CLAUDE.md). Endpoints de limpieza masiva deben
> filtrar por la org actual y, si son destructivos, exigir superadmin — ver
> `delete_todos_extractos` (`extractos.py:290-326`).

## 4. Permisos: aplicarlos en la capa correcta

Si la acción **muta datos** o es sensible, protegé el endpoint con
`require_permission(...)` como dependencia (`middleware/auth.py:79`). El catálogo
de permisos por rol está en `check_permission` (`middleware/auth.py:85-94`) — no
lo redefinas, referenciá [`../security/SECURITY_MODEL.md`](../security/SECURITY_MODEL.md).

```python
from app.middleware.auth import require_permission

@router.delete("/{id}")
def borrar(id: int, db: Session = Depends(get_db),
           current_user: User = Depends(require_permission("delete_records"))):
    ...
```

Ejemplo real: `delete_extracto` exige `delete_records` (`extractos.py:266-268`).
Los `GET` de solo lectura suelen usar solo `get_current_user` (`ctb_plan.py:38-45`).
Superadmin pasa todos los permisos (`middleware/auth.py:82-83`); para "solo
superadmin" usá `require_superadmin` (`middleware/auth.py:69`).

**Capa correcta = la dependencia del endpoint**, no un `if` adentro del cuerpo:
así FastAPI rechaza antes de tocar la DB y queda en el contrato OpenAPI.

## 5. Paginación: `limit`/`offset` → `{items, total}`

Los listados devuelven `{"items": [...], "total": N}` y paginan con `limit` y
`offset` (o `skip`). El `total` se calcula con `.count()` **antes** de aplicar
`offset/limit`. Ver `ctb_plan.py:38-68`:

```python
@router.get("/cosas")
def listar(org_id: Optional[int] = Query(None),
           limit: int = Query(1000, ge=1, le=5000),
           offset: int = Query(0, ge=0),
           db: Session = Depends(get_db),
           current_user: User = Depends(get_current_user)):
    oid = _org_id(current_user, org_id)
    q = db.query(MiModelo).filter(MiModelo.organizacion_id == oid).order_by(MiModelo.codigo)
    total = q.count()
    items = q.offset(offset).limit(limit).all()
    return {"items": [_serializar(x) for x in items], "total": total}
```

- Acotá `limit` con `ge`/`le` para evitar pedidos abusivos (`ctb_plan.py:41`).
- `extractos.py:87-103` usa `skip`/`limit` con `response_model` Pydantic — ambos
  nombres existen en el repo; en módulos nuevos preferí `limit`/`offset`.
- **Excepción importante:** los *exports* NO paginan, traen todo el dataset —
  ver [`NEW_REPORT.md`](./NEW_REPORT.md).

## 6. Evitar el problema N+1 (eager loading)

Si serializás relaciones, cargalas con `selectinload`/`joinedload` para no
disparar una query por fila. Ver el comentario y el código en `ctb_plan.py:86-96`
(`selectinload(ReglaContable.cuenta_debe)`) e `historial.py:130-134`.

## 7. Schema Pydantic

Definí el schema de respuesta en `backend/app/schemas/` y pasalo como
`response_model` para validar y documentar la salida. Ejemplo:
`extractos.py:87` usa `response_model=ExtractoListResponse` (definido en
`app/schemas/extracto.py`). Para payloads de entrada simples se acepta `dict`
crudo (ver `renombrar_extracto`, `extractos.py:249-251`), pero para entradas con
estructura preferí un `BaseModel` con validación.

## 8. Manejo de errores (NO enmascarar)

- Lanzá `HTTPException(status, detail)` con el código correcto: `400` validación,
  `404` no encontrado / otra org, `409` conflicto (periodo cerrado, duplicado),
  `413` archivo grande, `403` sin permiso.
- En bloques `try/except` que envuelven escritura, **re-lanzá `HTTPException`
  primero** y solo después capturá `Exception` para hacer `rollback` + loguear.
  Patrón correcto: `extractos.py:238-243`:

```python
    except HTTPException:
        raise                      # no la enmascares como 400 genérico
    except Exception as e:
        db.rollback()
        logger.error("contexto: %s", e)
        raise HTTPException(400, "Mensaje claro para el usuario")
```

> **Anti-patrón (ver `../../BUGS.md`):** un `except Exception` que devuelve un
> mensaje genérico ("Error al procesar el archivo") **antes** de re-lanzar la
> `HTTPException` real esconde la causa (p.ej. un `409` de unique index quedaba
> reportado como "error genérico de procesar el archivo"). El orden
> `except HTTPException: raise` primero es obligatorio.

## 9. Auditoría y consistencia

Las operaciones que mutan datos registran auditoría con `registrar_log(db,
user_id, tabla, entidad_id, accion, payload)` — ver `extractos.py:232-233`.
`registrar_log` debe recibir tipos serializables: si pasás montos, convertí
`Decimal` a `str` (bug histórico de serialización JSON de `Decimal`, ver
`../../BUGS.md`).

## 10. Registrar el router

Si creaste un router nuevo, montalo donde se arma la app (`backend/app/main.py`)
con `app.include_router(...)`. Verificá que el `prefix` no choque con rutas
existentes — ver la nota de `extractos.py:728-733` sobre montar
`conciliaciones_router` con prefix propio para no colisionar con `/extractos/{id}`.

## 11. Verificación

```bash
cd backend && pytest                 # tests del backend
```

Test mínimo del endpoint nuevo:
1. Caso feliz (200 + forma `{items,total}` o el schema esperado).
2. Aislamiento: un usuario de la org B no ve/edita datos de la org A (404).
3. Permisos: un rol sin el permiso recibe 403.
4. Si hay `DELETE` con FKs entrantes, test de borrado **con** datos relacionados
   (no solo el caso feliz) — bug recurrente, ver `../../BUGS.md`.

---

## Pendiente de revisar

- **Convención de paginación fijada**: el estándar canónico es `limit`/`offset`
  (ver [`../api/API_RULES.md §4`](../api/API_RULES.md)). Los routers legacy con `skip`
  (extractos, historial, caja, pagos, auditoria, admin, ctb_libro) se migran
  oportunamente, no en masa. **Código nuevo: siempre `offset`.**
