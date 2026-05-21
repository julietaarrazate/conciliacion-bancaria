# Contratos de API
> Actualizar cuando se agreguen/modifiquen endpoints. El frontend y mobile dependen de este documento.

---

## Base URL

```
Desarrollo: http://localhost:8000
```

## Autenticación

Todos los endpoints (excepto `/auth/login` y `/auth/register`) requieren header:
```
Authorization: Bearer <jwt_token>
```

---

## Auth

### POST /auth/login
**Body:** `{ "email": "string", "password": "string" }`
**Response 200:** `{ "access_token": "string", "token_type": "bearer" }`

### POST /auth/register
**Body:** `{ "email": "string", "password": "string", "full_name": "string" }`

---

## Cuentas Bancarias

### GET /accounts/  ·  POST /accounts/

---

## Extractos

### GET /statements/  ·  POST /statements/upload (multipart)
### DELETE /statements/{id}  → NO borra planillas, solo el extracto
### GET /statements/{id}/transactions
### POST /statements/{id}/transactions  → agregar UM manual
### PATCH /statements/transactions/{txn_id}  → editar fila (estado, fecha, cliente, monto)
### DELETE /statements/transactions/{txn_id}  → borrar UM
### GET /statements/{id}/export  → CSV con estados + cliente + planilla

---

## Conciliaciones

### GET /reconciliations/  ·  POST /reconciliations/
### GET /reconciliations/{id}/items
### POST /reconciliations/{id}/auto-match
**Response 200:**
```json
{ "matched": 38, "unmatched": 7, "difference": "-1250.00", "no_esta": 2, "faltan_datos": 3 }
```

### POST /reconciliations/{id}/items  → acreditación manual
**Body:**
```json
{
  "bank_transaction_id": 10,
  "accounting_entry_id": null,
  "planilla_movimiento_id": 42,
  "estado": "acreditado",
  "observacion": null
}
```
Debe especificarse `accounting_entry_id` O `planilla_movimiento_id`.

### PATCH /reconciliations/items/{item_id}  → editar estado/planilla/observación
### DELETE /reconciliations/items/{item_id}  → desacreditar (libera txn y movimiento)
### POST /reconciliations/{id}/close

---

## Clientes

### GET /clientes/?activo=true  ·  POST /clientes/
### GET /clientes/{id}  ·  PATCH /clientes/{id}
### GET /clientes/{id}/planillas

**Cliente body:**
```json
{
  "nombre": "string", "cuit": "string|null", "titular": "string|null",
  "cuenta": "string|null", "comision": "0.00",
  "forma_pago": "banco|efectivo|cheque|transferencia", "activo": true
}
```

---

## Planillas

### GET /planillas/?cliente_id=  ·  POST /planillas/
### GET /planillas/{id}/movimientos
### POST /planillas/movimientos
### PATCH /planillas/movimientos/{id}  → si `estado=ok` sincroniza con extracto
### DELETE /planillas/movimientos/{id}

**Estados de movimiento:** `pendiente | ok | no_esta | faltan_datos | rechazado`

---

## Cheques

### GET /cheques/  ·  POST /cheques/  (genera asiento: Debe Crédito / Haber Pasivo Cliente + Comisiones)
### POST /cheques/{id}/acreditar  (Debe Banco / Haber Crédito)
### POST /cheques/{id}/rechazar  (Debe Pasivo Cliente / Haber Crédito)

---

## Pagos

### GET /pagos/  ·  POST /pagos/
medio: `banco | efectivo`. Asiento: Debe Pasivo Cliente / Haber Banco|Efectivo.

---

## Gastos

### GET /gastos/  ·  POST /gastos/
medio: `banco | efectivo`. Asiento: Debe Gasto / Haber Banco|Efectivo.

---

## Contabilidad

### GET /contabilidad/cuentas  → catálogo
### GET /contabilidad/libro-diario  → todos los asientos con líneas
### GET /contabilidad/libro-mayor/{cuenta_id}  → mov. cronológicos + saldo acumulado
### GET /contabilidad/sumas-y-saldos
### GET /contabilidad/balance

---

## Estados (extracto y planillas)

| Estado | Significado |
|---|---|
| `pendiente` | sin acreditar |
| `acreditado` / `ok` | match confirmado |
| `no_esta` | el monto no apareció en el extracto |
| `faltan_datos` | no se puede identificar cliente (sin nombre/cuit/cuenta) |
| `duplicado` | (informativo) ya acreditado en otra fecha — ver `fecha_acreditacion_original` |
| `rechazado` | rechazado manualmente |

---

## Códigos de error

| Código | Significado |
|--------|-------------|
| 400 | Body inválido |
| 401 | Token ausente o expirado |
| 403 | Sin permisos |
| 404 | Recurso no encontrado |
| 422 | Validación Pydantic / regla de negocio |
| 500 | Error interno |
