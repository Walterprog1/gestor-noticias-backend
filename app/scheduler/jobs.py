"""
Scheduler — Ejecuta escaneos automáticos a horarios configurados.
"""
import logging
import os
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

logger = logging.getLogger(__name__)

scheduler = BackgroundScheduler()


def start_scheduler():
    """Start the background scheduler and load jobs from DB."""
    if os.getenv("DISABLE_SCHEDULER", "false").lower() == "true":
        logger.info("Scheduler disabled via DISABLE_SCHEDULER env var")
        return
    
    if scheduler.running:
        return

    try:
        # Add a default job that runs every 6 hours to scan all active sources
        scheduler.add_job(
            scan_all_active_sources,
            CronTrigger(hour="6,12,18,0"),
            id="scan_all",
            replace_existing=True,
            name="Escaneo automático de todas las fuentes"
        )

        scheduler.start()
        logger.info("Scheduler started")
    except Exception as e:
        logger.error(f"Failed to start scheduler: {e}")


def stop_scheduler():
    """Stop the background scheduler."""
    try:
        if scheduler.running:
            scheduler.shutdown(wait=False)
            logger.info("Scheduler stopped")
    except Exception as e:
        logger.error(f"Error stopping scheduler: {e}")


def scan_all_active_sources():
    """Scan all active sources."""
    from app.core.database import SessionLocal
    from app.models.fuente import Fuente
    from app.services.scraping import run_scan

    logger.info("Starting scheduled scan of all active sources")
    db = SessionLocal()
    try:
        fuentes = db.query(Fuente).filter(Fuente.activa == True).all()
        for fuente in fuentes:
            try:
                run_scan(fuente.id)
            except Exception as e:
                logger.error(f"Error scanning {fuente.nombre}: {e}")
    finally:
        db.close()
