"""
Agente 1 — TrendAgent
Elige el tema del próximo video.

Estrategia barata (sin APIs de pago de "trends"):
  1. Usa el LLM para proponer temas evergreen + de actualidad del nicho.
  2. (Opcional) cruza con títulos que están rindiendo en YouTube vía Data API.
  3. El FeedbackAgent puede pasar aquí qué temas rindieron para sesgar la elección.

Salida: dict {topic, angle, format, target_keyword, rationale}
"""
from config import settings
from pipeline.common import ask_llm_json, get_logger

log = get_logger("TrendAgent")

SYSTEM = (
    "You are a YouTube growth strategist specialized in the personal-finance "
    "and investing niche for an English-speaking audience. You pick topics that "
    "balance search demand, evergreen value, and a differentiated angle. You "
    "avoid generic clickbait and never give specific buy/sell recommendations."
)


def _realtime_block() -> str:
    """Trae señales en tiempo real (RSS/Reddit/Trends) para inspirar el tema."""
    if not settings.USE_REALTIME_TOPICS:
        return ""
    try:
        from integrations import topic_sources
        signals = topic_sources.gather(use_trends=settings.USE_GOOGLE_TRENDS)
    except Exception as e:
        log.warning("No pude traer temas en tiempo real: %s", e)
        return ""
    if not signals:
        return ""
    lines = [f"- [{s['source']}] {s['text']}" for s in signals[:25]]
    return ("\nHOT RIGHT NOW (real signals from finance news, Reddit and trends — "
            "use these to pick a timely, in-demand topic; adapt, don't copy):\n"
            + "\n".join(lines))


def pick_topic(video_format: str, recent_winners: list[str] | None = None) -> dict:
    """
    video_format: 'short' o 'long'
    recent_winners: títulos/temas que ya rindieron (del FeedbackAgent)
    """
    fmt = "a <60s vertical Short with one punchy idea" if video_format == "short" \
        else "an 8-minute long-form video with depth and structure"
    winners = ""
    if recent_winners:
        winners = (
            "\nThese past topics performed well — lean toward similar demand "
            "but do NOT repeat them:\n- " + "\n- ".join(recent_winners)
        )
    realtime = _realtime_block()

    prompt = f"""
Pick ONE video topic for a finance channel. Format: {fmt}.
Sub-topics in scope: {", ".join(settings.SUBTOPICS)}.{winners}{realtime}

Return JSON:
{{
  "topic": "concrete video subject",
  "angle": "the specific differentiated take / hook idea",
  "format": "{video_format}",
  "target_keyword": "main SEO keyword",
  "rationale": "1 sentence: why this earns views AND is monetizable"
}}
"""
    result = ask_llm_json(prompt, SYSTEM, max_tokens=600)
    result["format"] = video_format
    log.info("Tema elegido (%s): %s", video_format, result.get("topic"))
    return result
