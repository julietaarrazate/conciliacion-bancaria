# Backup y recuperación — Conciliación Bancaria

Procedimientos paso a paso para proteger los datos y recuperarse de incidentes.

---

## 1. Tipos de backup disponibles

| Tipo | Cuándo usar | Esfuerzo | Cobertura |
|------|-------------|----------|-----------|
| **A. Snapshot de Neon** | Antes de cambios grandes (migraciones, deploys riesgosos) | 2 min | 100% (toda la DB) |
| **B. Point-in-Time Recovery** | Después de un error humano (restaurar a "5 minutos atrás") | 5 min | 100%, últimos 7 días |
| **C. Export JSON completo** | Backup periódico para guardar fuera de Neon | 1 min | 100% por organización |
| **D. Export Excel** | Para inspección humana o entrega al contador | 1 min | Planillas + extractos |
| **E. Backup automatico por email** | Funciona solo, todos los días — el que recomendamos por default | 0 min | 100% todas las orgs |

**Regla simple**: tené prendido **E** (automático), hacé **A** antes de cualquier cambio grande.

---

## 1.5 Backup automatico diario por email (procedimiento E)

Scheduler interno (APScheduler en el backend) que todos los días a las **03:00 ART**:
1. Genera el JSON completo de TODAS las organizaciones
2. Lo gzippea (queda en ~10-30% del tamaño original)
3. Lo manda por email a `julietaarrazate@gmail.com` (configurable) con el `.json.gz` adjunto
4. Lo registra en auditoria (`accion=BACKUP_AUTO_OK` o `BACKUP_AUTO_ERROR`)

### Setup (una sola vez, en Render)

1. Crear cuenta en [resend.com](https://resend.com) (gratis, 3000 emails/mes)
2. **API Keys** → **Create API Key** → copiar el `re_xxxxxx`
3. En Render: **conciliacion-api** → **Environment** → **Add env var**:
   - `RESEND_API_KEY` = el token recién copiado
4. Save & deploy. El servicio reinicia y el scheduler arranca solo.

No requiere verificar dominio: usa el remitente default `onboarding@resend.dev`
de Resend, que sirve para mandarte a vos misma.

### Otras env vars opcionales

- `BACKUP_EMAIL_TO` = destinatario (default: `julietaarrazate@gmail.com`)
- `BACKUP_EMAIL_FROM` = remitente (default: `onboarding@resend.dev`)
- `BACKUP_HOUR_ART` = hora ART (default: `3`)
- `BACKUP_MINUTE` = minuto (default: `0`)
- `BACKUP_ENABLED` = `false` para apagarlo sin borrar la API key

### Verificación / control

- Pantalla `/papelera` (admin) muestra una card con:
  - Si está activo (verde) o pausado (amarillo)
  - Hora del cron
  - Último OK / último error con timestamp ART
  - Tamaño del último backup enviado
  - Botón **"Backup ahora"** para disparar uno manualmente (te llega en 5-10s)

- O por API:
  - `GET /admin/backup/status` → estado JSON
  - `POST /admin/backup/run-now` → dispara manual

### Restore desde el email

1. Bajás el `.json.gz` del email
2. `gunzip conciliacion_backup_YYYY-MM-DD.json.gz`
3. Cargás el JSON con cualquier herramienta que parsee el formato
   (estructura documentada en `app/services/backup_service.py`)

---

## 2. Procedimiento A — Snapshot de Neon (recomendado antes de cambios)

1. Entrá a [console.neon.tech](https://console.neon.tech)
2. Seleccioná el proyecto de conciliación
3. En el menú lateral: **Branches** → **Create branch**
4. Configurá:
   - **Name**: `backup-YYYYMMDD-motivo` (ej: `backup-20260524-antes-migracion`)
   - **Parent branch**: `production`
   - **Auto-delete**: poné **nunca** o el máximo
   - **Branch data and schema**: seleccioná "Include data from the parent branch up to this moment"
5. **Create branch**

Listo. Es una copia exacta y congelada de los datos. No afecta a producción.

**Para restaurar desde ese snapshot**: cambiá la `DATABASE_URL` de Render para que apunte a la branch del snapshot (vas a verla en Neon → Branches → la branch elegida → Connection string). Render redeploya y ya estás corriendo sobre los datos del snapshot.

---

## 3. Procedimiento B — Point-in-Time Recovery (después de un error)

Si alguien borró algo importante o se rompió algo en producción **en los últimos 7 días** (plan gratuito de Neon):

1. Entrá a [console.neon.tech](https://console.neon.tech)
2. Branches → **Create branch**
3. Seleccioná **"Branch data and schema from a past point in time"**
4. Elegí la fecha y hora ANTES del error (ej: hace 30 minutos)
5. **Create branch**

Eso te da una branch con los datos como estaban en ese momento. Después podés:
- Apuntar Render a esa branch (cambia `DATABASE_URL`) → restauración completa
- O conectarte con un cliente SQL y copiar solo las tablas que necesites

---

## 4. Procedimiento C — Export JSON completo (mensual)

Este es el backup que guardás **fuera** de Neon, por si pasa algo grave con la cuenta de Neon.

**Para una organización**:

```bash
curl -X GET "https://conciliacion-api.onrender.com/admin/organizaciones/1/backup-completo" \
  -H "Authorization: Bearer TU_TOKEN_JWT" \
  -o "backup_caneland_$(date +%Y%m%d).json"
```

**Para TODO el sistema** (solo superadmin):

```bash
curl -X GET "https://conciliacion-api.onrender.com/admin/organizaciones/backup-completo-todo" \
  -H "Authorization: Bearer TU_TOKEN_JWT" \
  -o "backup_sistema_$(date +%Y%m%d).json"
```

Para obtener el `TU_TOKEN_JWT`: hacé login en la app, abrí DevTools (F12) → Application → Local Storage → buscá `auth-storage` → ahí está el token.

**Qué contiene el JSON**:
- Organizaciones, usuarios (sin contraseñas), clientes
- Extractos + movimientos
- Planillas + filas conciliadas
- Cheques (con fotos), pagos, gastos
- Caja diaria + órdenes de pago
- Liquidaciones, cierres de período
- Plan de cuentas, reglas, asientos contables completos
- Patrones aprendidos (IA)
- Auditoría (últimos 50.000 logs)

**Dónde guardarlo**: Drive personal, disco externo, o cualquier lugar **fuera de Render y Neon**. La idea es que si esos servicios desaparecen, vos tenés los datos.

---

## 5. Procedimiento D — Export Excel (para el contador)

Desde la app: superadmin → Organizaciones → botón "Backup" en cada organización. Descarga un Excel con planillas + extractos formateado.

O por API:
```bash
curl -X GET "https://conciliacion-api.onrender.com/admin/organizaciones/1/backup" \
  -H "Authorization: Bearer TU_TOKEN_JWT" \
  -o backup_contador.xlsx
```

---

## 6. Calendario sugerido

| Frecuencia | Qué hacer |
|------------|-----------|
| **Antes de cualquier deploy con cambios de schema** | Procedimiento A (snapshot Neon) |
| **1 vez por mes** | Procedimiento C (JSON completo descargado a Drive) |
| **Trimestral** | Probar restauración: crear branch desde snapshot, apuntar app de test, verificar que funciona |
| **Después de un incidente** | Procedimiento B (PITR) o restaurar desde el JSON del mes anterior |

---

## 7. Plan de desastre — qué hacer si pasa lo peor

### Escenario: "Borré algo importante hace 20 minutos"
→ Procedimiento B. Creás branch a "hace 30 minutos", restaurás desde ahí.

### Escenario: "Hice un cambio que rompió todo"
→ En Render: Settings → Deploys → buscá el deploy anterior funcionando → "Rollback to this deploy". El código vuelve. Si además se corrompió la DB, sumá Procedimiento B.

### Escenario: "Neon perdió mi cuenta o me suspendieron"
→ Necesitás el JSON del Procedimiento C. Crear cuenta nueva en Neon (o cualquier Postgres), correr migrations de Alembic, y escribir un script de import desde el JSON.
**(Importante: hoy no tenemos script de import desde JSON. Si ese escenario es preocupante, avisame y lo creamos.)**

### Escenario: "Render desapareció"
→ Mover el repo a Fly.io / Railway / Vercel Functions. El backend es FastAPI estándar, corre en cualquier lado con Python.

---

## 8. Lo que NO está cubierto todavía

Estos son riesgos que existen pero requieren más trabajo:

- **Script automático de import desde JSON**: hoy podés exportar pero no re-importar en un sistema vacío
- **Backup automático programado**: hoy el JSON se baja manualmente; podríamos agregar un cron que lo suba a S3/Drive automáticamente
- **Soft delete**: cuando borrás un extracto, desaparece. Una papelera de reciclaje a 30 días sería el siguiente paso

Ver issue en CLAUDE.md → roadmap.
