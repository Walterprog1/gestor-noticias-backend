from sqlalchemy import Column, Integer, String, DateTime, Text, ForeignKey
from sqlalchemy.sql import func
from app.core.database import Base


class Correccion(Base):
    """Historial de correcciones para feedback loop."""
    __tablename__ = "correcciones"

    id = Column(Integer, primary_key=True, index=True)
    registro_id = Column(Integer, ForeignKey("registros.id"), nullable=False)
    campo = Column(String(50), nullable=False)
    valor_ia = Column(Text, nullable=True)
    valor_operador = Column(Text, nullable=True)
    usuario_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    usuario_nombre = Column(String(100), nullable=True)
    timestamp = Column(DateTime(timezone=True), server_default=func.now())
