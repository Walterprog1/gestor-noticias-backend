from pydantic import BaseModel, EmailStr
from typing import Optional
from datetime import datetime


# --- Auth ---
class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user: "UserResponse"


class RefreshRequest(BaseModel):
    refresh_token: str


# --- User ---
class UserCreate(BaseModel):
    username: str
    email: str
    password: str
    nombre_completo: str
    rol: str = "operador"
    sector_asignado: Optional[str] = None


class UserUpdate(BaseModel):
    nombre_completo: Optional[str] = None
    rol: Optional[str] = None
    sector_asignado: Optional[str] = None
    activo: Optional[bool] = None


class UserResponse(BaseModel):
    id: int
    username: str
    email: str
    nombre_completo: str
    rol: str
    sector_asignado: Optional[str]
    activo: bool
    created_at: Optional[datetime]

    class Config:
        from_attributes = True


# --- Fuente ---
class FuenteCreate(BaseModel):
    nombre: str
    url_base: str
    secciones: list = []
    horarios_escaneo: list = []
    sector: Optional[str] = None
    selectores_config: dict = {}


class FuenteUpdate(BaseModel):
    nombre: Optional[str] = None
    url_base: Optional[str] = None
    secciones: Optional[list] = None
    horarios_escaneo: Optional[list] = None
    sector: Optional[str] = None
    selectores_config: Optional[dict] = None
    activa: Optional[bool] = None


class FuenteResponse(BaseModel):
    id: int
    nombre: str
    url_base: str
    secciones: list
    horarios_escaneo: list
    sector: Optional[str]
    selectores_config: dict
    estado: str
    ultimo_error: Optional[str]
    activa: bool
    ultimo_escaneo: Optional[datetime]
    articulos_extraidos_total: int
    created_at: Optional[datetime]

    class Config:
        from_attributes = True


# --- Articulo ---
class ArticuloResponse(BaseModel):
    id: int
    fuente_id: int
    url: str
    titulo_original: Optional[str]
    texto_crudo: Optional[str]
    fecha_publicacion: Optional[datetime]
    nombre_medio: Optional[str]
    estado: str
    motivo_no_relevante: Optional[str]
    created_at: Optional[datetime]

    class Config:
        from_attributes = True


# --- Registro ---
class RegistroResponse(BaseModel):
    id: int
    articulo_id: int
    fuente: str
    fecha: Optional[datetime]
    link: str
    que: Optional[str]
    que_origen: str
    quien: Optional[str]
    quien_origen: str
    porque: Optional[str]
    porque_origen: str
    datos: Optional[str]
    datos_origen: str
    titulo: Optional[str]
    titulo_origen: str
    tags: Optional[str]
    tags_origen: str
    sector: Optional[str]
    sector_origen: str
    orbita: Optional[str]
    orbita_origen: str
    genero: Optional[str]
    ambito: Optional[str]
    region: Optional[str]
    estado: str
    motivo_rechazo: Optional[str]
    operador_id: Optional[int]
    sector_operador: Optional[str]
    fecha_aprobacion: Optional[datetime]
    correcciones_json: list
    created_at: Optional[datetime]
    # Extra field for the approval view: original article text
    texto_crudo: Optional[str] = None
    titulo_original: Optional[str] = None

    class Config:
        from_attributes = True


class RegistroApprove(BaseModel):
    """Fields the operator can edit before approving."""
    que: Optional[str] = None
    quien: Optional[str] = None
    porque: Optional[str] = None
    datos: Optional[str] = None
    titulo: Optional[str] = None
    tags: Optional[str] = None
    sector: Optional[str] = None
    orbita: Optional[str] = None
    genero: Optional[str] = None
    ambito: Optional[str] = None
    region: Optional[str] = None


class RegistroReject(BaseModel):
    motivo_rechazo: str


class BatchAction(BaseModel):
    ids: list[int]
    action: str  # "aprobar" | "rechazar"
    motivo_rechazo: Optional[str] = None


# --- Prompt ---
class PromptCreate(BaseModel):
    nombre: str
    descripcion: Optional[str] = None
    contenido: str
    tipo: str = "procesamiento"


class PromptUpdate(BaseModel):
    nombre: Optional[str] = None
    descripcion: Optional[str] = None
    contenido: Optional[str] = None
    activo: Optional[bool] = None


class PromptResponse(BaseModel):
    id: int
    nombre: str
    descripcion: Optional[str]
    contenido: str
    version: int
    activo: bool
    tipo: str
    created_at: Optional[datetime]

    class Config:
        from_attributes = True


# --- Export ---
class ExportRequest(BaseModel):
    ids: Optional[list[int]] = None  # Specific IDs or None for filtered results
    formato: str = "xlsx"  # xlsx, csv, docx
    solo_titulos: bool = False
    incluir_trazabilidad: bool = False
    # Filters (used when ids is None)
    fuente: Optional[str] = None
    fecha_desde: Optional[str] = None
    fecha_hasta: Optional[str] = None
    sector: Optional[str] = None
    orbita: Optional[str] = None
    genero: Optional[str] = None
    ambito: Optional[str] = None
    busqueda: Optional[str] = None


# --- Scan ---
class ScanRequest(BaseModel):
    fuente_id: int


class ManualLinkRequest(BaseModel):
    url: str
    fuente_id: Optional[int] = None
