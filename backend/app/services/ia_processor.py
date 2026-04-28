"""
Motor de Procesamiento IA — Genera registros editoriales a partir de artículos crudos.
Soporta: Opencode (big-pickle), OpenAI, Anthropic Claude.
"""
import json
import logging
import re
from datetime import datetime, timezone
from typing import Optional
from app.core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

# Prompt por defecto (se usa si no hay prompt activo en DB)
DEFAULT_PROMPT = """Eres un analista editorial experto. Analiza la siguiente noticia y genera un registro estructurado en formato JSON.

FORMATO ESTRICTO PARA EL CAMPO "QUE":
El QUE es el titular principal de la noticia. Debe seguir esta estructura EXACTA:

"NOMBRE PROPIO, cargo/funcion del actor, verbo de accion con complemento completo"

REGLAS:
1. PRIMERA palabra: Nombre propio del actor (ej: Khatam Al-Anbiya, Donald Trump, Milei)
2. SEGUNDO: coma, LUEGO cargo (ej: presidente de Estados Unidos, ministro de Economia)
3. TERCERO: coma, LUEGO verbo conjugado + complemento COMPLETO
4. PROHIBIDO empezar con pais ni sector: "Argentina, sector..." o "Economia, sector..." es INCORRECTO
5. PROHIBIDO empezar con articulos: El, La, Los, Las, Un, Una, Se, Esto, Esta
6. PROHIBIDO repetir el nombre: "Nombre, cargo Nombre verbo" es INCORRECTO
7. ORACION COMPLETA: termina en punto o fin natural, nunca cortada
8. SOLO procesar si hay un HECHO: presencia de actor institucional (politico, economico o sindical)

EJEMPLOS DE BUEN QUE:
✓ "Khatam Al-Anbiya, comandante central del ejercito de Iran, afirmo que el ejercito estadounidense invasor continua con el bloqueo"
✓ "Luis Caputo, ministro de Economia, ofrecio renovar $7,9 billones en bonos de deuda"
✓ "El Congreso argentino, camara de diputados, aprobo la ley de reforma laboral"

SECTORES VÁLIDOS: AGENDA, INDUSTRIAL, AGRO, ENERGÍA, FINANZAS, TRABAJADORES
SOLO usa INDUSTRIAL si el texto menciona "fábrica" o "planta industrial"
SOLO usa ENERGÍA si menciona empresas energéticas (YPF, Shell, Exxon) o recursos energéticos
SOLO usa AGRO si menciona campo, granos, soja, trigo, ganadería
SOLO usa FINANZAS si menciona índices bursátiles, tipo de cambio, tasas del banco central
SOLO usa TRABAJADORES si menciona sindicatos, huelgas, convenios colectivos
TODO OTRO = AGENDA

Responde SOLO con JSON válido (sin texto extra antes o después):
{"relevante":true,"registros":[{"que":"...","quien":"...","porque":"...","datos":"...","titulo":"...","tags":"...","sector":"AGENDA","orbita":"POLÍTICA","genero":"nota","ambito":"internacional","region":""}]}

NOTICIA:
Título: {titulo}
Fuente: {fuente}
Texto: {texto}
"""

async def analyze_article(articulo, db):
    """Analyze article using big-pickle (or configured LLM)."""
    from app.models.registro import Registro
    from app.models.prompt import Prompt
    
    # Validar texto crudo
    if not articulo.texto_crudo or len(articulo.texto_crudo) < 50:
        articulo.estado = "no_relevante"
        articulo.motivo_no_relevante = "Texto demasiado corto para procesar"
        db.commit()
        return
    
    # Obtener prompt activo de DB (tipo="procesamiento")
    prompt_record = db.query(Prompt).filter(
        Prompt.activo == True,
        Prompt.tipo == "procesamiento"
    ).first()
    
    prompt_template = prompt_record.contenido if prompt_record else DEFAULT_PROMPT
    
    # Construir prompt
    prompt_text = prompt_template.replace("{titulo}", articulo.titulo_original or "Sin título")
    prompt_text = prompt_text.replace("{fuente}", articulo.nombre_medio or "Desconocida")
    prompt_text = prompt_text.replace("{texto}", articulo.texto_crudo[:8000])
    
    # Llamar a big-pickle (u otro LLM)
    result = await call_llm(prompt_text)
    
    if not result:
        articulo.estado = "error"
        db.commit()
        return
    
    # Parsear JSON (con reintentos para big-pickle)
    data = None
    try:
        data = json.loads(result)
    except json.JSONDecodeError:
        # Intentar extraer JSON de la respuesta (big-pickle a veces agrega texto)
        try:
            start = result.index("{")
            end = result.rindex("}") + 1
            data = json.loads(result[start:end])
        except (ValueError, json.JSONDecodeError):
            logger.error(f"Invalid JSON response for article {articulo.id}")
            articulo.estado = "error"
            db.commit()
            return
    
    # Verificar si es relevante
    if not data.get("relevante", True):
        articulo.estado = "no_relevante"
        articulo.motivo_no_relevante = data.get("motivo_no_relevante", "La IA determinó que no es relevante")
        db.commit()
        return
    
    # Crear registros - FORZAR 1 solo por artículo (tomar el primero)
    registros_data = data.get("registros", [data] if "que" in data else [])
    # Si hay múltiples, tomar solo el primero
    if isinstance(registros_data, list) and len(registros_data) > 1:
        registros_data = [registros_data[0]]
    
    for reg_data in registros_data:
        que_original = reg_data.get("que", "")
        quien_original = reg_data.get("quien", "")
        
        # Corregir QUE si empieza con artículo
        que_final = _corregir_que_si_necesario(que_original, quien_original)
        
        registro = Registro(
            articulo_id=articulo.id,
            fuente=articulo.nombre_medio or "Desconocida",
            fecha=articulo.fecha_publicacion or datetime.now(timezone.utc),
            link=articulo.url,
            que=que_final,
            que_origen="ia",
            quien=reg_data.get("quien", ""),
            quien_origen="ia",
            porque=reg_data.get("porque", ""),
            porque_origen="ia",
            datos=reg_data.get("datos", ""),
            datos_origen="ia",
            titulo=reg_data.get("titulo", ""),
            titulo_origen="ia",
            tags=reg_data.get("tags", ""),
            tags_origen="ia",
            sector=reg_data.get("sector", ""),
            sector_origen="ia",
            orbita=reg_data.get("orbita", ""),
            orbita_origen="ia",
            genero=reg_data.get("genero", "nota"),
            ambito=reg_data.get("ambito", "nacional"),
            region=reg_data.get("region", ""),
            estado="procesado",
            correcciones_json=[]
        )
        db.add(registro)
    
    articulo.estado = "procesado"
    db.commit()
    logger.info(f"Article {articulo.id} processed: {len(registros_data)} record(s) created")


async def call_llm(prompt: str) -> Optional[str]:
    """Call the configured LLM provider (big-pickle por defecto)."""
    provider = settings.LLM_PROVIDER.lower()
    
    if provider == "mock":
        return _mock_llm_response(prompt)
    elif provider == "anthropic":
        return await _call_anthropic(prompt)
    elif provider in ("openai", "opencode"):
        return await _call_openai(prompt)
    else:
        logger.error(f"Unknown LLM provider: {provider}")
        return None


def _mock_llm_response(prompt: str) -> str:
    """Mock response for development."""
    import re
    
    titulo_match = re.search(r"Título: (.+)", prompt)
    fuente_match = re.search(r"Fuente: (.+)", prompt)
    titulo = titulo_match.group(1) if titulo_match else "Noticia sin título"
    fuente = fuente_match.group(1) if fuente_match else "Medio desconocido"
    
    response = {
        "relevante": True,
        "registros": [{
            "que": f"[MOCK] Acontecimiento relacionado con {fuente}",
            "quien": "[MOCK] Actores mencionados",
            "porque": "[MOCK] Contexto generado automáticamente",
            "datos": "[MOCK] Datos cuantitativos",
            "titulo": titulo,
            "tags": "Actor 1, Actor 2",
            "sector": "AGENDA",
            "orbita": "POLÍTICA",
            "genero": "nota",
            "ambito": "nacional",
            "region": ""
        }]
    }
    return json.dumps(response, ensure_ascii=False)


async def _call_anthropic(prompt: str) -> Optional[str]:
    """Call Anthropic Claude API."""
    try:
        import anthropic
        client = anthropic.Anthropic(api_key=settings.LLM_API_KEY)
        message = client.messages.create(
            model=settings.LLM_MODEL,
            max_tokens=4000,
            messages=[{"role": "user", "content": prompt}]
        )
        return message.content[0].text
    except Exception as e:
        logger.error(f"Anthropic API error: {e}")
        return None


async def _call_openai(prompt: str) -> Optional[str]:
    """Call OpenAI API or compatible providers (like big-pickle)."""
    try:
        from openai import OpenAI
        
        # Lista de modelos a probar (big-pickle primero)
        models_to_try = [settings.LLM_MODEL, "big-pickle", "gpt-4o", "gpt-4o-mini"]
        client = OpenAI(api_key=settings.LLM_API_KEY, base_url=settings.LLM_BASE_URL)
        
        for model_name in models_to_try:
            try:
                response = client.chat.completions.create(
                    model=model_name,
                    messages=[{"role": "user", "content": prompt}],
                    max_tokens=4000,
                    temperature=0.3
                )
                return response.choices[0].message.content
            except Exception as e:
                logger.warning(f"Model {model_name} failed: {e}")
                continue
        
        logger.error("All models failed in _call_openai")
        return None
    except Exception as e:
        logger.error(f"General error in _call_openai: {e}")
        return None


# Patrones para corregir QUE
ARTICULOS_INICIALES = ("el", "la", "los", "las", "un", "una", "se", "esto", "esta")
ARTICULOS_INICIALES_REG = r"^(el|la|los|las|un|una|se|esto|esta)\s+"
REGEX_ARTICULOS = re.compile(ARTICULOS_INICIALES_REG, re.IGNORECASE)


def _que_tiene_problema(que: str) -> bool:
    """Check if QUE starts with an article instead of an actor."""
    if not que:
        return True
    return bool(REGEX_ARTICULOS.match(que.lower()))


def _corregir_que_si_necesario(que: str, quien: str) -> str:
    """Corrige un QUE que empieza con artículo."""
    if not _que_tiene_problema(que):
        return que
    
    # Extraer nombre de QUIEN
    quien_nombre = ""
    if quien:
        parte_nombre = quien.split(",")[0].strip()
        if parte_nombre:
            quien_nombre = parte_nombre
    
    if not quien_nombre:
        return que
    
    # Remover artículo inicial y reconstruir
    article_match = REGEX_ARTICULOS.match(que)
    if not article_match:
        return que
    
    article_len = article_match.end()
    que_sin_articulo = que[article_len:]
    que_corregido = f"{quien_nombre}, {que_sin_articulo}"
    
    return que_corregido if not _que_tiene_problema(que_corregido) else que
