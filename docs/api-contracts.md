# Contratos de API
> Actualizar cuando se agreguen/modifiquen endpoints. El frontend y mobile dependen de este documento.

---

## Base URL

```
Desarrollo: http://localhost:8000
```

## Autenticación

Todos los endpoints (excepto `/auth/login`) requieren header:
```
Authorization: Bearer <jwt_token>
```

---

## Auth

### POST /auth/login
**Body:**
```json
{ "email": "string", "password": "string" }
```
**Response 200:**
```json
{ "access_token": "string", "token_type": "bearer" }
```

---

## Cuentas Bancarias

### GET /accounts/
**Response 200:**
```json
[{ "id": 1, "name": "Cuenta Corriente BNA", "account_number": "...", "bank_name": "BNA", "currency": "ARS" }]
```

### POST /accounts/
**Body:**
```json
{ "name": "string", "account_number": "string", "bank_name": "string", "currency": "ARS" }
```
**Response 201:** objeto cuenta creada

---

## Extractos

### POST /statements/upload
**Body:** `multipart/form-data` con campo `file` (CSV o OFX) y `account_id`
**Response 201:**
```json
{ "id": 1, "period_start": "2024-01-01", "period_end": "2024-01-31", "transactions_count": 45 }
```

---

## Conciliaciones

### GET /reconciliations/
**Query params:** `account_id` (opcional), `status` (opcional: open/in_progress/closed)
**Response 200:** lista de conciliaciones

### POST /reconciliations/
**Body:**
```json
{ "statement_id": 1 }
```
**Response 201:** objeto conciliación creada

### POST /reconciliations/{id}/auto-match
**Response 200:**
```json
{ "matched": 38, "unmatched": 7, "difference": "-1250.00" }
```

### PATCH /reconciliations/{id}/items/{item_id}
**Body:**
```json
{ "bank_transaction_id": 10, "accounting_entry_id": 45 }
```
**Response 200:** ítem actualizado

---

## Códigos de error

| Código | Significado |
|--------|-------------|
| 400 | Body inválido o validación fallida |
| 401 | Token ausente o expirado |
| 403 | Sin permisos para ese recurso |
| 404 | Recurso no encontrado |
| 422 | Error de validación Pydantic |
| 500 | Error interno |
