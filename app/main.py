"""
Gestor de Noticias — Backend API
FastAPI application entry point.
"""
import logging
import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.database import init_db, SessionLocal
from app.core.security import get_password_hash
from app.core.config import get_settings
from app.models import User, Prompt
from app.api import auth, fuentes, escaneo, registros, exportacion, prompts
from app.scheduler.jobs import start_scheduler, stop_scheduler
from app.services.ia_processor import DEFAULT_PROMPT

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def seed_database():
    """Create default admin user and default prompt if they don't exist."""
    db = SessionLocal()
    try:
        # Create default admin
        if not db.query(User).filter(User.username == "admin").first():
            admin = User(
                username="admin",
                email="admin@gestor.local",
                password_hash=get_password_hash("admin123"),
                nombre_completo="Administrador",
                rol="administrador",
                sector_asignado=None
            )
            db.add(admin)
            logger.info("Default admin user created (admin / admin123)")

        # Create default operator
        if not db.query(User).filter(User.username == "operador").first():
            operador = User(
                username="operador",
                email="operador@gestor.local",
                password_hash=get_password_hash("operador123"),
                nombre_completo="Operador Demo",
                rol="operador",
                sector_asignado="AGENDA"
            )
            db.add(operador)
            logger.info("Default operator user created (operador / operador123)")

        # Create default analyst
        if not db.query(User).filter(User.username == "analista").first():
            analista = User(
                username="analista",
                email="analista@gestor.local",
                password_hash=get_password_hash("analista123"),
                nombre_completo="Analista Demo",
                rol="analista",
                sector_asignado=None
            )
            db.add(analista)
            logger.info("Default analyst user created (analista / analista123)")

        # Create default processing prompt
        if not db.query(Prompt).filter(Prompt.tipo == "procesamiento").first():
            prompt = Prompt(
                nombre="Prompt de Procesamiento Editorial v1",
                descripcion="Prompt principal para la generación de registros editoriales a partir de noticias.",
                contenido=DEFAULT_PROMPT,
                tipo="procesamiento",
                activo=True
            )
            db.add(prompt)
            logger.info("Default processing prompt created")

        db.commit()
    finally:
        db.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("Starting Gestor de Noticias API...")
    settings = get_settings()
    logger.info(f"LLM Provider: {settings.LLM_PROVIDER}, Model: {settings.LLM_MODEL}")
    
    try:
        init_db()
        seed_database()
    except Exception as e:
        logger.error(f"Database initialization failed: {e}")
        raise
    
    start_scheduler()
    yield
    
    # Shutdown
    try:
        stop_scheduler()
    except Exception as e:
        logger.error(f"Error during shutdown: {e}")
    logger.info("Gestor de Noticias API stopped.")


app = FastAPI(
    title="Gestor de Noticias API",
    description="API para la gestión y reedición automatizada de noticias con IA",
    version="2.0.0",
    lifespan=lifespan
)

ALLOWED_ORIGINS = os.getenv(
    "ALLOWED_ORIGINS", 
    "http://localhost:5173,http://localhost:3000,http://127.0.0.1:5173,https://*.vercel.app,https://gestor-noticias-frontend.vercel.app"
).split(",")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers
app.include_router(auth.router)
app.include_router(fuentes.router)
app.include_router(escaneo.router)
app.include_router(registros.router)
app.include_router(exportacion.router)
app.include_router(prompts.router)


@app.get("/")
def root():
    return {"message": "Gestor de Noticias API v2.0", "status": "running"}


@app.get("/health")
def health():
    return {"status": "ok"}
