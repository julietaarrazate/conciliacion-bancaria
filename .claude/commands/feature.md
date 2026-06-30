# /feature — Implementar una feature nueva siguiendo el patrón

Propósito: agregar funcionalidad nueva respetando el patrón establecido del repo (modelo +
service + router 3 capas + migración + safety net + tests + página + nav gateada, opt-in por org),
sin romper reglas transversales.

## Pasos

1. **Encuadrar** con la plantilla [`.claude/templates/feature_template.md`](../templates/feature_template.md):
   problema, alcance, archivos a tocar, criterios de aceptación, test plan. Correr antes el
   flujo [`/analyze`](./analyze.md) sobre el área afectada.
2. **Elegir el playbook** según el tamaño:
   - Módulo nuevo completo → [`docs/playbooks/NEW_MODULE.md`](../../docs/playbooks/NEW_MODULE.md).
   - Endpoint dentro de un módulo existente → [`docs/playbooks/NEW_API_ENDPOINT.md`](../../docs/playbooks/NEW_API_ENDPOINT.md).
   - Variantes: banco nuevo, parser, reporte, módulo contable → ver `docs/playbooks/`.
3. **Implementar backend** (router fino, lógica en el service):
   - Montos en `Decimal`; fechas de negocio con `hoy_art()`/`now_art()`.
   - Multi-tenant: `org_id` validado con `can_switch_org`, toda query filtra por `organizacion_id`.
     Org A solo aditivo.
   - Permisos en 3 capas (`require_permission(...)` donde mute o sea sensible).
   - Migración Alembic **+** safety-net idempotente equivalente en `main.py`
     (`CREATE TABLE/ADD COLUMN IF NOT EXISTS`). Opt-in por org, no hardcodeado.
4. **Tests backend**: caso feliz + aislamiento de otra org (404) + 403 sin permiso + borrado con
   FKs si hay `DELETE`.
5. **Implementar frontend**: página, ruta gateada por permiso en `App.tsx`, item en `Layout.tsx`,
   endpoints en `services/api.ts`. `localIsoDate()` para fechas, `parseMonto()` para montos AR.
   Probar en modo claro y oscuro.
6. **Recorrer** [`.claude/checklists/feature_checklist.md`](../checklists/feature_checklist.md) entero
   antes de dar por cerrado.
7. **Docs**: correr [`/docs`](./docs.md) para sincronizar `docs/` si cambió arquitectura/API/DB.

## Verificación

```bash
cd backend && python -m pytest -q
cd frontend && npx tsc --noEmit && npm run build
```

## PR

Rama `claude/...` → PR squash a `main`. Commits con
`git commit --author="Julieta Arrazate <julietaarrazate@gmail.com>"` (Vercel bloquea otros autores).
Commit por sub-paso, no al final.
