# Monitoreo de Arquitectura y Costos — Cuadra

**Última actualización:** 3 de junio de 2026  
**Objetivo:** Mantener control de recursos, limits gratis y costos potenciales

---

## 1. INFRAESTRUCTURA BASE (Producción)

### Backend — Render (FastAPI)
- **Servicio:** srv-d7pqt81j2pic73c0c6fg
- **Plan:** Gratuito (5GB RAM, dormancy)
- **Límite gratis:** Ilimitado (pero duerme tras 15 min inactividad)
- **Costo si se actualiza:** ~$7-10/mes (hobby plan con garantía de actividad)
- **Monitoreo:** https://dashboard.render.com/services/srv-d7pqt81j2pic73c0c6fg
- **Alertas:** UptimeRobot pinguea `/health` cada 5 min (evita dormancy)

### Frontend — Vercel (React + PWA)
- **Proyecto:** prj_cVINkspVm6j3B1fxOrdU81B0ehWg
- **Plan:** Gratuito (Hobby)
- **Límite gratis:** 100 GB bandwidth/mes, builds ilimitados
- **Costo si se actualiza:** ~$20/mes (Pro plan)
- **Monitoreo:** https://vercel.com/dashboard
- **Alertas:** Auto-redeploy en push a main (vía GitHub)

### Base de datos — Neon (PostgreSQL)
- **Endpoint:** ep-ancient-hall-anz4pezn.c-6.us-east-1.aws.neon.tech
- **Plan:** Free (5 GB storage, 1 compute unit)
- **Límite gratis:** 5 GB (hoy ~200 MB con fotos en base64)
- **Costo si se pasa:** $0.30/GB/mes
- **Monitoreo:** https://console.neon.tech → Projects → conciliacion-bancaria
- **Estimación:** Con R2 activado, nunca se pasará (fotos → R2, no DB)

---

## 2. STORAGE EXTERNO (Nuevo — junio 2026)

### R2 — Cloudflare (Almacenamiento de fotos)
- **Bucket:** conciliacion-fotos
- **Plan:** Free (10 GB/mes gratis)
- **Límite actual:** 0 GB (sin fotos aún, recién activado)
- **Costo post-free:** $0.015/GB (después de 10 GB gratis/mes)
- **Monitoreo:** 
  - Dashboard: https://dash.cloudflare.com → R2 → conciliacion-fotos → Overview
  - **Alerta automática:** Cron diario **09:00 ART** → si > 8 GB, envía email a `julietaarrazate@gmail.com`
- **Estimación de consumo:**
  - 1 foto cheque: ~800 KB
  - 100 cheques/mes = 80 MB
  - 1,000 cheques/mes = 800 MB
  - ~12 meses = 10 GB ✓ (dentro del free)
- **Cómo desactivar:** En Render, eliminar env vars `S3_*` → redeploy

---

## 3. MONITOREO DE ERRORES (Nuevo — junio 2026)

### Sentry (Backend + Frontend)

#### Backend — FastAPI
- **Proyecto:** https://cuadra-yq.sentry.io/projects/python
- **DSN:** `https://12714f4d10b4dcb1db1e1b67dda6f330@o4511502043250688.ingest.us.sentry.io/4511502067171328`
- **Plan:** Free (5,000 errores/mes gratis)
- **Límite actual:** 0 errores (recién activado)
- **Costo post-free:** $29/mes para 50,000 eventos (muy raro)
- **Monitoreo:** https://cuadra-yq.sentry.io/projects/python
  - Ver: "Issues" (errores capturados)
  - Stats: eventos por día en dashboard
- **Alertas:** Sentry envía email si se acerca a 4,500 eventos
- **Cómo desactivar:** En Render, eliminar env var `SENTRY_DSN` → redeploy

#### Frontend — React
- **Proyecto:** https://cuadra-yq.sentry.io/projects/conciliacion-frontend
- **DSN:** `https://67a53be36ded4edc3f056f01296826c5@o4511502043250688.ingest.us.sentry.io/4511502096728065`
- **Plan:** Free (5,000 errores/mes gratis, compartido con backend)
- **Límite actual:** 0 errores (recién activado)
- **Monitoreo:** https://cuadra-yq.sentry.io/projects/conciliacion-frontend
- **Cómo desactivar:** En Vercel, eliminar env var `VITE_SENTRY_DSN` → redeploy

---

## 4. EMAIL Y NOTIFICACIONES

### Resend (Backend — Backup + Password Reset)
- **Plan:** Free (100 emails/día)
- **Uso actual:** ~1-2 emails/mes (backup diario + password resets ocasionales)
- **Límite:** 100/día es más que suficiente
- **Monitoreo:** https://resend.com/emails
- **Costo post-free:** $20/mes para 1,000/mes (muy raro)

### Web Push (Backend — Notificaciones)
- **Tech:** VAPIR keys (standard, gratis)
- **Costo:** $0 (es un protocolo, no un servicio)
- **Limitación:** Requiere PWA instalada (Chrome Android)
- **Monitoreo:** Manual en `/perfil` → "Activar notificaciones"

---

## 5. CHECKLIST DE COSTOS MENSUALES

| Servicio | Plan | Gratis | Potencial | Status |
|----------|------|--------|-----------|--------|
| **Render (Backend)** | Hobby free | ✓ | $7-10 | ✅ OK |
| **Vercel (Frontend)** | Hobby free | ✓ | $20 | ✅ OK |
| **Neon (DB)** | Free 5GB | ✓ | $0.30/GB | ✅ OK (200 MB hoy) |
| **R2 (Fotos)** | Free 10GB/mes | ✓ | $0.015/GB | ✅ OK (~800 MB/mes estimado) |
| **Sentry (Errors)** | Free 5K/mes | ✓ | $29 | ✅ OK (sin errores) |
| **Resend (Email)** | Free 100/día | ✓ | $20 | ✅ OK (2 emails/mes) |
| **TOTAL POTENCIAL** | | **$0/mes** | **~$56-60/mes** | ✅ SAFE |

---

## 6. ALERTAS AUTOMÁTICAS POR SERVICIO

### Render
- ✅ UptimeRobot (interno) — pinguea `/health` cada 5 min
- ⚠️ Si no responde → intenta reactivar automáticamente
- 📧 Vercel GitHub Actions — notifica en Slack si deploy falla

### Vercel
- ✅ Auto-redeploy en push a main
- ⚠️ Vercel Dashboard → Deployments → status

### Neon
- 📧 Email automático si llega a 4 GB (falta 1 GB para límite)
- 📊 Monitoreo manual: Dashboard → Billing

### Sentry
- 📧 Email automático si llega a 4,500 eventos (5,000 es límite)
- 📊 Dashboard en tiempo real → Issues

### R2
- 📊 Sin alertas automáticas; chequear mensual en Dashboard

---

## 7. PROCEDURE MENSUAL DE CONTROL (5 min)

**1er día del mes:**
1. Sentry (ambos proyectos) → Issues → ver si hay errores nuevos
2. R2 → Usage → anotar GB consumidos (estimar trend)
3. Neon → Dashboard → ver tamaño DB (debe estar ~500 MB)
4. Vercel → Analytics → bandwidth usado (típicamente <1 GB)
5. Render → Logs → buscar errores 500 (trigger de alertas)

**Si algo se acerca al límite:**
- Sentry >4,500 eventos → investigar qué está errando
- R2 >7 GB → revisar si hay fotos duplicadas/stale
- Neon >4 GB → correr cleanup de base64 viejas (si aún existen)

---

## 8. ESCALADA DE COSTOS (Cómo reaccionar)

### Escenario 1: Sentry llega a 5,000 eventos
- **Causa probable:** App tiene bugs, no usuarios excesivos
- **Acción:** Investigar issues en Sentry, fixear bugs
- **Costo:** $29/mes si se activa plan Pro (50K eventos)

### Escenario 2: R2 llega a 15 GB
- **Causa probable:** +1,500 fotos en el mes (7,500 cheques)
- **Acción:** Nada (sigue siendo gratuito primer 10 GB); anotar que mes próximo costará $75 (~5 GB × $0.015)
- **Costo:** $75/mes si sigue creciendo 5 GB/mes

### Escenario 3: Neon llega a 4.5 GB
- **Causa probable:** Fotos en base64 antiguas no migraron a R2
- **Acción:** Correr script de migration de base64 → R2; eliminar de DB
- **Costo:** $0.30 × 0.5 GB = $0.15 (mínimo)

### Escenario 4: Render cae a free tier (app duerme)
- **Causa probable:** UptimeRobot se paró o tuvo un error
- **Acción:** Revisar UptimeRobot, reactivar manualmente
- **Costo:** $0 (sigue siendo free); solo downtime ~15 min hasta re-activate

---

## 9. CÓMO DESACTIVAR SI ES NECESARIO

| Servicio | Desactivar | Efecto |
|----------|-----------|--------|
| **R2** | Eliminar env vars `S3_*` en Render | Fotos vuelven a base64 (retro-compatible) |
| **Sentry Backend** | Eliminar `SENTRY_DSN` en Render | Sin monitoreo de errores del API |
| **Sentry Frontend** | Eliminar `VITE_SENTRY_DSN` en Vercel | Sin monitoreo de errores del cliente |
| **Resend (Email)** | Eliminar `RESEND_API_KEY` en Render | Sin backups por email; password reset sigue funcionando (fallback interno) |
| **Push Notifications** | Eliminar `VAPID_*` en Render | Sin notificaciones push; alertas manuales en `/perfil` |

---

## 10. NOTAS FINALES

- ✅ **Arquitectura muy económica:** $0-10/mes en producción hoy
- ✅ **Escalabilidad a bajo costo:** Hasta ~10,000 usuarios sin pasar free tiers
- ✅ **Sin sorpresas:** Todos los servicios tienen alertas o límites conocidos
- ⚠️ **Action requerida:** Revisar este documento **1× por mes** (5 min)

**Próxima revisión:** 3 de julio de 2026

---

## APÉNDICE: URLs de Monitoreo (Acceso rápido)

```
RENDER DASHBOARD:      https://dashboard.render.com/services/srv-d7pqt81j2pic73c0c6fg
VERCEL DASHBOARD:      https://vercel.com/dashboard
NEON CONSOLE:          https://console.neon.tech/app/projects
CLOUDFLARE R2:         https://dash.cloudflare.com → R2 → conciliacion-fotos
SENTRY BACKEND:        https://cuadra-yq.sentry.io/projects/python
SENTRY FRONTEND:       https://cuadra-yq.sentry.io/projects/conciliacion-frontend
UPTIMEROBOT:           https://uptimerobot.com (check /health status)
```
