<!-- Plantilla de Pull Request de Cuadra. Completá lo que aplique; borrá lo que no. -->

## Resumen

<!-- Qué cambia y por qué, en 1-3 líneas. -->

## Tipo de cambio

- [ ] 🐛 Fix de bug
- [ ] ✨ Feature
- [ ] ♻️ Refactor (sin cambio de comportamiento)
- [ ] 📝 Documentación
- [ ] ⚙️ Infra / tooling

## Detalle

<!-- Qué archivos/áreas toca. Si hay decisiones de diseño, explicá el porqué. -->

## Checklist

- [ ] `cd backend && python -m pytest -q` en verde
- [ ] `cd frontend && npx tsc --noEmit && npm run build` en verde
- [ ] Montos en `Decimal`/`Numeric`, nunca `float` (ver `BUGS.md`)
- [ ] Multi-tenant: endpoints respetan `org_id` + `can_switch_org` (si aplica)
- [ ] Migración Alembic **+** safety-net en `main.py` (si toca el esquema)
- [ ] No se modifican datos existentes de Org A (`organizacion_id=1`)
- [ ] Sin secretos/keys en el código
- [ ] Documentación de `/docs` actualizada si cambió el comportamiento
- [ ] Commit con autoría `Julieta Arrazate <julietaarrazate@gmail.com>`

## Test plan

<!-- Cómo se probó. Incluí casos límite / mobile si aplica. -->
