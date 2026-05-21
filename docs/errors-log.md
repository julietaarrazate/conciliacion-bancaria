# Registro de Errores Conocidos
> **Leer este archivo ANTES de empezar cualquier sesión.**
> Agregar errores nuevos al final con el formato establecido.

---

## Formato de entrada

```
### [MÓDULO] Título corto del error
**Fecha:** YYYY-MM-DD
**Síntoma:** qué se ve cuando ocurre
**Causa raíz:** por qué ocurre
**Solución:** cómo se resolvió
**Cómo evitarlo:** qué hacer para no caer de nuevo
```

---

## Errores registrados

### [BACKEND] No se podía modificar acreditaciones del extracto
**Fecha:** 2026-05-21
**Síntoma:** Una acreditación equivocada en el extracto no se podía editar ni borrar.
**Causa raíz:** No existían endpoints PATCH/DELETE para `reconciliation_items` ni `bank_transactions`.
**Solución:** Agregados `PATCH /reconciliations/items/{id}`, `DELETE /reconciliations/items/{id}` (con liberación de planilla), `PATCH /statements/transactions/{id}`, `DELETE /statements/transactions/{id}`.
**Cómo evitarlo:** Para cada operación de creación pensar siempre en su edición/borrado.

### [BACKEND] Borrar extracto eliminaba planillas de clientes
**Causa raíz:** Cascade implícito a través de FK.
**Solución:** FK `bank_transactions.planilla_movimiento_id` → `ON DELETE SET NULL`. Planillas viven independientes.

### [BACKEND] Acreditación manual guardaba en planilla aparte
**Solución:** `POST /reconciliations/{id}/items` ahora exige `planilla_movimiento_id` cuando no hay `accounting_entry_id`. La transacción queda vinculada a esa planilla del cliente.

### [BACKEND] Duplicado falso entre fechas
**Síntoma:** Una acreditación hecha en otra fecha aparecía como duplicado.
**Solución:** `matching_service.auto_match_full` detecta acreditaciones previas por (monto, ref) y guarda `fecha_acreditacion_original`. NO se marca como error.

### [BACKEND] Faltaban estados NO ESTÁ y FALTAN DATOS
**Solución:** Columnas `estado` en `bank_transactions` y `movimientos_planilla`. Matching detecta:
- Movimiento de planilla sin contraparte → `no_esta`.
- Transacción sin cliente identificable (sin cliente_id ni referencia) → `faltan_datos`.

### [BACKEND] No se podían crear clientes sin conciliaciones previas
**Solución:** Modelo `Cliente` independiente. `POST /clientes/` autocontenido.

### [BACKEND] `db.get()` se usaba sin `await` en routers async
**Causa raíz:** SQLAlchemy 2.0 async requiere `await db.get(...)`.
**Solución:** Refactorizado `reconciliations.py` con `await` y validación de ownership.

### [BACKEND] `EmailStr` fallaba al importar
**Causa raíz:** `pydantic[email]` no estaba en requirements.txt.
**Solución:** Reemplazado `pydantic==2.7.1` por `pydantic[email]==2.7.1`.

---

## Patrones de error recurrentes (actualizar si aparece alguno)

*(vacío al inicio)*
