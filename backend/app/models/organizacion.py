from sqlalchemy import Column, Integer, String, Boolean, JSON
from app.database import Base

CONFIG_DEFAULT = {
    "match_rules": ["monto_cuit"],
    "tolerancia_monto": 0.01,
    "dias_tolerancia_fecha": 0,
    "estados_habilitados": ["pendiente", "ok", "no está", "duplicado", "faltan datos"],
    "requiere_cierre_periodo": False,
    "notificaciones_whatsapp": False,
    "exportar_formato_contador": "excel_actual"
}


class Organizacion(Base):
    __tablename__ = "organizaciones"

    id = Column(Integer, primary_key=True, index=True)
    nombre = Column(String, unique=True, nullable=False, index=True)
    plan = Column(String, default="basic", nullable=False)  # basic / pro
    configuracion = Column(JSON, nullable=False, default=CONFIG_DEFAULT)
    activo = Column(Boolean, default=True)
