"""
Configuración central del pipeline.
Todas las claves se leen de variables de entorno — nunca hardcodear.
Copiá .env.example a .env y completá tus valores.
"""
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# --- Rutas ---
ROOT = Path(__file__).resolve().parent.parent
OUTPUT_DIR = ROOT / "output"
ASSETS_DIR = ROOT / "assets"
OUTPUT_DIR.mkdir(exist_ok=True)
ASSETS_DIR.mkdir(exist_ok=True)

# --- LLM (Anthropic) ---
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
LLM_MODEL = os.getenv("LLM_MODEL", "claude-sonnet-4-6")

# --- Nicho / canal ---
NICHE = "personal finance and investing"
LANGUAGE = "en"  # canal en inglés (CPM más alto)
# Combinación elegida: finanzas personales (imán de Shorts) + inversiones (CPM alto)
SUBTOPICS = [
    "personal finance", "saving money", "investing basics",
    "index funds", "stock market", "budgeting", "passive income",
]

# --- TTS local (Kokoro) ---
TTS_ENGINE = os.getenv("TTS_ENGINE", "kokoro")   # kokoro | piper | azure
TTS_VOICE = os.getenv("TTS_VOICE", "af_heart")   # voz Kokoro por defecto
TTS_DEVICE = os.getenv("TTS_DEVICE", "cuda")     # cuda si tenés GPU, cpu si no

# --- Stock visual ---
PEXELS_API_KEY = os.getenv("PEXELS_API_KEY", "")
PIXABAY_API_KEY = os.getenv("PIXABAY_API_KEY", "")

# --- YouTube ---
YT_CLIENT_SECRETS = os.getenv("YT_CLIENT_SECRETS", str(ROOT / "config" / "client_secrets.json"))
YT_TOKEN_FILE = str(ROOT / "config" / "token.json")
# 'private' mientras probás; cambiá a 'public' cuando confíes en la salida
YT_PRIVACY_STATUS = os.getenv("YT_PRIVACY_STATUS", "private")

# --- Notificaciones (opcionales; si faltan, se omiten) ---
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")
DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL", "")

# --- Fuentes de temas en tiempo real ---
USE_REALTIME_TOPICS = os.getenv("USE_REALTIME_TOPICS", "true").lower() == "true"
USE_GOOGLE_TRENDS = os.getenv("USE_GOOGLE_TRENDS", "false").lower() == "true"  # requiere pytrends

# --- Scheduler 24/7 ---
# Cuántos videos por día de cada formato, y cada cuánto revisa el loop.
SCHEDULE = {
    "shorts_per_day": int(os.getenv("SHORTS_PER_DAY", "3")),
    "longs_per_day": int(os.getenv("LONGS_PER_DAY", "1")),
    "loop_check_minutes": int(os.getenv("LOOP_CHECK_MINUTES", "30")),
    "heartbeat_hour_utc": int(os.getenv("HEARTBEAT_HOUR_UTC", "12")),
}

# --- Formatos de video ---
SHORT = {"name": "short", "width": 1080, "height": 1920, "max_seconds": 58}
LONG = {"name": "long", "width": 1920, "height": 1080, "target_minutes": 8}

# --- Cumplimiento / seguridad de contenido ---
# El canal es EDUCATIVO, no asesoramiento financiero. Este disclaimer
# se inyecta en cada guion y descripción para reducir riesgo YMYL.
DISCLAIMER = (
    "This video is for educational and entertainment purposes only and is "
    "not financial advice. Always do your own research or consult a licensed "
    "financial professional before making investment decisions."
)
