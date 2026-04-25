import asyncio
import logging
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import or_
from datetime import datetime, timezone
from app.core.database import get_db
from app.core.security import get_current_user, require_role
from app.models.user import User
from app.models.registro import Registro
from app.models.articulo import Articulo
from app.models.correccion import Correccion
from app.schemas.schemas import (
    RegistroResponse, RegistroApprove, RegistroReject, BatchAction
)

router = APIRouter(prefix="/api/registros", tags=["Registros"])
logger = logging.getLogger(__name__)


def _enrich_registro(registro: Registro, db: Session) -> dict:
    """Add original article text to registro response."""
    data = RegistroResponse.model_validate(registro).model_dump()
    articulo = db.query(Articulo).filter(Articulo.id == registro.articulo_id).first()
    if articulo:
        data["texto_crudo"] = articulo.texto_crudo
        data["titulo_original"] = articulo.titulo_original
    return data


@router.get("/cola", response_model=list[RegistroResponse])
def get_approval_queue(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("administrador", "operador"))
):
    """Get approval queue filtered by operator's assigned sector."""
    query = db.query(Registro).filter(Registro.estado == "procesado")

    # Operators see only their sector; admins see all
    if current_user.rol == "operador" and current_user.sector_asignado:
        query = query.filter(Registro.sector == current_user.sector_asignado)

    registros = query.order_by(Registro.created_at.desc()).all()
    return [_enrich_registro(r, db) for r in registros]


@router.get("/", response_model=list[RegistroResponse])
def list_registros(
    estado: str = None,
    fuente: str = None,
    sector: str = None,
    orbita: str = None,
    genero: str = None,
    ambito: str = None,
    region: str = None,
    busqueda: str = None,
    fecha_desde: str = None,
    fecha_hasta: str = None,
    orden: str = "fecha_desc",
    limit: int = 50,
    offset: int = 0,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Search approved records with combined filters."""
    query = db.query(Registro)

    # Default to approved for non-admin
    if estado:
        query = query.filter(Registro.estado == estado)
    elif current_user.rol == "analista":
        query = query.filter(Registro.estado == "aprobado")

    if fuente:
        query = query.filter(Registro.fuente.ilike(f"%{fuente}%"))
    if sector:
        query = query.filter(Registro.sector == sector)
    if orbita:
        query = query.filter(Registro.orbita == orbita)
    if genero:
        query = query.filter(Registro.genero == genero)
    if ambito:
        query = query.filter(Registro.ambito == ambito)
    if region:
        query = query.filter(Registro.region.ilike(f"%{region}%"))
    if fecha_desde:
        query = query.filter(Registro.fecha >= fecha_desde)
    if fecha_hasta:
        query = query.filter(Registro.fecha <= fecha_hasta)
    if busqueda:
        search = f"%{busqueda}%"
        query = query.filter(
            or_(
                Registro.titulo.ilike(search),
                Registro.que.ilike(search),
                Registro.quien.ilike(search),
                Registro.tags.ilike(search),
            )
        )

    # Ordering
    if orden == "fecha_asc":
        query = query.order_by(Registro.fecha.asc())
    elif orden == "fuente":
        query = query.order_by(Registro.fuente)
    elif orden == "sector":
        query = query.order_by(Registro.sector)
    else:
        query = query.order_by(Registro.fecha.desc())

    total = query.count()
    registros = query.offset(offset).limit(limit).all()

    return [_enrich_registro(r, db) for r in registros]


@router.get("/count")
def count_registros(
    estado: str = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    query = db.query(Registro)
    if estado:
        query = query.filter(Registro.estado == estado)
    return {"count": query.count()}


@router.get("/{registro_id}", response_model=RegistroResponse)
def get_registro(
    registro_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    registro = db.query(Registro).filter(Registro.id == registro_id).first()
    if not registro:
        raise HTTPException(status_code=404, detail="Registro no encontrado")
    return _enrich_registro(registro, db)


@router.post("/{registro_id}/aprobar", response_model=RegistroResponse)
def approve_registro(
    registro_id: int,
    data: RegistroApprove = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("administrador", "operador"))
):
    """Approve a record, optionally editing fields before approval."""
    registro = db.query(Registro).filter(Registro.id == registro_id).first()
    if not registro:
        raise HTTPException(status_code=404, detail="Registro no encontrado")
    if registro.estado == "aprobado":
        raise HTTPException(status_code=400, detail="Registro ya aprobado")

    # If operator edited fields, track corrections
    if data:
        editable_fields = [
            "que", "quien", "porque", "datos", "titulo",
            "tags", "sector", "orbita", "genero", "ambito", "region"
        ]
        corrections = registro.correcciones_json or []

        for field in editable_fields:
            new_value = getattr(data, field, None)
            if new_value is not None:
                old_value = getattr(registro, field)
                if new_value != old_value:
                    # Record correction
                    corrections.append({
                        "campo": field,
                        "valor_ia": old_value,
                        "valor_operador": new_value,
                        "usuario": current_user.username,
                        "timestamp": datetime.now(timezone.utc).isoformat()
                    })
                    # Save correction to separate table too
                    correccion = Correccion(
                        registro_id=registro.id,
                        campo=field,
                        valor_ia=old_value,
                        valor_operador=new_value,
                        usuario_id=current_user.id,
                        usuario_nombre=current_user.username
                    )
                    db.add(correccion)

                    # Update the field
                    setattr(registro, field, new_value)
                    setattr(registro, f"{field}_origen", "operador")

        registro.correcciones_json = corrections

    # Validate required fields
    if not registro.que or not registro.titulo:
        raise HTTPException(
            status_code=400,
            detail="No se puede aprobar: campos obligatorios vacíos (QUÉ, TÍTULO)"
        )

    registro.estado = "aprobado"
    registro.operador_id = current_user.id
    registro.sector_operador = current_user.sector_asignado
    registro.fecha_aprobacion = datetime.now(timezone.utc)

    db.commit()
    db.refresh(registro)
    return _enrich_registro(registro, db)


@router.post("/{registro_id}/rechazar", response_model=RegistroResponse)
def reject_registro(
    registro_id: int,
    data: RegistroReject,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("administrador", "operador"))
):
    """Reject a record with mandatory reason."""
    registro = db.query(Registro).filter(Registro.id == registro_id).first()
    if not registro:
        raise HTTPException(status_code=404, detail="Registro no encontrado")

    registro.estado = "rechazado"
    registro.motivo_rechazo = data.motivo_rechazo
    registro.operador_id = current_user.id
    registro.sector_operador = current_user.sector_asignado
    registro.fecha_aprobacion = datetime.now(timezone.utc)

    db.commit()
    db.refresh(registro)
    return _enrich_registro(registro, db)


@router.post("/batch")
def batch_action(
    data: BatchAction,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("administrador", "operador"))
):
    """Batch approve or reject multiple records."""
    registros = db.query(Registro).filter(Registro.id.in_(data.ids)).all()

    if data.action == "rechazar" and not data.motivo_rechazo:
        raise HTTPException(status_code=400, detail="Motivo de rechazo obligatorio")

    count = 0
    for registro in registros:
        if registro.estado != "procesado":
            continue

        if data.action == "aprobar":
            if not registro.que or not registro.titulo:
                continue
            registro.estado = "aprobado"
        elif data.action == "rechazar":
            registro.estado = "rechazado"
            registro.motivo_rechazo = data.motivo_rechazo

        registro.operador_id = current_user.id
        registro.sector_operador = current_user.sector_asignado
        registro.fecha_aprobacion = datetime.now(timezone.utc)
        count += 1

    db.commit()
    return {"message": f"{count} registros {'aprobados' if data.action == 'aprobar' else 'rechazados'}"}


@router.post("/reprocesar-sector")
def reprocesar_por_sector(
    sector_incorrecto: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("administrador"))
):
    """Borrar y reprocesar artículos que generaron registros con sector incorrecto."""
    from app.services.ia_processor import process_article
    from app.models.articulo import Articulo
    
    # Encontrar todos los registros con ese sector que aún no fueron aprobados
    registros = db.query(Registro).filter(
        Registro.sector == sector_incorrecto,
        Registro.estado == "procesado"
    ).all()
    
    if not registros:
        return {"message": f"No hay registros con sector={sector_incorrecto} para reprocesar"}
    
    # Obtener los article_ids únicos
    article_ids = list(set(r.articulo_id for r in registros))
    
    # Borrar los registros generados por IA
    for r in registros:
        db.delete(r)
    db.commit()
    
    # Reprocesar los artículos
    reprocesados = 0
    errores = 0
    for aid in article_ids:
        articulo = db.query(Articulo).filter(Articulo.id == aid).first()
        if articulo:
            try:
                # Resetear estado para reprocesar
                articulo.estado = "crudo"
                db.commit()
                import asyncio
                asyncio.run(process_article(articulo, db))
                reprocesados += 1
            except Exception as e:
                errores += 1
                logger.error(f"Error reprocesando artículo {aid}: {e}")
    
    return {
        "message": f"Reprocesados {reprocesados} artículos, {errores} errores",
        "articulos_reprocesados": article_ids
    }
