"""Safety-net DDL: esquema mínimo que debe existir aunque Alembic no corra.

Segunda fuente de verdad del esquema (la primaria son las migraciones Alembic en
`alembic/versions/`). En Render la migración puede fallar o no ejecutarse; estas
sentencias garantizan que el arranque no se caiga por una columna/tabla/índice
faltante. Se ejecutan en cada startup (ver `main.py::_run_alembic`).

INVARIANTE (verificada en `tests/test_db_safety.py`): **toda** sentencia debe ser
idempotente — segura de re-ejecutar en cada boot y contra una DB ya migrada. En la
práctica: `IF NOT EXISTS` para CREATE/ADD COLUMN/CREATE INDEX, y `IF EXISTS` para
DROP. Un `ALTER TABLE ... ADD COLUMN` sin `IF NOT EXISTS` crashea el arranque en la
segunda corrida — por eso el test lo bloquea en CI.

Al agregar una migración Alembic que toque el esquema base, replicá el cambio acá
(y viceversa) para que ambas fuentes no diverjan. Ver `docs/database/DATABASE_RULES.md`.
"""

# Sentencias DDL idempotentes. Orden = orden de aplicación (respetá dependencias FK).
SAFETY_NET_DDL = [
    "ALTER TABLE clientes ADD COLUMN IF NOT EXISTS porcentaje_comision NUMERIC(5,4)",
    "ALTER TABLE clientes ADD COLUMN IF NOT EXISTS porcentaje_comision_local NUMERIC(5,4)",
    "ALTER TABLE clientes ADD COLUMN IF NOT EXISTS porcentaje_comision_interior NUMERIC(5,4)",
    "ALTER TABLE planillas ADD COLUMN IF NOT EXISTS porcentaje_comision NUMERIC(5,4)",
    "ALTER TABLE cheques ADD COLUMN IF NOT EXISTS porcentaje_comision NUMERIC(5,4)",
    "ALTER TABLE clientes ADD COLUMN IF NOT EXISTS cuenta_contable_id INTEGER REFERENCES plan_cuentas(id)",
    # v3.25 — perfil aprendido del formato de planilla por cliente (pipeline de estandarización)
    "ALTER TABLE clientes ADD COLUMN IF NOT EXISTS mapeo_planilla JSONB",
    "ALTER TABLE users ADD COLUMN IF NOT EXISTS allowed_org_ids JSONB DEFAULT '[]'",
    "ALTER TABLE asientos ADD COLUMN IF NOT EXISTS numero_asiento INTEGER",
    # v3.9.2 — portadores + campos cheque
    "CREATE TABLE IF NOT EXISTS portadores (id SERIAL PRIMARY KEY, organizacion_id INTEGER NOT NULL DEFAULT 1, nombre VARCHAR NOT NULL)",
    "ALTER TABLE cheques ADD COLUMN IF NOT EXISTS portador_id INTEGER REFERENCES portadores(id)",
    "ALTER TABLE cheques ADD COLUMN IF NOT EXISTS librador VARCHAR",
    "ALTER TABLE cheques ADD COLUMN IF NOT EXISTS codigo_postal VARCHAR",
    "ALTER TABLE cheques ADD COLUMN IF NOT EXISTS local_interior VARCHAR",
    "ALTER TABLE cheques ADD COLUMN IF NOT EXISTS fecha_rechazo DATE",
    "ALTER TABLE cheques ADD COLUMN IF NOT EXISTS fisico BOOLEAN DEFAULT FALSE",
    "ALTER TABLE cheques ADD COLUMN IF NOT EXISTS fecha_devolucion DATE",
    "UPDATE cheques SET librador = titular WHERE librador IS NULL AND titular IS NOT NULL",
    "CREATE TABLE IF NOT EXISTS twofa_codes (id SERIAL PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id), code_hash VARCHAR NOT NULL, expires_at TIMESTAMP NOT NULL, used BOOLEAN NOT NULL DEFAULT FALSE, created_at TIMESTAMP DEFAULT NOW())",
    "ALTER TABLE twofa_codes ADD COLUMN IF NOT EXISTS failed_attempts INTEGER NOT NULL DEFAULT 0",
    "CREATE INDEX IF NOT EXISTS ix_egresos_tipo ON egresos (tipo)",
    "CREATE INDEX IF NOT EXISTS ix_egresos_forma_pago ON egresos (forma_pago)",
    "CREATE INDEX IF NOT EXISTS ix_egresos_cliente_id ON egresos (cliente_id)",
    "CREATE INDEX IF NOT EXISTS ix_egresos_org_fecha ON egresos (organizacion_id, fecha DESC)",
    # TAREA 3 — liquidaciones de tarjetas (Visa / Mastercard / Amex)
    "CREATE TABLE IF NOT EXISTS liquidaciones_tarjeta ("
    "id SERIAL PRIMARY KEY, "
    "organizacion_id INTEGER NOT NULL REFERENCES organizaciones(id), "
    "marca VARCHAR NOT NULL, "
    "periodo VARCHAR(7) NOT NULL, "
    "fecha_acreditacion DATE NOT NULL, "
    "monto_bruto NUMERIC(12,2) NOT NULL, "
    "aranceles NUMERIC(12,2) NOT NULL DEFAULT 0, "
    "iva_df NUMERIC(12,2) NOT NULL DEFAULT 0, "
    "percepciones_iibb NUMERIC(12,2) NOT NULL DEFAULT 0, "
    "retenciones NUMERIC(12,2) NOT NULL DEFAULT 0, "
    "neto NUMERIC(12,2) NOT NULL, "
    "estado VARCHAR(20) DEFAULT 'pendiente', "
    "extracto_movimiento_id INTEGER REFERENCES movimientos_banco(id), "
    "archivo_original VARCHAR(255), "
    "asiento_id INTEGER REFERENCES asientos(id), "
    "notas TEXT, "
    "usuario_id INTEGER REFERENCES users(id), "
    "created_at TIMESTAMP DEFAULT NOW(), "
    "deleted_at TIMESTAMP)",
    "CREATE INDEX IF NOT EXISTS ix_liq_tarjeta_org ON liquidaciones_tarjeta (organizacion_id)",
    "CREATE INDEX IF NOT EXISTS ix_liq_tarjeta_org_fecha ON liquidaciones_tarjeta (organizacion_id, fecha_acreditacion DESC)",
    # migración 012 — índices críticos para módulo contabilidad (Libro Diario, Cuentas Corrientes)
    # asientos.organizacion_id aparece en TODOS los filtros contables; sin índice → full scan
    "CREATE INDEX IF NOT EXISTS idx_asiento_org ON asientos(organizacion_id)",
    "CREATE INDEX IF NOT EXISTS idx_asiento_org_fecha ON asientos(organizacion_id, fecha)",
    "CREATE INDEX IF NOT EXISTS idx_asiento_modulo ON asientos(modulo)",
    # asiento_detalle: asiento_id y cuenta_id son FK de JOIN críticos sin índice
    "CREATE INDEX IF NOT EXISTS idx_asdet_asiento ON asiento_detalle(asiento_id)",
    "CREATE INDEX IF NOT EXISTS idx_asdet_cuenta ON asiento_detalle(cuenta_id)",
    "CREATE INDEX IF NOT EXISTS idx_asdet_cuenta_asiento ON asiento_detalle(cuenta_id, asiento_id)",
    # uq_extracto_fp_org: excluir extractos borrados (soft delete) del índice
    # único, así borrar y re-subir el mismo archivo crea uno nuevo en vez de
    # chocar contra la fila borrada (migración 020). DROP+CREATE para reemplazar
    # la definición vieja de la migración 006.
    "DROP INDEX IF EXISTS uq_extracto_fp_org",
    "CREATE UNIQUE INDEX IF NOT EXISTS uq_extracto_fp_org ON extractos_bancarios (fingerprint, organizacion_id) WHERE fingerprint IS NOT NULL AND deleted_at IS NULL",
    # módulo IVA Proyección y DDJJ — tasa de IVA por cuenta + snapshot por período
    "ALTER TABLE plan_cuentas ADD COLUMN IF NOT EXISTS tasa_iva NUMERIC(5,4)",
    "CREATE TABLE IF NOT EXISTS proyecciones_iva ("
    "id SERIAL PRIMARY KEY, "
    "organizacion_id INTEGER NOT NULL REFERENCES organizaciones(id), "
    "periodo VARCHAR(7) NOT NULL, "
    "debito_fiscal NUMERIC(12,2) NOT NULL DEFAULT 0, "
    "credito_fiscal NUMERIC(12,2) NOT NULL DEFAULT 0, "
    "saldo NUMERIC(12,2) NOT NULL DEFAULT 0, "
    "estado VARCHAR(20) NOT NULL DEFAULT 'proyectado', "
    "fecha_presentacion TIMESTAMP, "
    "detalle JSONB, "
    "created_at TIMESTAMP DEFAULT NOW(), "
    "updated_at TIMESTAMP DEFAULT NOW(), "
    "CONSTRAINT uq_proyeccion_iva_org_periodo UNIQUE (organizacion_id, periodo))",
    "CREATE INDEX IF NOT EXISTS ix_proyeccion_iva_org ON proyecciones_iva (organizacion_id)",
    # módulo Control Semestral Monotributo — categorías, config opt-in y snapshots
    "CREATE TABLE IF NOT EXISTS categorias_monotributo ("
    "id SERIAL PRIMARY KEY, "
    "organizacion_id INTEGER NOT NULL REFERENCES organizaciones(id), "
    "categoria VARCHAR(2) NOT NULL, "
    "tipo_actividad VARCHAR(20) NOT NULL, "
    "limite_anual NUMERIC(12,2) NOT NULL DEFAULT 0, "
    "orden INTEGER NOT NULL DEFAULT 0, "
    "created_at TIMESTAMP DEFAULT NOW(), "
    "updated_at TIMESTAMP DEFAULT NOW(), "
    "CONSTRAINT uq_categoria_monotributo_org_cat_tipo "
    "UNIQUE (organizacion_id, categoria, tipo_actividad))",
    "CREATE INDEX IF NOT EXISTS ix_categoria_monotributo_org ON categorias_monotributo (organizacion_id)",
    "CREATE TABLE IF NOT EXISTS monotributo_config ("
    "id SERIAL PRIMARY KEY, "
    "organizacion_id INTEGER NOT NULL UNIQUE REFERENCES organizaciones(id), "
    "categoria_actual VARCHAR(2), "
    "tipo_actividad VARCHAR(20) NOT NULL DEFAULT 'servicios', "
    "activo BOOLEAN NOT NULL DEFAULT FALSE, "
    "created_at TIMESTAMP DEFAULT NOW(), "
    "updated_at TIMESTAMP DEFAULT NOW())",
    "CREATE TABLE IF NOT EXISTS controles_monotributo ("
    "id SERIAL PRIMARY KEY, "
    "organizacion_id INTEGER NOT NULL REFERENCES organizaciones(id), "
    "periodo VARCHAR(7) NOT NULL, "
    "fecha_corte DATE NOT NULL, "
    "ingresos_12m NUMERIC(12,2) NOT NULL DEFAULT 0, "
    "categoria_actual VARCHAR(2), "
    "limite_categoria_actual NUMERIC(12,2) NOT NULL DEFAULT 0, "
    "porcentaje_uso NUMERIC(6,2) NOT NULL DEFAULT 0, "
    "categoria_sugerida VARCHAR(2), "
    "excede BOOLEAN NOT NULL DEFAULT FALSE, "
    "estado VARCHAR(20) NOT NULL DEFAULT 'pendiente', "
    "fecha_revision TIMESTAMP, "
    "detalle JSONB, "
    "created_at TIMESTAMP DEFAULT NOW(), "
    "updated_at TIMESTAMP DEFAULT NOW(), "
    "CONSTRAINT uq_control_monotributo_org_periodo "
    "UNIQUE (organizacion_id, periodo))",
    "CREATE INDEX IF NOT EXISTS ix_control_monotributo_org ON controles_monotributo (organizacion_id)",
    # módulo Ingresos Brutos (IIBB) y Convenio Multilateral — jurisdicciones, config opt-in y snapshots
    "CREATE TABLE IF NOT EXISTS jurisdicciones_iibb ("
    "id SERIAL PRIMARY KEY, "
    "organizacion_id INTEGER NOT NULL REFERENCES organizaciones(id), "
    "nombre VARCHAR(80) NOT NULL, "
    "alicuota NUMERIC(5,4) NOT NULL DEFAULT 0, "
    "coeficiente_distribucion NUMERIC(5,4) NOT NULL DEFAULT 0, "
    "activa BOOLEAN NOT NULL DEFAULT TRUE, "
    "orden INTEGER NOT NULL DEFAULT 0, "
    "created_at TIMESTAMP DEFAULT NOW(), "
    "updated_at TIMESTAMP DEFAULT NOW(), "
    "CONSTRAINT uq_jurisdiccion_iibb_org_nombre UNIQUE (organizacion_id, nombre))",
    "CREATE INDEX IF NOT EXISTS ix_jurisdiccion_iibb_org ON jurisdicciones_iibb (organizacion_id)",
    "CREATE TABLE IF NOT EXISTS iibb_config ("
    "id SERIAL PRIMARY KEY, "
    "organizacion_id INTEGER NOT NULL UNIQUE REFERENCES organizaciones(id), "
    "activo BOOLEAN NOT NULL DEFAULT FALSE, "
    "modo VARCHAR(24) NOT NULL DEFAULT 'simple', "
    "jurisdiccion_unica_id INTEGER REFERENCES jurisdicciones_iibb(id), "
    "created_at TIMESTAMP DEFAULT NOW(), "
    "updated_at TIMESTAMP DEFAULT NOW())",
    "CREATE TABLE IF NOT EXISTS proyecciones_iibb ("
    "id SERIAL PRIMARY KEY, "
    "organizacion_id INTEGER NOT NULL REFERENCES organizaciones(id), "
    "periodo VARCHAR(7) NOT NULL, "
    "ingreso_total NUMERIC(12,2) NOT NULL DEFAULT 0, "
    "impuesto_total NUMERIC(12,2) NOT NULL DEFAULT 0, "
    "detalle_por_jurisdiccion JSONB, "
    "estado VARCHAR(20) NOT NULL DEFAULT 'proyectado', "
    "fecha_presentacion TIMESTAMP, "
    "created_at TIMESTAMP DEFAULT NOW(), "
    "updated_at TIMESTAMP DEFAULT NOW(), "
    "CONSTRAINT uq_proyeccion_iibb_org_periodo UNIQUE (organizacion_id, periodo))",
    "CREATE INDEX IF NOT EXISTS ix_proyeccion_iibb_org ON proyecciones_iibb (organizacion_id)",
    # módulo Liquidador de Sueldos y F931 — convenios, categorías, empleados, config y liquidaciones
    "CREATE TABLE IF NOT EXISTS convenios_colectivos ("
    "id SERIAL PRIMARY KEY, "
    "organizacion_id INTEGER NOT NULL REFERENCES organizaciones(id), "
    "nombre VARCHAR(120) NOT NULL, "
    "descripcion VARCHAR(255), "
    "activo BOOLEAN NOT NULL DEFAULT TRUE, "
    "created_at TIMESTAMP DEFAULT NOW(), "
    "updated_at TIMESTAMP DEFAULT NOW(), "
    "CONSTRAINT uq_convenio_org_nombre UNIQUE (organizacion_id, nombre))",
    "CREATE INDEX IF NOT EXISTS ix_convenio_org ON convenios_colectivos (organizacion_id)",
    "CREATE TABLE IF NOT EXISTS categorias_convenio ("
    "id SERIAL PRIMARY KEY, "
    "convenio_id INTEGER NOT NULL REFERENCES convenios_colectivos(id), "
    "nombre VARCHAR(120) NOT NULL, "
    "sueldo_basico NUMERIC(12,2) NOT NULL DEFAULT 0, "
    "orden INTEGER NOT NULL DEFAULT 0, "
    "created_at TIMESTAMP DEFAULT NOW(), "
    "updated_at TIMESTAMP DEFAULT NOW(), "
    "CONSTRAINT uq_categoria_convenio_nombre UNIQUE (convenio_id, nombre))",
    "CREATE INDEX IF NOT EXISTS ix_categoria_convenio ON categorias_convenio (convenio_id)",
    "CREATE TABLE IF NOT EXISTS empleados ("
    "id SERIAL PRIMARY KEY, "
    "organizacion_id INTEGER NOT NULL REFERENCES organizaciones(id), "
    "nombre VARCHAR(160) NOT NULL, "
    "cuil VARCHAR(13), "
    "convenio_id INTEGER REFERENCES convenios_colectivos(id), "
    "categoria_id INTEGER REFERENCES categorias_convenio(id), "
    "fecha_ingreso DATE, "
    "sueldo_basico NUMERIC(12,2), "
    "cargas_familia INTEGER NOT NULL DEFAULT 0, "
    "activo BOOLEAN NOT NULL DEFAULT TRUE, "
    "deleted_at TIMESTAMP, "
    "created_at TIMESTAMP DEFAULT NOW(), "
    "updated_at TIMESTAMP DEFAULT NOW())",
    "CREATE INDEX IF NOT EXISTS ix_empleado_org ON empleados (organizacion_id)",
    "CREATE INDEX IF NOT EXISTS ix_empleado_deleted ON empleados (deleted_at)",
    "CREATE TABLE IF NOT EXISTS config_sueldos ("
    "id SERIAL PRIMARY KEY, "
    "organizacion_id INTEGER NOT NULL UNIQUE REFERENCES organizaciones(id), "
    "activo BOOLEAN NOT NULL DEFAULT FALSE, "
    "aporte_jubilacion NUMERIC(5,4) NOT NULL DEFAULT 0, "
    "aporte_inssjp NUMERIC(5,4) NOT NULL DEFAULT 0, "
    "aporte_obra_social NUMERIC(5,4) NOT NULL DEFAULT 0, "
    "contrib_jubilacion NUMERIC(5,4) NOT NULL DEFAULT 0, "
    "contrib_inssjp NUMERIC(5,4) NOT NULL DEFAULT 0, "
    "contrib_obra_social NUMERIC(5,4) NOT NULL DEFAULT 0, "
    "contrib_asig_fam NUMERIC(5,4) NOT NULL DEFAULT 0, "
    "contrib_fondo_desempleo NUMERIC(5,4) NOT NULL DEFAULT 0, "
    "alicuota_art NUMERIC(5,4) NOT NULL DEFAULT 0, "
    "created_at TIMESTAMP DEFAULT NOW(), "
    "updated_at TIMESTAMP DEFAULT NOW())",
    "CREATE TABLE IF NOT EXISTS liquidaciones_sueldo ("
    "id SERIAL PRIMARY KEY, "
    "organizacion_id INTEGER NOT NULL REFERENCES organizaciones(id), "
    "periodo VARCHAR(7) NOT NULL, "
    "estado VARCHAR(20) NOT NULL DEFAULT 'borrador', "
    "total_bruto NUMERIC(12,2) NOT NULL DEFAULT 0, "
    "total_aportes NUMERIC(12,2) NOT NULL DEFAULT 0, "
    "total_contribuciones NUMERIC(12,2) NOT NULL DEFAULT 0, "
    "total_neto NUMERIC(12,2) NOT NULL DEFAULT 0, "
    "fecha_aprobacion TIMESTAMP, "
    "fecha_presentacion TIMESTAMP, "
    "created_at TIMESTAMP DEFAULT NOW(), "
    "updated_at TIMESTAMP DEFAULT NOW(), "
    "CONSTRAINT uq_liquidacion_sueldo_org_periodo UNIQUE (organizacion_id, periodo))",
    "CREATE INDEX IF NOT EXISTS ix_liquidacion_sueldo_org ON liquidaciones_sueldo (organizacion_id)",
    "CREATE TABLE IF NOT EXISTS detalles_liquidacion_sueldo ("
    "id SERIAL PRIMARY KEY, "
    "liquidacion_periodo_id INTEGER NOT NULL REFERENCES liquidaciones_sueldo(id), "
    "empleado_id INTEGER REFERENCES empleados(id), "
    "sueldo_bruto NUMERIC(12,2) NOT NULL DEFAULT 0, "
    "sac_proporcional NUMERIC(12,2) NOT NULL DEFAULT 0, "
    "total_aportes NUMERIC(12,2) NOT NULL DEFAULT 0, "
    "total_contribuciones NUMERIC(12,2) NOT NULL DEFAULT 0, "
    "sueldo_neto NUMERIC(12,2) NOT NULL DEFAULT 0, "
    "detalle_json JSONB, "
    "created_at TIMESTAMP DEFAULT NOW())",
    "CREATE INDEX IF NOT EXISTS ix_detalle_liq_sueldo ON detalles_liquidacion_sueldo (liquidacion_periodo_id)",
    # Retención de Ganancias 4ta categoría (opt-in, ver migración 017)
    "ALTER TABLE config_sueldos ADD COLUMN IF NOT EXISTS ganancias_activo BOOLEAN NOT NULL DEFAULT FALSE",
    "ALTER TABLE config_sueldos ADD COLUMN IF NOT EXISTS minimo_no_imponible NUMERIC(12,2) NOT NULL DEFAULT 0",
    "ALTER TABLE config_sueldos ADD COLUMN IF NOT EXISTS deduccion_especial NUMERIC(12,2) NOT NULL DEFAULT 0",
    "ALTER TABLE detalles_liquidacion_sueldo ADD COLUMN IF NOT EXISTS retencion_ganancias NUMERIC(12,2) NOT NULL DEFAULT 0",
    "CREATE TABLE IF NOT EXISTS escala_ganancias ("
    "id SERIAL PRIMARY KEY, "
    "organizacion_id INTEGER NOT NULL REFERENCES organizaciones(id), "
    "tramo_desde NUMERIC(14,2) NOT NULL DEFAULT 0, "
    "tramo_hasta NUMERIC(14,2), "
    "alicuota NUMERIC(5,4) NOT NULL DEFAULT 0, "
    "monto_fijo NUMERIC(12,2) NOT NULL DEFAULT 0, "
    "created_at TIMESTAMP DEFAULT NOW(), "
    "updated_at TIMESTAMP DEFAULT NOW())",
    "CREATE INDEX IF NOT EXISTS ix_escala_ganancias_org ON escala_ganancias (organizacion_id)",
    # Total de retención de Ganancias en el período (contrapartida 2-1-6-0, ver migración 018)
    "ALTER TABLE liquidaciones_sueldo ADD COLUMN IF NOT EXISTS total_retencion_ganancias NUMERIC(12,2) NOT NULL DEFAULT 0",
    # ARCA (ex-AFIP) — facturación electrónica, integración propia WSFEv1/WSAA (ver migración 019)
    "CREATE TABLE IF NOT EXISTS arca_config ("
    "id SERIAL PRIMARY KEY, "
    "organizacion_id INTEGER NOT NULL UNIQUE REFERENCES organizaciones(id), "
    "cuit VARCHAR(11), "
    "ambiente VARCHAR(20) NOT NULL DEFAULT 'homologacion', "
    "punto_venta INTEGER NOT NULL DEFAULT 1, "
    "activo BOOLEAN NOT NULL DEFAULT FALSE, "
    "certificado_enc TEXT, "
    "clave_privada_enc TEXT, "
    "certificado_subido_en TIMESTAMP, "
    "ultimo_token_enc TEXT, "
    "ultimo_sign_enc TEXT, "
    "token_expira TIMESTAMP, "
    "created_at TIMESTAMP DEFAULT NOW(), "
    "updated_at TIMESTAMP DEFAULT NOW())",
    "CREATE TABLE IF NOT EXISTS comprobantes_arca ("
    "id SERIAL PRIMARY KEY, "
    "organizacion_id INTEGER NOT NULL REFERENCES organizaciones(id), "
    "cliente_id INTEGER REFERENCES clientes(id), "
    "tipo_comprobante INTEGER NOT NULL, "
    "punto_venta INTEGER NOT NULL, "
    "numero INTEGER, "
    "concepto INTEGER NOT NULL DEFAULT 1, "
    "doc_tipo INTEGER NOT NULL DEFAULT 99, "
    "doc_nro VARCHAR(11), "
    "fecha_emision DATE NOT NULL, "
    "fecha_serv_desde DATE, "
    "fecha_serv_hasta DATE, "
    "fecha_vto_pago DATE, "
    "importe_neto NUMERIC(12,2) NOT NULL DEFAULT 0, "
    "importe_iva NUMERIC(12,2) NOT NULL DEFAULT 0, "
    "importe_total NUMERIC(12,2) NOT NULL DEFAULT 0, "
    "cae VARCHAR(20), "
    "cae_vencimiento DATE, "
    "estado VARCHAR(20) NOT NULL DEFAULT 'borrador', "
    "error_detalle TEXT, "
    "referencia_planilla_id INTEGER REFERENCES planillas(id), "
    "asiento_id INTEGER REFERENCES asientos(id), "
    "usuario_id INTEGER REFERENCES users(id), "
    "created_at TIMESTAMP DEFAULT NOW(), "
    "updated_at TIMESTAMP DEFAULT NOW(), "
    "CONSTRAINT uq_comprobante_arca_org_pv_tipo_numero UNIQUE (organizacion_id, punto_venta, tipo_comprobante, numero))",
    # Por si la tabla ya existía sin estas 3 columnas (deploy parcial de la migración 019)
    "ALTER TABLE comprobantes_arca ADD COLUMN IF NOT EXISTS fecha_serv_desde DATE",
    "ALTER TABLE comprobantes_arca ADD COLUMN IF NOT EXISTS fecha_serv_hasta DATE",
    "ALTER TABLE comprobantes_arca ADD COLUMN IF NOT EXISTS fecha_vto_pago DATE",
    "CREATE INDEX IF NOT EXISTS ix_arca_config_org ON arca_config (organizacion_id)",
    "CREATE INDEX IF NOT EXISTS ix_comprobantes_arca_org ON comprobantes_arca (organizacion_id)",
    "CREATE INDEX IF NOT EXISTS ix_comprobantes_arca_cliente ON comprobantes_arca (cliente_id)",
    # módulo Liquidación REAL de IVA (Excel "Mis Comprobantes" de ARCA) — staging + snapshot mensual
    "CREATE TABLE IF NOT EXISTS comprobantes_iva ("
    "id SERIAL PRIMARY KEY, "
    "organizacion_id INTEGER NOT NULL REFERENCES organizaciones(id), "
    "direccion VARCHAR(10) NOT NULL, "
    "periodo VARCHAR(7) NOT NULL, "
    "fecha DATE NOT NULL, "
    "tipo_codigo INTEGER NOT NULL, "
    "tipo_desc VARCHAR(80), "
    "punto_venta INTEGER, "
    "numero INTEGER, "
    "cuit_contraparte VARCHAR(20), "
    "denominacion VARCHAR(255), "
    "neto_gravado_total NUMERIC(14,2) NOT NULL DEFAULT 0, "
    "total_iva NUMERIC(14,2) NOT NULL DEFAULT 0, "
    "imp_total NUMERIC(14,2) NOT NULL DEFAULT 0, "
    "detalle_alicuotas JSONB, "
    "incluido BOOLEAN NOT NULL DEFAULT TRUE, "
    "archivo_origen VARCHAR(255), "
    "created_at TIMESTAMP DEFAULT NOW(), "
    "CONSTRAINT uq_comprobante_iva_dedup UNIQUE "
    "(organizacion_id, direccion, tipo_codigo, punto_venta, numero, cuit_contraparte))",
    "CREATE INDEX IF NOT EXISTS ix_comprobante_iva_org ON comprobantes_iva (organizacion_id)",
    "CREATE INDEX IF NOT EXISTS ix_comprobante_iva_org_periodo ON comprobantes_iva (organizacion_id, periodo)",
    "CREATE TABLE IF NOT EXISTS liquidaciones_iva ("
    "id SERIAL PRIMARY KEY, "
    "organizacion_id INTEGER NOT NULL REFERENCES organizaciones(id), "
    "periodo VARCHAR(7) NOT NULL, "
    "debito_fiscal NUMERIC(14,2) NOT NULL DEFAULT 0, "
    "credito_fiscal NUMERIC(14,2) NOT NULL DEFAULT 0, "
    "tecnico_periodo NUMERIC(14,2) NOT NULL DEFAULT 0, "
    "saldo_tecnico_anterior NUMERIC(14,2) NOT NULL DEFAULT 0, "
    "saldo_tecnico_nuevo NUMERIC(14,2) NOT NULL DEFAULT 0, "
    "retenciones NUMERIC(14,2) NOT NULL DEFAULT 0, "
    "percepciones NUMERIC(14,2) NOT NULL DEFAULT 0, "
    "saldo_libre_anterior NUMERIC(14,2) NOT NULL DEFAULT 0, "
    "saldo_libre_nuevo NUMERIC(14,2) NOT NULL DEFAULT 0, "
    "saldo_a_pagar NUMERIC(14,2) NOT NULL DEFAULT 0, "
    "cant_emitidos INTEGER NOT NULL DEFAULT 0, "
    "cant_recibidos INTEGER NOT NULL DEFAULT 0, "
    "estado VARCHAR(20) NOT NULL DEFAULT 'borrador', "
    "fecha_presentacion TIMESTAMP, "
    "created_at TIMESTAMP DEFAULT NOW(), "
    "updated_at TIMESTAMP DEFAULT NOW(), "
    "CONSTRAINT uq_liquidacion_iva_org_periodo UNIQUE (organizacion_id, periodo))",
    "CREATE INDEX IF NOT EXISTS ix_liquidacion_iva_org ON liquidaciones_iva (organizacion_id)",
]
