# Comprobantes por revisar (facturas de compra por mail + lectura con IA)

Módulo aditivo (v3.30). Las facturas de proveedores llegan por mail a una dirección propia de
cada organización, o se suben a mano; la IA (Gemini) completa los datos y una persona del
estudio los revisa y confirma. Recién al confirmar impactan en IVA (y en Pagos si se pide).

No toca la conciliación ni el cálculo de la liquidación de IVA.

Fuentes de verdad (código):
- `backend/app/models/comprobante_compra.py` — `BuzonComprobantes`, `BorradorComprobante`.
- `backend/app/services/comprobantes_compra_service.py` — lectura con IA, normalización,
  controles, firma del webhook, confirmación.
- `backend/app/routers/comprobantes_compra.py` — endpoints (`/comprobantes-compra`).
- `frontend/src/pages/ComprobantesCompra.tsx` — pantalla `/comprobantes-compra`.
- Tests: `backend/tests/test_comprobantes_compra.py`,
  `frontend/src/pages/__tests__/ComprobantesCompra.test.tsx`.

---

## 1. Flujo

1. **Llega el archivo.**
   - Por mail: Resend Inbound recibe el mail en `facturas-<token>@<INBOUND_EMAIL_DOMAIN>` y
     llama a `POST /comprobantes-compra/webhook/resend` (evento `email.received`). Se crea un
     borrador por adjunto PDF/foto. Las imágenes inline (logos de firmas) se ignoran.
   - A mano: `POST /comprobantes-compra/subir`, hasta 10 archivos de hasta 5 MB (PDF, JPG,
     PNG, WebP).
2. **La IA lo lee en segundo plano** (`BackgroundTasks`): para mails primero se baja el
   adjunto de la API de Resend (las URLs de descarga duran 1 hora). Gemini devuelve JSON, se
   normaliza (`normalizar_datos`) y se corren los controles (`validar_datos`). Estado `listo`,
   o `error` con el motivo si no se pudo leer.
3. **Una persona revisa** en la pantalla, con el PDF al lado, corrige si hace falta y confirma.
4. **Al confirmar** (`confirmar_borrador`):
   - Se crea un `ComprobanteIva` con `direccion="recibido"`, período = mes de la fecha (o el
     que elija la persona) y `archivo_origen = "Comprobantes por revisar #<id>"`.
   - Si se tildó "ya está pagada" y no es nota de crédito: se crea un `Egreso`
     (`tipo=proveedor`, `forma_pago=banco`) y su asiento con `motor_contable.registrar_egreso`,
     igual que `POST /pagos` (fault-tolerant: si el asiento falla, el pago queda y se avisa).

## 2. Reglas

- **Nada entra solo**: sin confirmación no hay `ComprobanteIva` ni `Egreso`.
- **Sin duplicados**: `ComprobanteIva` tiene el unique `(org, direccion, tipo, PV, número,
  CUIT)`. Confirmar una factura ya cargada devuelve 409; importar después el Excel de "Mis
  Comprobantes" con la misma factura la cuenta como duplicada. Al leer, si ya existe, se agrega
  la alerta "Este comprobante ya está cargado en IVA".
- **Para confirmar** hacen falta tipo, punto de venta, número, fecha, CUIT de 11 dígitos y total.
- **Controles (alertas, no bloquean)**: CUIT con dígito verificador inválido; neto + IVA +
  no gravado + exento + percepciones + otros ≠ total (tolerancia $0,10); IVA de una alícuota
  que no coincide con neto × tasa; comprobante C con IVA; comprobante A sin IVA; fecha futura o
  de más de un año.
- **Percepciones**: se leen y quedan guardadas en el borrador, pero **no** se suman solas a la
  liquidación de IVA (ahí siguen cargándose a mano, como antes).
- **Notas de crédito** restan en IVA como cualquier NC (`es_nota_credito`) y nunca generan pago.
- **Montos** en `Decimal`; en el JSON del borrador se guardan como string con 2 decimales.

## 3. Buzón de mail (opt-in por organización)

- No existe hasta que un admin (`admin_accounting`) toca "Crear dirección de mail".
  "Generar otra dirección" cambia el token y la anterior deja de recibir.
- El token tiene 16 caracteres aleatorios; un mail a un token inexistente o viejo se ignora con
  200 (no se revela si existe).
- Un mail sin PDF/foto queda como `sin_adjunto` con su asunto, para que se vea, por ejemplo, el
  código de confirmación del reenvío de Gmail.
- El webhook es idempotente por `email_id` (Resend reintenta).

### Configuración (Render)

| Env var | Para qué |
|---|---|
| `RESEND_API_KEY` | ya existe (backups / 2FA); se usa para bajar los adjuntos |
| `INBOUND_EMAIL_DOMAIN` | dominio de recepción: el `<id>.resend.app` que da Resend, o uno propio con MX a Resend |
| `RESEND_INBOUND_SECRET` | signing secret (`whsec_...`) del webhook `email.received` |
| `GEMINI_API_KEY` | ya existe; sin ella los borradores quedan en `error` y se completan a mano |
| `FACTURAS_OCR_DAILY_LIMIT` | opcional, tope diario de lecturas (default 200, aparte del OCR de cheques) |

En Resend: activar Receiving, crear un webhook a
`https://conciliacion-api.onrender.com/comprobantes-compra/webhook/resend` con el evento
`email.received` y copiar su signing secret. Sin `INBOUND_EMAIL_DOMAIN` + `RESEND_INBOUND_SECRET`
la pantalla oculta la dirección y la subida manual sigue funcionando.

## 4. Permisos

| Acción | Permiso |
|---|---|
| Ver bandeja y dirección | `view_accounting` |
| Subir, volver a leer, descartar | `upload_files` |
| Confirmar | `manage_finance` (igual que importar "Mis Comprobantes") |
| Crear / regenerar la dirección | `admin_accounting` |
| Webhook | sin JWT; firma Svix obligatoria |

Todo filtrado por `organizacion_id` (otra org recibe 404).

## Pendiente de revisar

- El procesamiento corre en `BackgroundTasks` del mismo proceso: si Render se reinicia en el
  medio, el borrador queda en `procesando`. Hoy se resuelve volviendo a subirlo; un job que
  reintente los `procesando` viejos sería una mejora.
- El tope diario de lecturas vive en memoria del proceso (se reinicia con cada deploy), igual
  que el del OCR de cheques (deuda D-4).
- No hay vista previa de PDFs guardados en R2 si el bucket no permite CORS/iframe; con base64
  (default) funciona.
