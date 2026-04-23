import asyncio
from app.core.database import SessionLocal
from app.services.ia_processor import process_article
from app.models.articulo import Articulo

async def main():
    db = SessionLocal()
    try:
        articles = db.query(Articulo).filter(Articulo.estado == 'crudo').all()
        for a in articles:
            await process_article(a, db)
    finally:
        db.close()

if __name__ == "__main__":
    asyncio.run(main())
