from sqlalchemy import Column, Integer, String, ForeignKey
from sqlalchemy.orm import relationship
from app.database import Base


class Portador(Base):
    __tablename__ = "portadores"

    id              = Column(Integer, primary_key=True, index=True)
    organizacion_id = Column(Integer, ForeignKey("organizaciones.id"), nullable=False, default=1)
    nombre          = Column(String, nullable=False)

    organizacion = relationship("Organizacion", foreign_keys=[organizacion_id])
