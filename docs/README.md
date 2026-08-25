# Documentación de Cuadra

Documentación técnica y de producto de **Cuadra** — conciliación bancaria y gestión financiera
multi-tenant. Esta carpeta es la **fuente de verdad arquitectónica** del proyecto; describe el
estado actual del sistema basándose exclusivamente en el código.

> Para contexto operativo y reglas de trabajo con Claude, ver [`../CLAUDE.md`](../CLAUDE.md).
> Para el historial de versiones, [`../CHANGELOG.md`](../CHANGELOG.md). Para bugs recurrentes,
> [`../BUGS.md`](../BUGS.md).

## Índice

### Panorama general
- [ESTADO_SISTEMA.md](./ESTADO_SISTEMA.md) — snapshot completo y autocontenido de todo lo construido (módulos, deuda técnica, pendientes); pensado para revisión externa

### Arquitectura (`architecture/`)
- [ARCHITECTURE.md](./architecture/ARCHITECTURE.md) — stack, capas, topología de producción, ciclo de request, schedulers
- [SYSTEM_MAP.md](./architecture/SYSTEM_MAP.md) — mapa módulo → router → service → modelo → página
- [DOMAIN_MODEL.md](./architecture/DOMAIN_MODEL.md) — entidades y relaciones (ERD)
- [EVENTS.md](./architecture/EVENTS.md) — eventos de dominio y efectos secundarios
- [ACCOUNTING_ENGINE.md](./architecture/ACCOUNTING_ENGINE.md) — motor contable de partida doble

### Negocio (`business/`)
- [PRODUCT_BIBLE.md](./business/PRODUCT_BIBLE.md) — qué es Cuadra, para quién, módulos
- [BUSINESS_RULES.md](./business/BUSINESS_RULES.md) — reglas (scoring de conciliación, dedup, impuestos)
- [WORKFLOWS.md](./business/WORKFLOWS.md) — flujos de usuario end-to-end

### IA (`ai/`)
- [AI_GUIDE.md](./ai/AI_GUIDE.md) — asistente Gemini (chat, OCR, voz)

### API (`api/`)
- [API_RULES.md](./api/API_RULES.md) — convenciones REST (org_id, permisos, paginación, errores)

### Base de datos (`database/`)
- [DATABASE_RULES.md](./database/DATABASE_RULES.md) — Decimal, soft delete, migraciones + safety nets, índices

### Seguridad (`security/`)
- [SECURITY_MODEL.md](./security/SECURITY_MODEL.md) — auth, roles/permisos, multi-tenant, 2FA, cifrado

### UX (`ux/`)
- [UX_RULES.md](./ux/UX_RULES.md) — dark mode, PWA, lock/PIN, toasts, fechas locales
- [DESIGN_SYSTEM.md](./ux/DESIGN_SYSTEM.md) — tokens de diseño, paleta, tipografía, componentes

### Decisiones (`adr/`)
- [DECISIONS.md](./adr/DECISIONS.md) — registro de decisiones arquitectónicas (ADR)

### Playbooks (`playbooks/`) — guías paso a paso
- [LOOPS.md](./playbooks/LOOPS.md) — ciclos de trabajo permanentes (Feature/Bug/Refactor/… con ruteo por modelo)
- [NEW_MODULE.md](./playbooks/NEW_MODULE.md) — agregar un módulo
- [NEW_API_ENDPOINT.md](./playbooks/NEW_API_ENDPOINT.md) — agregar un endpoint
- [NEW_BANK.md](./playbooks/NEW_BANK.md) — soportar un banco nuevo
- [NEW_PARSER.md](./playbooks/NEW_PARSER.md) — extender el parser de Excel
- [NEW_REPORT.md](./playbooks/NEW_REPORT.md) — agregar un reporte/export
- [NEW_ACCOUNTING_MODULE.md](./playbooks/NEW_ACCOUNTING_MODULE.md) — integrar con el motor contable
- [RESET_OPERATIVO.md](./playbooks/RESET_OPERATIVO.md) — vaciar lo transaccional (arrancar limpio) conservando maestros

## Convención

Si encontrás una discrepancia entre un documento y el código, no la tapes: agregala a la sección
`## Pendiente de revisar` del documento correspondiente. La doc describe el código tal como está,
no como debería ser.
