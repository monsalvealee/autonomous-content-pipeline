"""
Agente 7 — FeedbackAgent
Lee el rendimiento de videos ya publicados y devuelve los temas ganadores
para que el TrendAgent sesgue las próximas elecciones.

Mantiene un historial simple en output/history.json.
La lectura de analytics vía YouTube Analytics API es opcional; sin credenciales,
funciona igual usando solo el historial local de lo que se publicó.

Salida: list[str] de temas que rindieron.
"""
import json
from pathlib import Path

from config import settings
from pipeline.common import get_logger

log = get_logger("FeedbackAgent")

HISTORY = settings.OUTPUT_DIR / "history.json"


def record(topic: dict, publish_result: dict) -> None:
    hist = []
    if HISTORY.exists():
        hist = json.loads(HISTORY.read_text())
    hist.append({
        "topic": topic["topic"],
        "keyword": topic.get("target_keyword"),
        "format": topic["format"],
        "video_id": publish_result.get("video_id"),
        "url": publish_result.get("url"),
        "views": None,  # se completa al leer analytics
    })
    HISTORY.write_text(json.dumps(hist, indent=2, ensure_ascii=False))


def recent_winners(top_n: int = 5) -> list[str]:
    """
    Devuelve los temas con más vistas si hay datos de analytics;
    si no, los más recientes como proxy.
    """
    if not HISTORY.exists():
        return []
    hist = json.loads(HISTORY.read_text())
    with_views = [h for h in hist if h.get("views") is not None]
    if with_views:
        top = sorted(with_views, key=lambda h: h["views"], reverse=True)[:top_n]
    else:
        top = hist[-top_n:]
    return [h["topic"] for h in top]


def refresh_analytics() -> None:
    """
    Opcional: completa 'views' consultando la YouTube Analytics API.
    Requiere scope adicional. Dejado como stub para no romper el flujo mínimo.
    """
    log.info("refresh_analytics: stub — implementar con youtubeAnalytics.v2 si se desea.")
