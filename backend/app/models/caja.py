from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Date, Boolean, Text, JSON, Numeric
from sqlalchemy.orm import relationship
from datetime import datetime, date
from app.database import Base

# Denominaciones de billetes argentinos
DENOMINACIONES = [20000, 10000, 2000, 1000, 500, 200, 100]


def denominaciones_vacias() -> dict:
    return {str(d): 0 for d in DENOMINACIONES}


class ArqueoDiario(Base):
    __tablename__ = "arqueos_diarios"

    id              = Column(Integer, primary_key=True, index=True)
    organizacion_id = Column(Integer, ForeignKey("organizaciones.id"), nullable=False, index=True)
    fecha           = Column(Date, nullable=False, index=True)

    saldo_inicial   = Column(Numeric(12, 2), default=0)   # arrastrado del dia anterior
    pesos_agregados = Column(Numeric(12, 2), default=0)   # efectivo que le dan para pagar mas egresos
    ingresos        = Column(Numeric(12, 2), default=0)   # clientes que traen plata

    # Billetes fisicos: {"20000": 1500, "10000": 1419, "2000": 408, ...}
    denominaciones  = Column(JSON, default=denominaciones_vacias)

    cerrado         = Column(Boolean, default=False)
    notas           = Column(Text, nullable=True)

    creado_por      = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at      = Column(DateTime, default=datetime.utcnow)
    updated_at      = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    organizacion    = relationship("Organizacion", foreign_keys=[organizacion_id])
    creador         = relationship("User", foreign_keys=[creado_por])
    # Egresos en efectivo del día (reemplaza la vieja relación con OrdenDePago)
    egresos         = relationship("Egreso", back_populates="arqueo", foreign_keys="Egreso.arqueo_id")

    @property
    def total_arqueo_fisico(self) -> float:
        """Suma total de billetes * denominacion"""
        dens = self.denominaciones or {}
        return sum(int(k) * int(v) for k, v in dens.items() if v)

    @property
    def pagos_dia(self) -> float:
        """Total pagado en efectivo en el día (egresos en efectivo)"""
        return sum(e.monto for e in self.egresos if e.monto)

    @property
    def caja_restante(self) -> float:
        return self.saldo_inicial + (self.pesos_agregados or 0) + (self.ingresos or 0) - self.pagos_dia

    @property
    def cruce(self) -> float:
        """Debe ser 0: arqueo fisico - caja restante"""
        return self.total_arqueo_fisico - self.caja_restante
