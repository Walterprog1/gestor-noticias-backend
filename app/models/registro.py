from sqlalchemy import Column, Integer, String, DateTime, Text, ForeignKey, JSON
from sqlalchemy.sql import func
from app.core.database import Base


class Registro(Base):
    """Registro editorial procesado — entidad central del sistema."""
    __tablename__ = "registros"

    id = Column(Integer, primary_key=True, index=True)
    articulo_id = Column(Integer, ForeignKey("articulos.id"), nullable=False)

    # Datos de la fuente
    fuente = Column(String(100), nullable=False)
    fecha = Column(DateTime(timezone=True), nullable=True)
    link = Column(String(1000), nullable=False)

    # Campos de contenido editorial
    que = Column(Text, nullable=True)
    que_origen = Column(String(10), default="ia")  # 'ia' | 'operador'
    quien = Column(Text, nullable=True)
    quien_origen = Column(String(10), default="ia")
    porque = Column(Text, nullable=True)
    porque_origen = Column(String(10), default="ia")
    datos = Column(Text, nullable=True)
    datos_origen = Column(String(10), default="ia")

    # Título
    titulo = Column(String(500), nullable=True)
    titulo_origen = Column(String(10), default="ia")

    # Clasificación
    tags = Column(Text, nullable=True)  # Comma-separated actors
    tags_origen = Column(String(10), default="ia")
    sector = Column(String(50), nullable=True)  # AGENDA, AGRO, ENERGÍA, FINANZAS, TRABAJADORES, INDUSTRIAL
    sector_origen = Column(String(10), default="ia")
    orbita = Column(String(50), nullable=True)  # POLÍTICA, ECONOMÍA, ESTRATEGIA
    orbita_origen = Column(String(10), default="ia")
    genero = Column(String(20), nullable=True)  # nota, opinión
    ambito = Column(String(50), nullable=True)  # provincial, nacional, latinoamericano, internacional
    region = Column(String(100), nullable=True)

    # Estado del registro
    estado = Column(String(20), default="procesado", index=True)  # procesado, aprobado, rechazado
    motivo_rechazo = Column(Text, nullable=True)

    # Trazabilidad
    operador_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    sector_operador = Column(String(50), nullable=True)
    fecha_aprobacion = Column(DateTime(timezone=True), nullable=True)
    correcciones_json = Column(JSON, default=list)
    # Format: [{"campo": "titulo", "valor_ia": "...", "valor_operador": "...", "usuario": "...", "timestamp": "..."}]

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
