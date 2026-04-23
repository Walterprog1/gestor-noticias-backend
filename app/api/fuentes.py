from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.security import get_current_user, require_role
from app.models.user import User
from app.models.fuente import Fuente
from app.schemas.schemas import FuenteCreate, FuenteUpdate, FuenteResponse

router = APIRouter(prefix="/api/fuentes", tags=["Fuentes"])


@router.get("/", response_model=list[FuenteResponse])
def list_fuentes(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    fuentes = db.query(Fuente).order_by(Fuente.nombre).all()
    return [FuenteResponse.model_validate(f) for f in fuentes]


@router.get("/{fuente_id}", response_model=FuenteResponse)
def get_fuente(
    fuente_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    fuente = db.query(Fuente).filter(Fuente.id == fuente_id).first()
    if not fuente:
        raise HTTPException(status_code=404, detail="Fuente no encontrada")
    return FuenteResponse.model_validate(fuente)


@router.post("/", response_model=FuenteResponse)
def create_fuente(
    data: FuenteCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("administrador"))
):
    fuente = Fuente(**data.model_dump())
    db.add(fuente)
    db.commit()
    db.refresh(fuente)
    return FuenteResponse.model_validate(fuente)


@router.put("/{fuente_id}", response_model=FuenteResponse)
def update_fuente(
    fuente_id: int,
    data: FuenteUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("administrador"))
):
    fuente = db.query(Fuente).filter(Fuente.id == fuente_id).first()
    if not fuente:
        raise HTTPException(status_code=404, detail="Fuente no encontrada")

    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(fuente, field, value)

    db.commit()
    db.refresh(fuente)
    return FuenteResponse.model_validate(fuente)


@router.delete("/{fuente_id}")
def deactivate_fuente(
    fuente_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("administrador"))
):
    fuente = db.query(Fuente).filter(Fuente.id == fuente_id).first()
    if not fuente:
        raise HTTPException(status_code=404, detail="Fuente no encontrada")

    fuente.activa = False
    fuente.estado = "desactivada"
    db.commit()
    return {"message": "Fuente desactivada"}
