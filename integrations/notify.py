"""
Notificaciones a Telegram y/o Discord.

Aunque el pipeline es totalmente autónomo (PASS publica solo), conviene que te
avise qué está pasando: qué publicó, qué bloqueó el QualityGate, y si algo se
rompió. Así podés monitorear desde el celular sin mirar logs.

Ambos canales son gratis y opcionales — si no configurás tokens, se omiten
silenciosamente y el pipeline sigue igual.

Telegram:
  - Creá un bot con @BotFather → obtenés TELEGRAM_BOT_TOKEN
  - Escribile a tu bot, luego abrí
    https://api.telegram.org/bot<TOKEN>/getUpdates para ver tu TELEGRAM_CHAT_ID
Discord:
  - Server Settings → Integrations → Webhooks → New Webhook → copiá la URL
"""
from __future__ import annotations
import json
import urllib.request
import urllib.error

from config import settings
from pipeline.common import get_logger

log = get_logger("Notify")


def _post(url: str, payload: dict) -> bool:
    try:
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            url, data=data, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=15) as r:
            return 200 <= r.status < 300
    except (urllib.error.URLError, urllib.error.HTTPError) as e:
        log.warning("Notificación falló (%s): %s", url.split("/")[2], e)
        return False
    except Exception as e:
        log.warning("Error notificando: %s", e)
        return False


def _telegram(text: str) -> None:
    token = settings.TELEGRAM_BOT_TOKEN
    chat_id = settings.TELEGRAM_CHAT_ID
    if not (token and chat_id):
        return
    _post(f"https://api.telegram.org/bot{token}/sendMessage",
          {"chat_id": chat_id, "text": text, "parse_mode": "HTML",
           "disable_web_page_preview": False})


def _discord(text: str) -> None:
    url = settings.DISCORD_WEBHOOK_URL
    if not url:
        return
    _post(url, {"content": text[:1900]})  # límite de Discord


def send(text: str) -> None:
    """Envía a todos los canales configurados. Nunca lanza excepción."""
    _telegram(text)
    _discord(text)


# ---- Helpers semánticos para eventos del pipeline ----
def published(title: str, url: str, video_format: str, score: int) -> None:
    send(f"✅ <b>Publicado</b> ({video_format}, QG {score})\n{title}\n{url}")


def blocked(title: str, score: int, reasons: list[str]) -> None:
    r = "\n".join(f"• {x}" for x in reasons[:3]) or "—"
    send(f"⛔ <b>Bloqueado por QualityGate</b> (score {score})\n{title}\n{r}")


def review_needed(title: str, url: str, score: int) -> None:
    send(f"👀 <b>Requiere revisión</b> (score {score}) — publicado en PRIVADO\n"
         f"{title}\n{url}")


def error(stage: str, detail: str) -> None:
    send(f"🔥 <b>Error en {stage}</b>\n{detail[:500]}")


def heartbeat(stats: dict) -> None:
    send(f"💓 <b>Pipeline vivo</b>\n"
         f"Hoy: {stats.get('published', 0)} publicados, "
         f"{stats.get('blocked', 0)} bloqueados, "
         f"{stats.get('errors', 0)} errores.")
