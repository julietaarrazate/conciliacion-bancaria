"""Plan de cuentas jerárquico del contador (4 niveles) + numeración correlativa de asientos

Revision ID: 003
Revises: 002
Create Date: 2026-05-21

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = '003'
down_revision: Union[str, None] = '002'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Limpiar el seed plano de la 002 (todavía no hay asientos creados sobre estas cuentas)
    op.execute("DELETE FROM lineas_asiento")
    op.execute("DELETE FROM asientos_contables")
    op.execute("DELETE FROM cuentas_contables")

    # Agregar columnas jerárquicas
    op.add_column('cuentas_contables', sa.Column('nivel', sa.Integer(), nullable=False, server_default='1'))
    op.add_column('cuentas_contables', sa.Column('parent_id', sa.Integer(), nullable=True))
    op.add_column('cuentas_contables', sa.Column('imputable', sa.Boolean(), nullable=False, server_default='false'))
    op.add_column('cuentas_contables', sa.Column('cliente_id', sa.Integer(), nullable=True))
    op.create_foreign_key('fk_cc_parent', 'cuentas_contables', 'cuentas_contables', ['parent_id'], ['id'])
    op.create_foreign_key('fk_cc_cliente', 'cuentas_contables', 'clientes', ['cliente_id'], ['id'])
    op.create_index('ix_cc_parent_id', 'cuentas_contables', ['parent_id'])
    op.create_index('ix_cc_cliente_id', 'cuentas_contables', ['cliente_id'])

    # Cambiar UNIQUE de nombre por compuesto (nombre, parent_id) — permite "Banco" en varios contextos si hiciera falta
    op.drop_constraint('cuentas_contables_nombre_key', 'cuentas_contables', type_='unique')

    # Numeración correlativa de asientos
    op.add_column(
        'asientos_contables',
        sa.Column('numero', sa.Integer(), nullable=False, server_default='0'),
    )
    op.create_index('ix_asientos_numero', 'asientos_contables', ['numero'])

    # Tabla auxiliar para correlativos por ejercicio
    op.create_table(
        'secuencias',
        sa.Column('clave', sa.String(50), nullable=False),
        sa.Column('valor', sa.Integer(), nullable=False, server_default='0'),
        sa.PrimaryKeyConstraint('clave'),
    )
    op.execute("INSERT INTO secuencias (clave, valor) VALUES ('asiento', 0)")

    # === SEED del plan de cuentas (jerárquico) ===
    # Construido en Python para resolver parent_id correctamente
    plan = [
        # (codigo, nombre, tipo, naturaleza, nivel, parent_codigo, imputable)
        ("1-0-0-0", "Activo",              "activo",  "deudora",   1, None,      False),
        ("1-1-0-0", "Activo Corriente",    "activo",  "deudora",   2, "1-0-0-0", False),
        ("1-1-1-0", "Disponibilidades",    "activo",  "deudora",   3, "1-1-0-0", False),
        ("1-1-1-1", "Caja chica",          "activo",  "deudora",   4, "1-1-1-0", True),
        ("1-1-1-2", "Efectivo",            "activo",  "deudora",   4, "1-1-1-0", True),
        ("1-1-1-3", "Banco",               "activo",  "deudora",   4, "1-1-1-0", True),
        ("1-1-2-0", "Creditos",            "activo",  "deudora",   3, "1-1-0-0", True),  # imputable por defecto (cheques)
        ("1-2-0-0", "Activo no corriente", "activo",  "deudora",   2, "1-0-0-0", False),
        ("1-2-1-0", "Bienes de Uso",       "activo",  "deudora",   3, "1-2-0-0", True),

        ("2-0-0-0", "Pasivo",              "pasivo",  "acreedora", 1, None,      False),
        ("2-1-0-0", "Pasivo Corriente",    "pasivo",  "acreedora", 2, "2-0-0-0", False),
        ("2-1-1-0", "Pasivo a Confirmar",  "pasivo",  "acreedora", 3, "2-1-0-0", False),
        ("2-1-1-1", "No identificado",     "pasivo",  "acreedora", 4, "2-1-1-0", True),
        ("2-1-2-0", "Cliente",             "pasivo",  "acreedora", 3, "2-1-0-0", False),
        ("2-1-2-1", "Green",               "pasivo",  "acreedora", 4, "2-1-2-0", True),
        ("2-1-2-2", "Tucu",                "pasivo",  "acreedora", 4, "2-1-2-0", True),
        ("2-1-2-3", "Alojando",            "pasivo",  "acreedora", 4, "2-1-2-0", True),

        ("3-0-0-0", "Resultado",                "resultado_positivo", "acreedora", 1, None,      False),
        ("3-1-0-0", "Ingresos",                 "resultado_positivo", "acreedora", 2, "3-0-0-0", False),
        ("3-1-1-0", "Comisiones",               "resultado_positivo", "acreedora", 3, "3-1-0-0", True),
        ("3-1-2-0", "Operaciones de cambio",    "resultado_positivo", "acreedora", 3, "3-1-0-0", True),
        ("3-2-0-0", "Gastos",                   "resultado_negativo", "deudora",   2, "3-0-0-0", False),
        ("3-2-1-0", "Impuesto deb y cred",      "resultado_negativo", "deudora",   3, "3-2-0-0", True),
        ("3-2-2-0", "Gastos bancarios",         "resultado_negativo", "deudora",   3, "3-2-0-0", True),
    ]

    conn = op.get_bind()
    id_by_code: dict[str, int] = {}
    for codigo, nombre, tipo, nat, nivel, parent_code, imputable in plan:
        parent_id = id_by_code.get(parent_code) if parent_code else None
        result = conn.execute(
            sa.text(
                "INSERT INTO cuentas_contables (codigo, nombre, tipo, naturaleza, nivel, parent_id, imputable) "
                "VALUES (:codigo, :nombre, :tipo, :naturaleza, :nivel, :parent_id, :imputable) RETURNING id"
            ),
            {
                "codigo": codigo, "nombre": nombre, "tipo": tipo,
                "naturaleza": nat, "nivel": nivel, "parent_id": parent_id,
                "imputable": imputable,
            },
        )
        id_by_code[codigo] = result.scalar_one()

    # Crear sub-cuenta de cliente para cada cliente existente que no sea Green/Tucu/Alojando
    cliente_parent_id = id_by_code["2-1-2-0"]
    cliente_rows = conn.execute(sa.text("SELECT id, nombre FROM clientes ORDER BY id")).all()
    existing_names = {"green", "tucu", "alojando"}
    next_num = 4  # los primeros 3 ya están sembrados
    for cid, nombre in cliente_rows:
        if nombre.lower() in existing_names:
            # Vincular cliente existente con la cuenta sembrada
            conn.execute(
                sa.text("UPDATE cuentas_contables SET cliente_id=:cid WHERE codigo=:codigo"),
                {"cid": cid, "codigo": f"2-1-2-{['green','tucu','alojando'].index(nombre.lower()) + 1}"},
            )
        else:
            codigo = f"2-1-2-{next_num}"
            next_num += 1
            conn.execute(
                sa.text(
                    "INSERT INTO cuentas_contables (codigo, nombre, tipo, naturaleza, nivel, parent_id, imputable, cliente_id) "
                    "VALUES (:codigo, :nombre, 'pasivo', 'acreedora', 4, :pid, true, :cid)"
                ),
                {"codigo": codigo, "nombre": nombre, "pid": cliente_parent_id, "cid": cid},
            )


def downgrade() -> None:
    op.drop_table('secuencias')
    op.drop_index('ix_asientos_numero', table_name='asientos_contables')
    op.drop_column('asientos_contables', 'numero')

    op.drop_index('ix_cc_cliente_id', table_name='cuentas_contables')
    op.drop_index('ix_cc_parent_id', table_name='cuentas_contables')
    op.drop_constraint('fk_cc_cliente', 'cuentas_contables', type_='foreignkey')
    op.drop_constraint('fk_cc_parent', 'cuentas_contables', type_='foreignkey')
    op.drop_column('cuentas_contables', 'cliente_id')
    op.drop_column('cuentas_contables', 'imputable')
    op.drop_column('cuentas_contables', 'parent_id')
    op.drop_column('cuentas_contables', 'nivel')

    op.execute("DELETE FROM cuentas_contables")
