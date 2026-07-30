"""
Utilidades compartidas: cliente LLM, logging, y helpers de estado en disco.
Cada agente escribe su salida a output/<run_id>/ para que el pipeline
sea reanudable y debuggeable.
"""
import json
import logging
import re
from datetime import datetime
from pathlib import Path

import anthropic

from config import settings

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(name)-14s | %(levelname)-7s | %(message)s",
    datefmt="%H:%M:%S",
)


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)


# ------------------------------------------------------------------ LLM
_client = None


def llm_client() -> anthropic.Anthropic:
    global _client
    if _client is None:
        if not settings.ANTHROPIC_API_KEY:
            raise RuntimeError(
                "Falta ANTHROPIC_API_KEY. Copiá .env.example a .env y completala."
            )
        _client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)
    return _client


def ask_llm(prompt: str, system: str = "", max_tokens: int = 2000) -> str:
    """Llamada simple al LLM. Devuelve el texto de la respuesta."""
    resp = llm_client().messages.create(
        model=settings.LLM_MODEL,
        max_tokens=max_tokens,
        system=system or "You are a precise assistant.",
        messages=[{"role": "user", "content": prompt}],
    )
    return "".join(b.text for b in resp.content if b.type == "text").strip()


def ask_llm_json(prompt: str, system: str = "", max_tokens: int = 2000) -> dict:
    """Igual que ask_llm pero fuerza y parsea JSON."""
    system = (system + "\nRespond with ONLY valid JSON, no prose, no code fences.").strip()
    raw = ask_llm(prompt, system, max_tokens)
    raw = re.sub(r"^```(json)?|```$", "", raw.strip(), flags=re.MULTILINE).strip()
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        m = re.search(r"\{.*\}", raw, re.DOTALL)
        if m:
            return json.loads(m.group(0))
        raise


# ------------------------------------------------------------------ estado en disco
def new_run_dir() -> Path:
    run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    d = settings.OUTPUT_DIR / run_id
    d.mkdir(parents=True, exist_ok=True)
    return d


def save_json(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))
