from sqlalchemy import Column, Integer, String, DateTime, Text, ForeignKey
from sqlalchemy.sql import func
from app.core.database import Base


class Articulo(Base):
    __tablename__ = "articulos"

    id = Column(Integer, primary_key=True, index=True)
    fuente_id = Column(Integer, ForeignKey("fuentes.id"), nullable=False)
    url = Column(String(1000), nullable=False)
    url_hash = Column(String(64), unique=True, index=True, nullable=False)  # SHA256 for dedup
    titulo_original = Column(String(500), nullable=True)
    texto_crudo = Column(Text, nullable=True)
    fecha_publicacion = Column(DateTime(timezone=True), nullable=True)
    nombre_medio = Column(String(100), nullable=True)
    estado = Column(String(20), default="crudo")  # crudo, filtrado, procesado, no_relevante
    motivo_no_relevante = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
