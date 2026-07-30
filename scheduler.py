"""
Scheduler 24/7 — corré esto y dejalo prendido en tu máquina.

    python scheduler.py

Qué hace:
  - Reparte los videos del día según config/settings.SCHEDULE
    (p.ej. 3 shorts + 1 long por día), espaciados en el tiempo.
  - Corre en modo TOTALMENTE AUTÓNOMO: cada video pasa por el QualityGate;
    lo que da PASS se publica solo. REVIEW se publica en privado (te avisa).
    BLOCK no se publica (te avisa).
  - Tolerante a fallos: si un video falla, notifica y sigue con el próximo;
    el loop nunca se cae.
  - Manda un "heartbeat" diario para confirmar que sigue vivo.
  - Reanudable: guarda el progreso del día en output/scheduler_state.json,
    así si reiniciás la máquina no re-hace lo ya hecho hoy.

No necesita cron: es un proceso de larga duración. Si preferís cron o systemd,
mirá el README (sección "Operación 24/7").
"""
from __future__ import annotations
import json
import time
import signal
from datetime import datetime, timezone, date

from config import settings
from pipeline.common import get_logger
from integrations import notify
from main import make_one

log = get_logger("Scheduler")
STATE_FILE = settings.OUTPUT_DIR / "scheduler_state.json"

_running = True


def _stop(signum, frame):
    global _running
    log.info("Señal %s recibida — terminando el ciclo actual y saliendo...", signum)
    _running = False


signal.signal(signal.SIGINT, _stop)
signal.signal(signal.SIGTERM, _stop)


def _load_state() -> dict:
    today = date.today().isoformat()
    if STATE_FILE.exists():
        try:
            st = json.loads(STATE_FILE.read_text())
            if st.get("day") == today:
                return st
        except Exception:
            pass
    # nuevo día → cuota fresca
    return {"day": today, "shorts_done": 0, "longs_done": 0,
            "published": 0, "blocked": 0, "errors": 0, "heartbeat_sent": False}


def _save_state(st: dict) -> None:
    STATE_FILE.write_text(json.dumps(st, indent=2))


def _due_format(st: dict) -> str | None:
    """Decide qué formato toca ahora, o None si ya se cumplió la cuota del día."""
    sched = settings.SCHEDULE
    if st["longs_done"] < sched["longs_per_day"]:
        # intercalá: primero asegurá el long temprano, luego shorts
        if st["shorts_done"] >= sched["shorts_per_day"] // 2 or sched["shorts_per_day"] == 0:
            return "long"
    if st["shorts_done"] < sched["shorts_per_day"]:
        return "short"
    if st["longs_done"] < sched["longs_per_day"]:
        return "long"
    return None


def _maybe_heartbeat(st: dict) -> None:
    hb_hour = settings.SCHEDULE["heartbeat_hour_utc"]
    now = datetime.now(timezone.utc)
    if now.hour == hb_hour and not st["heartbeat_sent"]:
        notify.heartbeat(st)
        st["heartbeat_sent"] = True
        _save_state(st)


def run_forever():
    log.info("=== Scheduler 24/7 iniciado (modo autónomo) ===")
    log.info("Cuota diaria: %d shorts + %d longs | chequeo cada %d min",
             settings.SCHEDULE["shorts_per_day"],
             settings.SCHEDULE["longs_per_day"],
             settings.SCHEDULE["loop_check_minutes"])
    notify.send("🚀 <b>Pipeline 24/7 iniciado</b> (modo autónomo)")

    while _running:
        st = _load_state()
        _maybe_heartbeat(st)

        fmt = _due_format(st)
        if fmt is None:
            log.info("Cuota del día cumplida. Esperando al próximo día...")
        else:
            try:
                log.info("Generando un '%s' (progreso hoy: %ds/%dl)...",
                         fmt, st["shorts_done"], st["longs_done"])
                result = make_one(fmt, dry_run=False)

                if result.get("reason") == "quality_gate_block":
                    st["blocked"] += 1
                elif result.get("video_id"):
                    st["published"] += 1
                # cuenta como "intentado" pase lo que pase, para no loopear infinito
                if fmt == "short":
                    st["shorts_done"] += 1
                else:
                    st["longs_done"] += 1
                _save_state(st)

            except Exception as e:
                st["errors"] += 1
                # igual marcamos el intento para no quedar atascados en el mismo video
                if fmt == "short":
                    st["shorts_done"] += 1
                else:
                    st["longs_done"] += 1
                _save_state(st)
                log.exception("Fallo generando '%s'", fmt)
                notify.error(f"generación de {fmt}", str(e))

        # dormir hasta el próximo chequeo (en tramos cortos para responder a Ctrl-C)
        slept = 0
        interval = settings.SCHEDULE["loop_check_minutes"] * 60
        while _running and slept < interval:
            time.sleep(min(10, interval - slept))
            slept += 10

    log.info("=== Scheduler detenido limpiamente ===")
    notify.send("🛑 <b>Pipeline 24/7 detenido</b>")


if __name__ == "__main__":
    run_forever()
