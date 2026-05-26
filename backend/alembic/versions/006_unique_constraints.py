"""006_unique_constraints — protege contra duplicados por concurrencia

Tres unique constraints que cubren bugs reales de race conditions:
- asientos.(modulo, referencia_id, organizacion_id): el motor contable
  no crea dos veces el mismo asiento aunque dos requests entren a la vez.
- arqueos_diarios.(organizacion_id, fecha): un solo arqueo por dia y org.
- extractos_bancarios.(fingerprint, organizacion_id): no se sube dos veces
  el mismo archivo en paralelo dentro de la misma org.

Usa indices unique parciales en vez de UniqueConstraint para evitar romper
data legacy con NULLs.
"""

from alembic import op

revision = "006"
down_revision = "005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Asientos: unique de (modulo, referencia_id, organizacion_id) cuando todos no son NULL
    op.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS uq_asiento_modulo_ref_org
        ON asientos (modulo, referencia_id, organizacion_id)
        WHERE modulo IS NOT NULL AND referencia_id IS NOT NULL AND organizacion_id IS NOT NULL
    """)
    # ArqueoDiario: un arqueo por dia + org
    op.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS uq_arqueo_org_fecha
        ON arqueos_diarios (organizacion_id, fecha)
    """)
    # ExtractoBancario: fingerprint unico por org (no global, para que orgs
    # distintas puedan tener archivos con el mismo fingerprint coincidente)
    op.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS uq_extracto_fp_org
        ON extractos_bancarios (fingerprint, organizacion_id)
        WHERE fingerprint IS NOT NULL
    """)


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS uq_extracto_fp_org")
    op.execute("DROP INDEX IF EXISTS uq_arqueo_org_fecha")
    op.execute("DROP INDEX IF EXISTS uq_asiento_modulo_ref_org")
