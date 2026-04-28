import sys
import os

# CONFIGURAR DATABASE_URL DE RAILWAY ANTES DE CUALQUIER IMPORT
os.environ["DATABASE_URL"] = "postgresql://postgres:MwrzGDPSRInoQdOMboqaIFosqbCazATN@shortline.proxy.rlwy.net:15295/railway"

# Agregar backend al path
sys.path.append(os.path.join(os.path.dirname(__file__), "backend"))

import asyncio

from app.core.database import SessionLocal
from app.models.articulo import Articulo
from app.services.scraping import _process_single_article
from app.core.config import get_settings

async def main():
    settings = get_settings()
    print(f"LLM: {settings.LLM_PROVIDER} | Modelo: {settings.LLM_MODEL}")
    
    db = SessionLocal()
    try:
        crudo_articles = db.query(Articulo).filter(Articulo.estado == "crudo").all()
        total = len(crudo_articles)
        
        if total == 0:
            print("No hay artículos en estado 'crudo'")
            return
        
        print(f"Procesando {total} artículos 'crudo':")
        processed = 0
        filtered = 0
        failed = 0
        
        for idx, art in enumerate(crudo_articles, 1):
            print(f"\n{idx}/{total} (ID: {art.id})")
            try:
                await _process_single_article(art.id, db)
                db.refresh(art)
                print(f"  -> Estado: {art.estado}")
                if art.estado == "procesado":
                    processed +=1
                elif art.estado in ("filtrado", "no_relevante"):
                    filtered +=1
            except Exception as e:
                print(f"  -> Error: {e}")
                failed +=1
                db.rollback()
        
        print(f"\nResumen: {processed} a cola | {filtered} filtrados | {failed} errores")
    finally:
        db.close()

if __name__ == "__main__":
    asyncio.run(main())
