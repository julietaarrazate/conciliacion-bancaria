# EXTRACTO DE CÓDIGO FUENTE
## Sistema Integral de Gestión Financiera, Contable y Empresarial
**Versión:** v3.12 | **Fecha:** Junio 2026

---

## Descripción del Contenido

Este documento contiene extractos representativos del código fuente que implementa los componentes originales del sistema:

1. **Motor de Conciliación** — Algoritmo de scoring multi-criterio
2. **Motor Contable** — Generación automática de asientos
3. **Sistema de Aprendizaje** — Patrones automáticos
4. **Cliente API** — Comunicación frontend-backend
5. **Configuración Principal** — Inicialización y scheduler

---

## Arquitectura General del Sistema

### Backend (FastAPI + Python 3.11)
- 22 routers con endpoints especializados
- 18 servicios encapsulando lógica de negocio
- 18 modelos SQLAlchemy con 9 migraciones
- 156 tests automatizados
- Autenticación JWT, 2FA, Rate Limiting

### Frontend (React 18 + TypeScript)
- 31 páginas con componentes especializados
- 18 componentes reutilizables
- Cliente HTTP centralizado con caché SWR
- 6 stores de estado global (Zustand)
- Service Worker para PWA

### Base de Datos (PostgreSQL)
- 18 modelos principales
- Aritmética exacta (Numeric 12,2)
- Auditoría automática de operaciones
- Soft-delete con papelera de reciclaje

---

## Componentes Originales de Algoritmo

### Motor de Conciliación (backend/app/services/conciliacion.py)

**Scoring Multi-Criterio:**
- CUIT exacto: 12 puntos
- CBU/CVU exacto: 10 puntos
- Número de cuenta largo: 8 puntos
- Número de referencia: 6 puntos
- Titular (2 palabras): 5 puntos
- Titular (1 palabra): 3 puntos
- Bonus fecha cercana: +1 a +5 puntos

**Regla de Seguridad:** Monto duplicado en extracto → exige identidad verificada

**Tolerancia Configurada:**
- Fechas: ±5 días
- Deduplicación UM: (orden, monto) o (fecha, monto, titular_norm)

---

### Motor Contable Automático (backend/app/services/motor_contable.py)

**18+ Tipos de Asiento Generados Automáticamente:**

1. `um_lote` — Importar UM bancario
2. `um_reclass` — Reclasificar al conciliar
3. `cheque_registro` — Registro de cheque (3 líneas)
4. `cheque_acred_banco` — Acreditación bancaria
5. `cheque_acred_cliente` — Acreditación en cta cliente
6. `cheque_rechazo_banco` — Reversa bancaria
7. `cheque_rechazo_cliente` — Reabre deuda
8. `cheque_rechazo_gasto` — Gastos bancarios
9. `egreso` — Pago/gasto unificado
10. `caja_op` — Operación de caja
11. `caja_efectivo` — Efectivo en caja
12. `cc_inicial` — Backfill histórico
13-18. Reversos de cada tipo (`*_reverso`)

**Cuentas de Tránsito que Netean a Cero:**
- Cheques en cartera (1-1-2-1) + Cheques depositados (2-1-3-1)

---

### Sistema de Aprendizaje (backend/app/services/aprendizaje.py)

**Tabla `PatronAprendido`:**
- Aprende de correcciones manuales del usuario
- 2+ confirmaciones → patrón automático en futuras conciliaciones
- Ej: "cliente GARCIA" + CBU 285059094... → asociación automática

---

### Cliente API Centralizado (frontend/src/services/api.ts)

**Características:**
- ~25 KB de código TypeScript
- Interceptores de autenticación y error
- Cache SWR con TTL 30-60s
- Retry automático con backoff exponencial
- Manejo de 401/403/429 transparente

---

### Configuración Principal (backend/app/main.py)

**Seguridad al Arrancar:**
- ALTER TABLE safety nets (ADD COLUMN IF NOT EXISTS)
- Backfill de plan de cuentas idempotente (PLAN_PATCH)
- Vinculación cliente↔cuenta normalizada
- Migración de datos legacy

**Scheduler (APScheduler):**
- 03:00 ART — Backup completo JSON gzipeado
- 10:00 ART — Push alertas (cheques, movimientos sin asignar)

**Permisos en 3 Capas:**
- `view_accounting` — Lectura formal
- `manage_finance` — Operación diaria
- `admin_accounting` — Config estructural

---

## Tests Automatizados (156 tests)

| Módulo | Tests | Cobertura |
|---|---|---|
| Conciliación | 34 | Motor scoring, dedup, UM |
| Contabilidad | 41 | Asientos, cuentas corrientes, balances |
| Autenticación | 18 | JWT, 2FA, PIN, WebAuthn |
| Parsers | 22 | Multi-banco, Excel |
| Timezone | 4 | UTC-3 Argentina |
| Diversos | 37 | Permisos, soft-delete, auditoría |

---

## Seguridad Implementada

- JWT 8 horas (jornada laboral)
- pbkdf2_sha256 (sin bcrypt compilable)
- Rate limiting (slowapi) — 60 req/min por IP
- Headers de seguridad (CORS, CSP, X-Frame-Options)
- 2FA por email (código 6 dígitos SHA256)
- PIN de bloqueo + biometría (WebAuthn)
- Auditoría automática (antes/después de cada operación)

---

## Stack Completo

**Backend:** FastAPI 0.104 + SQLAlchemy 2.0 + PostgreSQL + Alembic  
**Frontend:** React 18 + TypeScript + Vite + TailwindCSS + Zustand  
**Móvil:** React Native (Expo) + React Navigation  
**Hosting:** Render (backend) + Vercel (web) + Railway (DB opciono)  
**CI/CD:** GitHub Actions + pre-commit hooks + tests automáticos

---

*Extracto de código fuente para registro de obra informática ante la DNDA*  
*Todos los derechos reservados — Julieta Arrazate — Junio 2026*
