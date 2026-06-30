# /analyze — Analizar una parte del sistema antes de tocarla

Propósito: entender en profundidad un área del código (módulo, endpoint, parser, motor)
y mapear lo que **no se puede romper** ANTES de proponer o escribir cambios. Salida: un
resumen accionable, no un parche.

## Pasos

1. **Leer la doc relevante primero** (no el código a ciegas). Punto de entrada:
   [`docs/README.md`](../../docs/README.md) → el índice apunta al doc del área. Mínimos:
   - Arquitectura/ubicación → [`docs/architecture/SYSTEM_MAP.md`](../../docs/architecture/SYSTEM_MAP.md).
   - Reglas de API → [`docs/api/API_RULES.md`](../../docs/api/API_RULES.md).
   - Reglas de DB → [`docs/database/DATABASE_RULES.md`](../../docs/database/DATABASE_RULES.md).
   - Seguridad/permisos → [`docs/security/SECURITY_MODEL.md`](../../docs/security/SECURITY_MODEL.md).
   - Reglas de negocio → [`docs/business/BUSINESS_RULES.md`](../../docs/business/BUSINESS_RULES.md).
2. **Mapear los archivos afectados**: modelo(s), service, router(s) (incluí splits del módulo),
   schema Pydantic, página frontend, `services/api.ts`, `App.tsx`, `Layout.tsx`. Anotar cuáles
   se comparten con otros módulos (`main.py`, `api.ts`, `App.tsx`, `Layout.tsx`) — esos serializan
   el trabajo si se paraleliza.
3. **Identificar las reglas que NO romper** en esa área, citando la fuente:
   - Dinero → `Decimal`/`Numeric(12,2)`, nunca `float` ([`BUGS.md`](../../BUGS.md)).
   - Fechas de negocio → `hoy_art()`/`now_art()` (backend) y `localIsoDate()` (frontend),
     nunca UTC directo ([`BUGS.md`](../../BUGS.md)).
   - Multi-tenant → toda query filtra por `organizacion_id`; `org_id` validado con `can_switch_org`.
   - Org A (`organizacion_id=1`) → solo cambios aditivos, nunca modificar datos existentes.
   - Permisos en 3 capas (router/scope/UI) si el área expone endpoints.
4. **Revisar `BUGS.md`** si el área toca alguno de los temas calientes: fechas, montos (Decimal),
   compartir por WhatsApp, detección de banco, `useEffect`, borrado con FKs, parseo de montos AR.
5. **Buscar tests existentes** del área (`backend/tests/`) para saber qué comportamiento está
   blindado y cuál no.

## Verificación / salida

Entregar un resumen: archivos afectados (rutas absolutas), reglas a respetar con su fuente,
riesgos/bugs recurrentes aplicables, y qué tests cubren hoy el área. No editar código en este
comando — es solo de análisis.
