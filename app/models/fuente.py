from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text, JSON
from sqlalchemy.sql import func
from app.core.database import Base


class Fuente(Base):
    __tablename__ = "fuentes"

    id = Column(Integer, primary_key=True, index=True)
    nombre = Column(String(100), nullable=False)
    url_base = Column(String(500), nullable=False)
    secciones = Column(JSON, default=list)  # [{"nombre": "Política", "url": "/politica/"}]
    horarios_escaneo = Column(JSON, default=list)  # ["06:00", "12:00", "18:00"]
    sector = Column(String(50), nullable=True)  # Sector/temática por defecto
    selectores_config = Column(JSON, default=dict)
    # Ejemplo selectores_config:
    # {
    #   "lista_articulos": "article.feed-list-card",
    #   "link_selector": "a.feed-list-card__link",
    #   "titulo_selector": "h2.feed-list-card__title",
    #   "contenido_selector": "div.article-body",
    #   "fecha_selector": "time",
    #   "espera_ms": 3000
    # }
    estado = Column(String(20), default="activa")  # activa, error, desactivada
    ultimo_error = Column(Text, nullable=True)
    activa = Column(Boolean, default=True)
    ultimo_escaneo = Column(DateTime(timezone=True), nullable=True)
    articulos_extraidos_total = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
