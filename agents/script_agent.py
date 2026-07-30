"""
Agente 2 — ScriptAgent
Convierte el tema en un guion estructurado y optimizado para retención.

Salida: dict {
  title, hook, segments[{narration, visual_query, on_screen_text}],
  cta, description, tags[], disclaimer
}
El guion se divide en segmentos: cada uno tiene la narración (para TTS),
una query de stock (para VisualAgent) y texto en pantalla (subtítulo destacado).
"""
from config import settings
from pipeline.common import ask_llm_json, get_logger

log = get_logger("ScriptAgent")

SYSTEM = (
    "You are an expert finance-content scriptwriter. You write for retention: "
    "a 5-second hook, tight pacing, concrete examples and numbers, and a clear "
    "call to action. You write EDUCATIONAL content, never specific financial "
    "advice or buy/sell calls. Your narration sounds natural when read aloud by "
    "a text-to-speech voice (short sentences, no complex punctuation)."
)


def write_script(topic: dict) -> dict:
    is_short = topic["format"] == "short"
    length_rule = (
        "6 to 9 segments, ~10-15 words of narration each. Total under 55 seconds."
        if is_short else
        "10 to 14 segments, ~40-70 words of narration each. Total ~8 minutes."
    )

    prompt = f"""
Write a YouTube {'Short' if is_short else 'long-form'} script.

TOPIC: {topic['topic']}
ANGLE: {topic['angle']}
TARGET KEYWORD: {topic['target_keyword']}

Rules:
- {length_rule}
- First segment MUST be a scroll-stopping hook.
- Use concrete numbers/examples. Educational, not advice.
- Each segment's "visual_query" is 2-4 words to search stock footage
  (e.g. "stock market chart", "person counting money").
- "on_screen_text" is a short caption (<=6 words) for that segment.
- End with a CTA to subscribe.

Return JSON:
{{
  "title": "SEO title under 70 chars, high CTR",
  "hook": "the opening line",
  "segments": [
    {{"narration": "...", "visual_query": "...", "on_screen_text": "..."}}
  ],
  "cta": "closing call to action line",
  "description": "2-3 sentence YouTube description with keyword",
  "tags": ["tag1", "tag2", "..."]
}}
"""
    script = ask_llm_json(prompt, SYSTEM, max_tokens=3000)
    # Inyectar disclaimer YMYL en la descripción (cumplimiento)
    script["description"] = script.get("description", "") + "\n\n" + settings.DISCLAIMER
    script["disclaimer"] = settings.DISCLAIMER
    log.info("Guion listo: %d segmentos | título: %s",
             len(script.get("segments", [])), script.get("title"))
    return script
