"""
Motor de Procesamiento IA — Genera registros editoriales a partir de artículos crudos.
Soporta: Anthropic Claude, OpenAI GPT, y modo mock para desarrollo sin API key.
"""
import json
import logging
from datetime import datetime, timezone
from typing import Optional
from app.core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

# Default processing prompt
DEFAULT_PROMPT = """Eres un analista editorial experto. Analiza la siguiente noticia y genera un registro estructurado en formato JSON.

REGLAS IMPORTANTES:
1. QUÉ: Describe el acontecimiento principal SIN subjetividad periodística. Debe ser una oración completa con acción, actores y lugar. Excluye análisis, adjetivación y opinión del periodista.
2. QUIÉN: Nombre del actor, su función/cargo y declaración textual (entre comillas si la original lo está). Excluye texto agregado por el periodista fuera de comillas.
3. POR QUÉ: Contexto y antecedentes mencionados en la nota. Solo hechos anteriores que el periodista recupera, NO acciones del día de la noticia.
4. DATOS: Cifras, números, estadísticas o información cuantitativa relevante mencionada en la nota.
5. TÍTULO: Oración breve con verbo en pasado + sujeto (actor) + predicado (contexto). Debe ser inteligible por sí misma.
6. TAGS: Lista de actores mencionados (quién, con quién, contra quién), separados por comas.
7. SECTOR: Clasifica según la ACTIVIDAD DEL ACTOR PRINCIPAL de la noticia:

   - AGENDA: Conflictos armados, diplomacia, cumbre de líderes, política internacional, organismos internacionales (ONU, FMI, Banco Mundial), relaciones exteriores, negociaciones de paz, terrorismo,举手, FFAA. Si hay presidents, prim ministers,外交官, generale, la respuesta es AGENDA.
   - TRABAJADORES: sindicatos, huelgas, convenios colectivos, condiciones laborales, gremios.
   - FINANZAS: bancos, mercados bursátiles, tipo de cambio, inflación, tasas de interés, inversores.
   - ENERGÍA: petróleo, gas, electricidad, empresas energéticas, renovable.
   - AGRO: campo, agricultura, ganadería, cereales, exportaciones agrícolas.
   - INDUSTRIAL: fábricas, manufactura, producción industrial, empresas que NO sean energéticas ni financieras.

8. ÓRBITA: POLÍTICA (si hay actor político/government), ECONOMÍA (solo actores privados económicos), ESTRATEGIA (FFAA, medios, consultoras).
9. GÉNERO: "nota" o "opinión".
10. ÁMBITO: provincial, nacional, latinoamericano, internacional.
11. REGIÓN: Solo si el ámbito es provincial (nombre de la región) o latinoamericano (nombre del país).
12. RELEVANTE: true si la nota contiene un actor que realiza una acción o declaración, false si no.
13. MOTIVO_NO_RELEVANTE: Si no es relevante, explica brevemente por qué.

Si la nota contiene MÚLTIPLES acciones diferenciadas del mismo día, genera un registro por cada acción (devuelve un array).

EJEMPLOS DE CLASIFICACIÓN:
- "Trump dijo X sobre Iran" → sector=AGENDA
- "Hezbollah amenazó a Israel" → sector=AGENDA
- "Aeropuerto de Tehran retoma vuelos" → sector=AGENDA (es notícia política/internacional)
- "Apple presentó nuevo iPhone" → sector=INDUSTRIAL
- "BCRA bajó tasas" → sector=FINANZAS
- "CGT llamó a huelga" → sector=TRABAJADORES
- "YPF informó ganancias" → sector=ENERGÍA

Responde SOLO con JSON válido, sin texto adicional. Formato:
{
  "relevante": true/false,
  "motivo_no_relevante": "...",
  "registros": [
    {
      "que": "...",
      "quien": "...",
      "porque": "...",
      "datos": "...",
      "titulo": "...",
      "tags": "actor1, actor2",
      "sector": "AGENDA|INDUSTRIAL|AGRO|ENERGÍA|FINANZAS|TRABAJADORES",
      "orbita": "POLÍTICA|ECONOMÍA|ESTRATEGIA",
      "genero": "nota|opinión",
      "ambito": "provincial|nacional|latinoamericano|internacional",
      "region": "..."
    }
  ]
}

NOTICIA A ANALIZAR:
Título: {titulo}
Fuente: {fuente}
Texto:
{texto}
"""


async def process_article(articulo, db):
    """Process a single article through the AI pipeline."""
    from app.models.articulo import Articulo
    from app.models.registro import Registro
    from app.models.prompt import Prompt

    if not articulo.texto_crudo or len(articulo.texto_crudo) < 50:
        articulo.estado = "no_relevante"
        articulo.motivo_no_relevante = "Texto demasiado corto para procesar"
        db.commit()
        return

    # Get active prompt or use default
    prompt_record = db.query(Prompt).filter(
        Prompt.activo == True,
        Prompt.tipo == "procesamiento"
    ).first()

    prompt_template = prompt_record.contenido if prompt_record else DEFAULT_PROMPT

    # Build the prompt
    prompt_text = prompt_template.replace("{titulo}", articulo.titulo_original or "Sin título")
    prompt_text = prompt_text.replace("{fuente}", articulo.nombre_medio or "Desconocida")
    prompt_text = prompt_text.replace("{texto}", articulo.texto_crudo[:8000])

    # Call LLM
    result = await call_llm(prompt_text)

    if not result:
        articulo.estado = "error"
        db.commit()
        return

    try:
        data = json.loads(result)
    except json.JSONDecodeError:
        # Try to extract JSON from response
        try:
            start = result.index("{")
            end = result.rindex("}") + 1
            data = json.loads(result[start:end])
        except (ValueError, json.JSONDecodeError):
            logger.error(f"Invalid JSON response for article {articulo.id}")
            articulo.estado = "error"
            db.commit()
            return

    # Check relevance
    if not data.get("relevante", True):
        articulo.estado = "no_relevante"
        articulo.motivo_no_relevante = data.get("motivo_no_relevante", "La IA determinó que no es relevante")
        db.commit()
        return

    # Create records
    registros_data = data.get("registros", [data] if "que" in data else [])

    for reg_data in registros_data:
        registro = Registro(
            articulo_id=articulo.id,
            fuente=articulo.nombre_medio or "Desconocida",
            fecha=articulo.fecha_publicacion or datetime.now(timezone.utc),
            link=articulo.url,
            que=reg_data.get("que", ""),
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
    """Call the configured LLM provider."""
    # Forzamos "opencode" para ignorar cualquier variable de entorno trabada en "mock"
    provider = "opencode"

    if provider == "mock":
        return _mock_llm_response(prompt)
    elif provider == "anthropic":
        return await _call_anthropic(prompt)
    elif provider in ("openai", "opencode"):
        return await _call_openai(prompt)
    else:
        logger.error(f"Unknown LLM provider: {provider}")
        return _mock_llm_response(prompt)


def _mock_llm_response(prompt: str) -> str:
    """Generate a mock response for development without API key."""
    import re

    # Extract title and source from prompt
    titulo_match = re.search(r"Título: (.+)", prompt)
    fuente_match = re.search(r"Fuente: (.+)", prompt)
    titulo = titulo_match.group(1) if titulo_match else "Noticia sin título"
    fuente = fuente_match.group(1) if fuente_match else "Medio desconocido"

    # Extract some text for mock data
    texto_match = re.search(r"Texto:\n(.+?)(?:\n\n|\Z)", prompt, re.DOTALL)
    texto = texto_match.group(1)[:500] if texto_match else ""

    # Simple keyword detection for sector/orbita
    texto_lower = texto.lower() + " " + titulo.lower()

    sector = "AGENDA"
    orbita = "POLÍTICA"
    if any(w in texto_lower for w in ["sindicato", "gremio", "cgt", "cta", "trabajador", "paro", "huelga"]):
        sector = "TRABAJADORES"
    elif any(w in texto_lower for w in ["banco", "dólar", "inflación", "bcra", "financier"]):
        sector = "FINANZAS"
        orbita = "ECONOMÍA"
    elif any(w in texto_lower for w in ["petróleo", "gas", "energía", "ypf", "minería"]):
        sector = "ENERGÍA"
        orbita = "ECONOMÍA"
    elif any(w in texto_lower for w in ["campo", "soja", "trigo", "agro", "ganadería"]):
        sector = "AGRO"
        orbita = "ECONOMÍA"
    elif any(w in texto_lower for w in ["industria", "fábrica", "manufactura", "producción"]):
        sector = "INDUSTRIAL"
        orbita = "ECONOMÍA"

    if any(w in texto_lower for w in ["presidente", "gobierno", "ministro", "congreso", "diputado", "senador"]):
        orbita = "POLÍTICA"

    # Determine genre
    genero = "opinión" if any(w in texto_lower for w in ["opinión", "editorial", "columna", "análisis"]) else "nota"

    # Determine scope
    ambito = "nacional"
    region = ""
    if any(w in texto_lower for w in ["eeuu", "trump", "biden", "europa", "china", "rusia"]):
        ambito = "internacional"
    elif any(w in texto_lower for w in ["brasil", "chile", "uruguay", "paraguay", "bolivia", "méxico"]):
        ambito = "latinoamericano"
        for pais in ["Brasil", "Chile", "Uruguay", "Paraguay", "Bolivia", "México", "Colombia", "Perú", "Venezuela"]:
            if pais.lower() in texto_lower:
                region = pais
                break

    # Build mock response
    que = f"[MOCK IA] Acontecimiento relacionado con {sector.lower()} según el artículo de {fuente}."
    quien = f"[MOCK IA] Actores mencionados en la noticia."
    porque = f"[MOCK IA] Contexto generado automáticamente (requiere API key real para procesamiento editorial completo)."
    datos = f"[MOCK IA] Datos cuantitativos del artículo."

    titulo_gen = titulo if genero == "opinión" else f"[MOCK] {titulo[:100]}"

    response = {
        "relevante": True,
        "registros": [{
            "que": que,
            "quien": quien,
            "porque": porque,
            "datos": datos,
            "titulo": titulo_gen,
            "tags": "Actor 1, Actor 2",
            "sector": sector,
            "orbita": orbita,
            "genero": genero,
            "ambito": ambito,
            "region": region
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


LAST_IA_ERROR = "No errors yet"

def get_last_error():
    return LAST_IA_ERROR

async def _call_openai(prompt: str) -> Optional[str]:
    """Call OpenAI GPT API or compatible providers like Opencode."""
    global LAST_IA_ERROR
    try:
        from openai import OpenAI
        api_key = settings.LLM_API_KEY
        base_url = settings.LLM_BASE_URL
        
        # Lista de modelos prioritarios recomendados por el usuario
        models_to_try = [settings.LLM_MODEL, "big-pickle", "minimax-m2.5-free", "gpt-4o", "gpt-4o-mini"]
        
        client = OpenAI(api_key=api_key, base_url=base_url)
        
        last_exception = None
        for model_name in models_to_try:
            try:
                LAST_IA_ERROR = f"Iniciando llamada con modelo: {model_name}"
                response = client.chat.completions.create(
                    model=model_name,
                    messages=[{"role": "user", "content": prompt}],
                    max_tokens=4000,
                    temperature=0.3
                )
                # Si llegamos aquí, funcionó
                LAST_IA_ERROR = f"Éxito con modelo: {model_name}"
                return response.choices[0].message.content
            except Exception as e:
                last_exception = e
                logger.warning(f"Model {model_name} failed: {e}")
                continue
        
        # Si todos fallaron
        LAST_IA_ERROR = f"Todos los modelos fallaron. Último error: {str(last_exception)}"
        logger.error(LAST_IA_ERROR)
        return None
    except Exception as e:
        LAST_IA_ERROR = f"Error general en _call_openai: {str(e)}"
        logger.error(LAST_IA_ERROR)
        return None
