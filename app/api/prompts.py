from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.security import require_role
from app.models.user import User
from app.models.prompt import Prompt
from app.schemas.schemas import PromptCreate, PromptUpdate, PromptResponse

router = APIRouter(prefix="/api/prompts", tags=["Prompts IA"])


@router.get("/", response_model=list[PromptResponse])
def list_prompts(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("administrador"))
):
    prompts = db.query(Prompt).order_by(Prompt.nombre).all()
    return [PromptResponse.model_validate(p) for p in prompts]


@router.post("/", response_model=PromptResponse)
def create_prompt(
    data: PromptCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("administrador"))
):
    prompt = Prompt(**data.model_dump())
    db.add(prompt)
    db.commit()
    db.refresh(prompt)
    return PromptResponse.model_validate(prompt)


@router.put("/{prompt_id}", response_model=PromptResponse)
def update_prompt(
    prompt_id: int,
    data: PromptUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("administrador"))
):
    prompt = db.query(Prompt).filter(Prompt.id == prompt_id).first()
    if not prompt:
        raise HTTPException(status_code=404, detail="Prompt no encontrado")

    # If content changed, increment version
    if data.contenido and data.contenido != prompt.contenido:
        prompt.version += 1

    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(prompt, field, value)

    db.commit()
    db.refresh(prompt)
    return PromptResponse.model_validate(prompt)
