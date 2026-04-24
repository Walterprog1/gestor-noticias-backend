from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.security import get_current_user, require_role
from app.models.user import User
from app.models.fuente import Fuente
from app.models.articulo import Articulo
from app.schemas.schemas import ScanRequest, ManualLinkRequest, ArticuloResponse
from app.core.config import get_settings
import os
import hashlib

router = APIRouter(prefix="/api/escaneo", tags=["Escaneo"])

@router.get("/config-test")
def config_test():
    from app.services.ia_processor import get_last_error
    settings = get_settings()
    llm_vars = {k: v for k, v in os.environ.items() if k.startswith("LLM_")}
    return {
        "settings_provider": settings.LLM_PROVIDER, 
        "settings_base_url": settings.LLM_BASE_URL,
        "settings_model": settings.LLM_MODEL,
        "last_ia_error": get_last_error(),
        "env_vars": llm_vars
    }

@router.post("/retry-errors")
async def retry_errors(background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    """Reset all error articles to crudo and re-trigger processing."""
    from app.services.scraping import _process_single_article
    from sqlalchemy import or_
    articulos = db.query(Articulo).filter(or_(Articulo.estado == "error", Articulo.estado == "crudo")).all()
    count = len(articulos)
    
    for a in articulos:
        a.estado = "crudo"
    db.commit()

    async def process_all():
        from app.core.database import SessionLocal
        new_db = SessionLocal()
        try:
            for a in articulos:
                try:
                    await _process_single_article(a.id, new_db)
                except Exception as e:
                    print(f"Error re-processing article {a.id}: {e}")
        finally:
            new_db.close()
    
    background_tasks.add_task(process_all)
    return {"message": f"Reiniciando el proceso para {count} artículos."}


@router.post("/manual")
async def scan_fuente(
    data: ScanRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("administrador", "operador"))
):
    """Trigger manual scan of a specific source."""
    fuente = db.query(Fuente).filter(Fuente.id == data.fuente_id).first()
    if not fuente:
        raise HTTPException(status_code=404, detail="Fuente no encontrada")

    from app.services.scraping import run_scan
    background_tasks.add_task(run_scan, data.fuente_id)

    return {"message": f"Escaneo de '{fuente.nombre}' iniciado en segundo plano"}


@router.post("/link")
async def add_manual_link(
    data: ManualLinkRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("administrador", "operador"))
):
    """Add a single link manually for processing."""
    url_hash = hashlib.sha256(data.url.encode()).hexdigest()

    # Check for duplicates
    existing = db.query(Articulo).filter(Articulo.url_hash == url_hash).first()
    if existing:
        raise HTTPException(status_code=400, detail="Este link ya fue procesado")

    fuente = None
    if data.fuente_id:
        fuente = db.query(Fuente).filter(Fuente.id == data.fuente_id).first()

    articulo = Articulo(
        fuente_id=data.fuente_id,
        url=data.url,
        url_hash=url_hash,
        nombre_medio=fuente.nombre if fuente else "Manual",
        estado="crudo"
    )
    db.add(articulo)
    db.commit()
    db.refresh(articulo)

    from app.services.scraping import extract_and_process_article
    background_tasks.add_task(extract_and_process_article, articulo.id)

    return {"message": "Link agregado y procesamiento iniciado", "articulo_id": articulo.id}


@router.get("/articulos", response_model=list[ArticuloResponse])
def list_articulos(
    estado: str = None,
    fuente_id: int = None,
    limit: int = 50,
    offset: int = 0,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """List extracted articles with optional filters."""
    query = db.query(Articulo)
    if estado:
        query = query.filter(Articulo.estado == estado)
    if fuente_id:
        query = query.filter(Articulo.fuente_id == fuente_id)

    articles = query.order_by(Articulo.created_at.desc()).offset(offset).limit(limit).all()
    return [ArticuloResponse.model_validate(a) for a in articles]


@router.get("/status")
def scan_status(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get overall scan status."""
    total = db.query(Articulo).count()
    crudo = db.query(Articulo).filter(Articulo.estado == "crudo").count()
    filtrado = db.query(Articulo).filter(Articulo.estado == "filtrado").count()
    procesado = db.query(Articulo).filter(Articulo.estado == "procesado").count()
    no_relevante = db.query(Articulo).filter(Articulo.estado == "no_relevante").count()

    return {
        "total_articulos": total,
        "crudo": crudo,
        "filtrado": filtrado,
        "procesado": procesado,
        "no_relevante": no_relevante,
    }
