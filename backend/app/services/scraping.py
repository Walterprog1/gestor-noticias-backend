"""
Motor de Scraping — Extrae noticias de fuentes configuradas.
Soporta sitios estáticos (BeautifulSoup) y dinámicos (Playwright).
"""
import hashlib
import logging
import re
from datetime import datetime, timezone
from typing import Optional
from bs4 import BeautifulSoup
import httpx

logger = logging.getLogger(__name__)


def _tiene_contexto_politico(texto: str) -> bool:
    """Check if article has political, economic or union context."""
    if not texto:
        return False
    return bool(RE_POLITICOS.search(texto)) or bool(RE_ECONOMICOS.search(texto)) or bool(RE_SINDICALES.search(texto))


def _tiene_hecho(texto: str) -> bool:
    """Check if article has HECHO (actor institucional, politico, economico o sindical).
    
    Returns True if the article has a relevant actor that justifies loading.
    Returns False if it's just an event/news without a relevant actor.
    """
    if not texto:
        return False
    return bool(RE_POLITICOS.search(texto)) or bool(RE_ECONOMICOS.search(texto)) or bool(RE_SINDICALES.search(texto))


def _es_seccion_excluida(url: str) -> bool:
    """Check if URL belongs to an excluded section."""
    url_lower = url.lower()
    for seccion in SECCIONES_EXCLUIR:
        if seccion in url_lower:
            return True
    return False


def _es_seccion_siempre_excluida(url: str) -> bool:
    """Check if URL is from a section that should ALWAYS be excluded."""
    url_lower = url.lower()
    for seccion in SECCIONES_EXCLUIDAS_SIEMPRE:
        if seccion in url_lower:
            return True
    return False


def _debe_filtrar_articulo(url: str, texto: str = "") -> bool:
    """Determine if an article should be filtered out.

    Returns True if article should be EXCLUDED (no tiene HECHO).
    Returns False if article should be KEPT.
    """
    # SIEMPRE FILTRAR secciones de contenido puro sin hechos institucionales
    if _es_seccion_siempre_excluida(url):
        return True
    
    # PARA TODAS las otras URLs: verificar si tiene HECHO
    if not _tiene_hecho(texto):
        return True
    
    return False

# Secciones que SIEMPRE se filtran (sin excepciones)
SECCIONES_EXCLUIDAS_SIEMPRE = [
    # Entretenimiento y cultura
    "/entretenimiento/", "/cultura/", "/espectaculos/", "/musica/", "/series/",
    "/peliculas/", "/tv/", "/streaming/", "/netflix/", "/disney/", "/hbo/",
    # Deportes
    "/deportes/", "/deporte/", "/sports/", "/futbol/", "/tenis/", "/basquet/",
    "/boxeo/", "/golf/", "/nba/", "/liga/", "/copa/",
    # Tag de deportes
    "/tag/deportes-internacional/",
    # Policiales y judiciales
    "/policiales/", "/judicial/", "/crimenes/", "/sucesos/",
    # Moda y lifestyle
    "/moda/", "/tendencias/", "/viral/", "/fama/",
]

# Secciones a filtrar (usado por _es_seccion_excluida para otros checks)
SECCIONES_EXCLUIR = [
    "/sociedad/", "/vida/", "/turismo/", "/viajes/", "/gastronomia/",
    "/tecnologia/", "/tech/", "/videojuegos/", "/gaming/", "/esports/",
    "/accidentes/", "/tragedia/", "/tragedias/", "/incidentes/",
    "/salud/", "/bienestar/", "/medicina/",
    "/tag/", "/tags/",
]

# Patrones de actores politicos (si aparecen, se mantiene aunque sea seccion excluida)
PATRONES_ACTORES_POLITICOS = [
    # Actores políticos
    r"\bpresidente\b", r"\bpresidenta\b", r"\bgobierno\b", r"\bministerio\b",
    r"\bministro\b", r"\bministra\b", r"\bcongreso\b", r"\bsenado\b",
    r"\bsenador\b", r"\bsenadora\b", r"\bdiputado\b", r"\bdiputada\b",
    r"\bgovernador\b", r"\bgovernadora\b", r"\balcalde\b", r"\balcaldesa\b",
    r"\bsecretario\b", r"\bsecretaria\b", r"\bfuncionario\b", r"\bautoridad\b",
    # Entidades gubernamentales
    r"\bsecretar[ií]a\b", r"\bdependencia\b", r"\borganismo\b",
    r"\bcomit[eé]\b", r"\bconsejo\b", r"\binstituto\b", r"\bagencia\b",
    r"\bcomisi[oó]n\b", r"\bdirecci[oó]n\b", r"\bsubsecretar[ií]a\b",
    r"\bgobierno\b.*\bestatal\b", r"\bestado\b.*\bemiti[oó]\b",
    r"\bcomunicado\b.*\boficial\b",
    # Contextos gubernamentales
    r"\bpalacio\b", r"\bcasa de gobierno\b", r"\bnaci[oó]n\b",
    r"\bestado\b", r"\bgabinete\b", r"\bpol[ií]tica\b.*\boficial\b",
    # Siglas específicas
    r"\bSegam\b", r"\bSedema\b", r"\bSemarnat\b", r"\bINE\b",
    r"\bINAH\b", r"\bSAT\b", r"\bBNCR\b",
]

RE_POLITICOS = re.compile("|".join(PATRONES_ACTORES_POLITICOS), re.IGNORECASE)

PATRONES_ACTORES_ECONOMICOS = [
    r"\bYPF\b", r"\bShell\b", r"\bExxon\b", r"\bTenaris\b", r"\bTernium\b",
    r"\bBanco\s*(?:de\s*la\s*Nación|Santander|Provincia|Galicia|HSBC|BBVA|Citibank)\b",
    r"\bFord\b", r"\bVolkswagen\b", r"\bToyota\b", r"\bGeneral\s*Motors\b", r"\bFiat\b",
    r"\bArcor\b", r"\bMolinos\b", r"\bCoca-Cola\b", r"\bPepsi\b",
    r"\bAES\b", r"\bEdenor\b", r"\bEdesur\b", r"\bCammesa\b",
    r"\bVaca\s*Muerta\b", r"\bpuerto\s*de\s*[A-Z]\w+\b", r"\bexportaciones?\b.*\bgranos\b",
    r"\bBolsa\b.*\bValores\b", r"\bMerval\b", r"\bBCRA\b", r"\bBanco\s*Central\b",
    r"\bfábrica\b", r"\bplanta\b.*\bindustrial\b", r"\bcomplejo\s*agroindustrial\b",
    r"\bminera\b", r"\bminería\b", r"\blitio\b", r"\bcobre\b",
]

PATRONES_ACTORES_SINDICALES = [
    r"\bCGT\b", r"\bCTA\b", r"\bCamioneros\b", r"\bUOM\b", r"\bSMATA\b",
    r"\bsindicato\b", r"\bgremio\b", r"\bgremial\b", r"\bparitaria\b",
    r"\bhuelga\b", r"\bparo\b", r"\bconvenio\s*colectivo\b",
    r"\bconflicto\s*laboral\b", r"\bnegociación\s*salarial\b",
]

RE_ECONOMICOS = re.compile("|".join(PATRONES_ACTORES_ECONOMICOS), re.IGNORECASE)
RE_SINDICALES = re.compile("|".join(PATRONES_ACTORES_SINDICALES), re.IGNORECASE)


async def fetch_page_content(url: str, wait_ms: int = 2000) -> Optional[str]:
    """Fetch page HTML content using httpx (for static sites)."""
    try:
        async with httpx.AsyncClient(
            timeout=30.0,
            follow_redirects=True,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            }
        ) as client:
            response = await client.get(url)
            response.raise_for_status()
            return response.text
    except Exception as e:
        logger.error(f"Error fetching {url}: {e}")
        return None


def extract_article_links(html: str, base_url: str, config: dict) -> list[dict]:
    """Extract article links from a listing page."""
    soup = BeautifulSoup(html, "html.parser")
    links = []

    link_selector = config.get("link_selector", "a")
    titulo_selector = config.get("titulo_selector", None)

    elements = soup.select(link_selector)

    for el in elements[:50]:  # Limit to 50 articles per scan
        href = el.get("href", "")
        if not href:
            continue

        # Normalize URL
        if href.startswith("/"):
            href = base_url.rstrip("/") + href
        elif not href.startswith("http"):
            href = base_url.rstrip("/") + "/" + href

        # Extract title if selector provided
        title = ""
        if titulo_selector:
            title_el = el.select_one(titulo_selector)
            if title_el:
                title = title_el.get_text(strip=True)
        elif el.get_text(strip=True):
            title = el.get_text(strip=True)

        if href and "/nota/" in href or "/article/" in href or len(href) > len(base_url) + 20:
            links.append({
                "url": href,
                "titulo": title[:500] if title else "",
                "hash": hashlib.sha256(href.encode()).hexdigest()
            })

    # Deduplicate by hash
    seen = set()
    unique_links = []
    for link in links:
        if link["hash"] not in seen:
            seen.add(link["hash"])
            unique_links.append(link)

    return unique_links


def extract_article_content(html: str, config: dict) -> dict:
    """Extract article body text from an article page."""
    soup = BeautifulSoup(html, "html.parser")

    contenido_selector = config.get("contenido_selector", "article")
    fecha_selector = config.get("fecha_selector", "time")

    # Extract body text
    content_el = soup.select_one(contenido_selector)
    texto = ""
    if content_el:
        # Remove script and style tags
        for tag in content_el.find_all(["script", "style", "nav", "footer"]):
            tag.decompose()
        texto = content_el.get_text(separator="\n", strip=True)
    else:
        # Fallback: try article tag or main content
        for fallback in ["article", "main", ".article-body", ".nota-body", "#article-body"]:
            content_el = soup.select_one(fallback)
            if content_el:
                for tag in content_el.find_all(["script", "style", "nav", "footer"]):
                    tag.decompose()
                texto = content_el.get_text(separator="\n", strip=True)
                break

    # Extract date
    fecha = None
    date_el = soup.select_one(fecha_selector)
    if date_el:
        datetime_attr = date_el.get("datetime", "")
        if datetime_attr:
            try:
                fecha = datetime.fromisoformat(datetime_attr.replace("Z", "+00:00"))
            except ValueError:
                pass

    # Extract title from page
    titulo = ""
    title_el = soup.select_one("h1")
    if title_el:
        titulo = title_el.get_text(strip=True)

    return {
        "texto": texto[:50000],  # Limit text length
        "fecha": fecha,
        "titulo": titulo[:500]
    }


def run_scan(fuente_id: int):
    """Synchronous wrapper to run a scan in a background task."""
    import asyncio
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(_async_scan(fuente_id))
    except Exception as e:
        logger.error(f"Error in scan for fuente {fuente_id}: {e}")
    finally:
        loop.close()


async def _async_scan(fuente_id: int):
    """Run a full scan of a source."""
    from app.core.database import SessionLocal
    from app.models.fuente import Fuente
    from app.models.articulo import Articulo

    db = SessionLocal()
    try:
        fuente = db.query(Fuente).filter(Fuente.id == fuente_id).first()
        if not fuente:
            logger.error(f"Fuente {fuente_id} not found")
            return

        logger.info(f"Starting scan of '{fuente.nombre}' ({fuente.url_base})")

        config = fuente.selectores_config or {}
        secciones = fuente.secciones or [{"url": ""}]
        total_new = 0

        for seccion in secciones:
            section_url = seccion.get("url", "")
            if section_url.startswith("/"):
                scan_url = fuente.url_base.rstrip("/") + section_url
            elif section_url.startswith("http"):
                scan_url = section_url
            else:
                scan_url = fuente.url_base.rstrip("/") + "/" + section_url

            # Fetch listing page
            html = await fetch_page_content(scan_url)
            if not html:
                fuente.estado = "error"
                fuente.ultimo_error = f"No se pudo acceder a {scan_url}"
                db.commit()
                continue

            # Extract links
            links = extract_article_links(html, fuente.url_base, config)
            logger.info(f"Found {len(links)} links in {scan_url}")

            for link_data in links:
                # Check for duplicates
                existing = db.query(Articulo).filter(
                    Articulo.url_hash == link_data["hash"]
                ).first()
                if existing:
                    continue

                # Filter: check if should be loaded based on HECHO
                if _es_seccion_excluida(link_data["url"]):
                    # Fetch para verificar contexto politico
                    article_html = await fetch_page_content(link_data["url"])
                    if not article_html:
                        continue
                    content = extract_article_content(article_html, config)
                    if not _tiene_contexto_politico(content["texto"]):
                        logger.debug(f"Skipping excluded section without context: {link_data['url']}")
                        continue
                else:
                    # Para todas las demas URLs, verificar HECHO
                    article_html = await fetch_page_content(link_data["url"])
                    if not article_html:
                        continue
                    content = extract_article_content(article_html, config)
                    if not _tiene_hecho(content["texto"]):
                        logger.debug(f"Skipping: no tiene HECHO - {link_data['url']}")
                        continue

                if not content["texto"] or len(content["texto"]) < 100:
                    continue

                articulo = Articulo(
                    fuente_id=fuente.id,
                    url=link_data["url"],
                    url_hash=link_data["hash"],
                    titulo_original=content["titulo"] or link_data["titulo"],
                    texto_crudo=content["texto"],
                    fecha_publicacion=content["fecha"],
                    nombre_medio=fuente.nombre,
                    estado="crudo"
                )
                db.add(articulo)
                total_new += 1

        fuente.ultimo_escaneo = datetime.now(timezone.utc)
        fuente.articulos_extraidos_total = (fuente.articulos_extraidos_total or 0) + total_new
        fuente.estado = "activa"
        fuente.ultimo_error = None
        db.commit()

        logger.info(f"Scan complete for '{fuente.nombre}': {total_new} new articles")
        logger.info(f"Articles left in 'crudo' state - triggering big-pickle processing")
        
        # Automatically trigger fill_approve_queue.py processing
        import subprocess
        import sys
        script_path = os.path.join(os.path.dirname(__file__), "..", "..", "..", "fill_approve_queue.py")
        script_path = os.path.abspath(script_path)
        
        def run_fill_approve_queue():
            """Run fill_approve_queue.py in background."""
            try:
                subprocess.Popen([
                    sys.executable, script_path
                ], 
                stdout=subprocess.DEVNULL, 
                stderr=subprocess.DEVNULL,
                start_new_session=True
                )
                logger.info(f"Triggered fill_approve_queue.py for big-pickle processing")
            except Exception as e:
                logger.error(f"Failed to trigger fill_approve_queue.py: {e}")
        
        # Run in a separate thread to not block the scan
        import threading
        thread = threading.Thread(target=run_fill_approve_queue)
        thread.daemon = True
        thread.start()
        
    except Exception as e:
        logger.error(f"Scan error for fuente {fuente_id}: {e}")
        if fuente:
            fuente.estado = "error"
            fuente.ultimo_error = str(e)
            db.commit()
    finally:
        db.close()


async def _process_single_article(articulo_id: int, db):
    """Process article through filtering and AI analysis."""
    from app.services.ia_processor import analyze_article
    from app.models.articulo import Articulo

    articulo = db.query(Articulo).filter(Articulo.id == articulo_id).first()
    if not articulo or articulo.estado != "crudo":
        return
    
    if _debe_filtrar_articulo(articulo.url, articulo.texto_crudo or ""):
        articulo.estado = "filtrado"
        articulo.motive_no_relevante = "Seccion excluida sin hecho institucional"
        db.commit()
        return
    
    # Now use big-pickle to analyze the article
    await analyze_article(articulo, db)


def extract_and_process_article(articulo_id: int):
    """Process a manually added article."""
    import asyncio
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(_extract_and_process(articulo_id))
    except Exception as e:
        logger.error(f"Error processing article {articulo_id}: {e}")
    finally:
        loop.close()


async def _extract_and_process(articulo_id: int):
    """Extract content from a manually added link and process it."""
    from app.core.database import SessionLocal
    from app.models.articulo import Articulo
    
    db = SessionLocal()
    try:
        articulo = db.query(Articulo).filter(Articulo.id == articulo_id).first()
        if not articulo:
            return
        
        # If already processed, skip
        if articulo.estado != "crudo":
            return
        
        # Fetch article
        html = await fetch_page_content(articulo.url)
        if not html:
            articulo.estado = "error"
            db.commit()
            return
        
        content = extract_article_content(html, {})
        articulo.texto_crudo = content["texto"]
        articulo.titulo_original = content["titulo"]
        articulo.fecha_publicacion = content["fecha"]
        db.commit()
        
        # Process through AI
        await _process_single_article(articulo.id, db)
        
    finally:
        db.close()
