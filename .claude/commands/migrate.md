# /migrate — Crear y aplicar migración de base de datos

Pasos para crear una migración segura:

1. Leer `database/CLAUDE.md` para entender el esquema actual
2. Verificar que los modelos SQLAlchemy estén actualizados
3. Generar la migración: `cd backend && alembic revision --autogenerate -m "descripcion"`
4. Revisar el archivo generado en `database/migrations/versions/`
5. Verificar que el `upgrade()` y `downgrade()` sean correctos
6. Aplicar: `alembic upgrade head`
7. Actualizar `database/CLAUDE.md` con los cambios al esquema

⚠️ NUNCA modificar migraciones ya aplicadas en producción.
