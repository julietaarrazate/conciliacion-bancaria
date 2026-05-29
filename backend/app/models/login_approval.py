"""Solicitudes de ingreso por aprobación en vivo (rol contador).

Cuando un usuario con rol `contador` se loguea, NO recibe token directo: se crea
un pedido `LoginApproval` en estado `pending` y se notifica al superadmin. El
superadmin aprueba/rechaza desde /aprobaciones. Al aprobar se genera el JWT (4h)
y se guarda en `access_token`, que el cliente del contador recoge una sola vez
por polling. Pasadas las 4h el token expira y debe pedir aprobación de nuevo.
"""

from sqlalchemy import Column, Integer, String, Text, DateTime
from datetime import datetime

from app.database import Base


class LoginApproval(Base):
    __tablename__ = "login_approvals"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, nullable=False, index=True)
    # pending / approved / denied / expired
    status = Column(String, default="pending", nullable=False)
    # sha256 del secreto que se devuelve al cliente al loguear; requerido para
    # consultar el estado (evita que un tercero adivine el approval_id y robe el token)
    poll_secret_hash = Column(String, nullable=False)
    # JWT generado al aprobar; se entrega una sola vez por polling y se limpia
    access_token = Column(Text, nullable=True)
    ip = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    # El pedido pendiente caduca si el superadmin no decide a tiempo
    request_expires_at = Column(DateTime, nullable=False)
    decided_at = Column(DateTime, nullable=True)
    decided_by = Column(Integer, nullable=True)
