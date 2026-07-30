"""
Agente 8 — QualityGateAgent
Control de calidad que corre ANTES de publicar. Su objetivo es reducir el riesgo
de desmonetización por contenido "no auténtico / made for AI / repetitivo",
que es la causa nº1 por la que YouTube penaliza canales automatizados.

IMPORTANTE — expectativas honestas:
  - Esto NO garantiza monetización ni que YouTube no te desmonetice. Las políticas
    de YouTube son opacas y cambian; la decisión final es de ellos.
  - Lo que sí hace: imponer un estándar de calidad y diferenciación verificable,
    y BLOQUEAR la publicación cuando el contenido no lo cumple.
  - No intenta "engañar" al sistema. Al contrario: fuerza que el contenido
    legítimamente aporte valor, que es lo único que funciona a largo plazo.

Hace 4 controles:
  1. Repetición: ¿este video se parece demasiado a los anteriores? (similitud de
     guion y estructura contra el historial).
  2. Valor propio: ¿tiene un ángulo/insight verificable, o es genérico y relleno?
     (juez LLM con rúbrica estricta).
  3. Exactitud financiera (YMYL): ¿hay afirmaciones financieras falsas, engañosas
     o que suenen a consejo de compra/venta? (juez LLM).
  4. Cumplimiento formal: disclaimer presente, sin promesas de retorno garantizado,
     sin clickbait que el video no cumple.

Salida: dict {verdict: PASS|REVIEW|BLOCK, score, checks{...}, reasons[], suggestions[]}
Si el verdict es BLOCK, el orquestador NO publica.
"""
import json
import re
from difflib import SequenceMatcher
from pathlib import Path

from config import settings
from pipeline.common import ask_llm_json, get_logger

log = get_logger("QualityGate")

HISTORY = settings.OUTPUT_DIR / "history.json"

# Umbrales (ajustables). Empezá estricto; relajá con datos reales.
SIMILARITY_BLOCK = 0.80   # si un guion se parece >=80% a otro previo → BLOCK
SIMILARITY_WARN = 0.65    # >=65% → cuenta como riesgo, baja el score
SCORE_PASS = 75           # >=75 publica
SCORE_REVIEW = 55         # 55-74 queda para revisión humana; <55 se bloquea

# Frases que son señal de riesgo YMYL / promesas indebidas.
RED_FLAG_PHRASES = [
    "guaranteed return", "guaranteed profit", "can't lose", "risk-free",
    "get rich quick", "100% safe", "double your money", "sure thing",
    "will definitely", "financial freedom in", "secret the banks",
]


# ---------------------------------------------------------------- 1. Repetición
def _script_fingerprint(script: dict) -> str:
    """Texto normalizado del guion para comparar similitud."""
    parts = [script.get("title", "")]
    for seg in script.get("segments", []):
        parts.append(seg.get("narration", ""))
    text = " ".join(parts).lower()
    return re.sub(r"[^a-z0-9 ]+", "", text)


def _repetition_check(script: dict) -> dict:
    """Compara el guion actual contra los guiones históricos guardados."""
    current = _script_fingerprint(script)
    max_sim = 0.0
    closest = None

    # buscar guiones previos en output/*/2_script.json
    for script_file in sorted(settings.OUTPUT_DIR.glob("*/2_script.json")):
        try:
            prev = json.loads(script_file.read_text(encoding="utf-8"))
        except Exception:
            continue
        prev_fp = _script_fingerprint(prev)
        if not prev_fp:
            continue
        sim = SequenceMatcher(None, current, prev_fp).ratio()
        if sim > max_sim:
            max_sim, closest = sim, prev.get("title", script_file.parent.name)

    if max_sim >= SIMILARITY_BLOCK:
        return {"ok": False, "block": True, "similarity": round(max_sim, 3),
                "closest": closest,
                "reason": f"Guion casi idéntico a uno previo ('{closest}', {max_sim:.0%})."}
    if max_sim >= SIMILARITY_WARN:
        return {"ok": False, "block": False, "similarity": round(max_sim, 3),
                "closest": closest,
                "reason": f"Guion parecido a '{closest}' ({max_sim:.0%}). Diferenciá más el ángulo."}
    return {"ok": True, "block": False, "similarity": round(max_sim, 3), "closest": closest}


# ------------------------------------------------- 2+3. Juez LLM (valor + YMYL)
JUDGE_SYSTEM = (
    "You are a strict YouTube Partner Program compliance reviewer for a finance "
    "channel. You protect the channel from demonetization for 'inauthentic / mass-"
    "produced / repetitious' content and from YMYL (financial) policy issues. You "
    "are skeptical and hard to please. You NEVER reward generic filler. You do not "
    "help anyone deceive YouTube — you only assess whether content genuinely earns "
    "its place by being original, accurate, and valuable."
)


def _llm_judge(script: dict) -> dict:
    narration = " ".join(s.get("narration", "") for s in script.get("segments", []))
    prompt = f"""
Assess this finance video script for YouTube monetization safety. Be strict.

TITLE: {script.get('title')}
NARRATION: {narration}

Score each 0-10:
- originality: does it have a specific, non-generic angle or insight? (10 = genuinely fresh; 0 = generic filler anyone could auto-generate)
- value: would a viewer learn something concrete/useful? (numbers, examples, a real takeaway)
- accuracy: are the financial claims correct and non-misleading? (10 = solid; 0 = false or reckless)
- advice_safety: does it stay EDUCATIONAL and avoid specific buy/sell calls or guaranteed-return promises?
- clickbait_integrity: does the video actually deliver what the title promises?

Also flag any concrete problems.

Return JSON only:
{{
  "originality": <int>, "value": <int>, "accuracy": <int>,
  "advice_safety": <int>, "clickbait_integrity": <int>,
  "problems": ["specific issue", "..."],
  "fixes": ["concrete suggestion", "..."]
}}
"""
    return ask_llm_json(prompt, JUDGE_SYSTEM, max_tokens=1000)


# ---------------------------------------------------------------- 4. Formal
def _formal_check(script: dict) -> dict:
    reasons = []
    text = (script.get("title", "") + " " +
            " ".join(s.get("narration", "") for s in script.get("segments", [])) + " " +
            script.get("description", "")).lower()

    hits = [p for p in RED_FLAG_PHRASES if p in text]
    if hits:
        reasons.append(f"Frases de riesgo YMYL detectadas: {', '.join(hits)}.")

    if settings.DISCLAIMER.split(".")[0].lower() not in script.get("description", "").lower():
        reasons.append("Falta el disclaimer educativo en la descripción.")

    return {"ok": not reasons, "reasons": reasons, "red_flags": hits}


# ---------------------------------------------------------------- Orquestación
def review(script: dict, run_dir: Path) -> dict:
    log.info("Revisando calidad y riesgo de desmonetización...")

    rep = _repetition_check(script)
    formal = _formal_check(script)
    try:
        judge = _llm_judge(script)
    except Exception as e:
        log.warning("Juez LLM falló (%s); marco para revisión humana.", e)
        judge = {"originality": 5, "value": 5, "accuracy": 5,
                 "advice_safety": 5, "clickbait_integrity": 5,
                 "problems": ["No se pudo evaluar con LLM."], "fixes": []}

    # score compuesto 0-100
    llm_avg = (judge["originality"] + judge["value"] + judge["accuracy"] +
               judge["advice_safety"] + judge["clickbait_integrity"]) / 5.0
    score = llm_avg * 10
    if rep["similarity"] >= SIMILARITY_WARN:
        score -= 20
    if not formal["ok"]:
        score -= 25
    score = max(0, min(100, round(score)))

    reasons, suggestions = [], list(judge.get("fixes", []))
    if rep.get("reason"):
        reasons.append(rep["reason"])
    reasons += formal.get("reasons", [])
    reasons += judge.get("problems", [])

    # veredicto — cualquier bloqueo duro fuerza BLOCK
    hard_block = rep.get("block") or bool(formal.get("red_flags")) \
        or judge["accuracy"] <= 3 or judge["advice_safety"] <= 3
    if hard_block or score < SCORE_REVIEW:
        verdict = "BLOCK"
    elif score < SCORE_PASS:
        verdict = "REVIEW"
    else:
        verdict = "PASS"

    result = {
        "verdict": verdict,
        "score": score,
        "checks": {"repetition": rep, "llm_judge": judge, "formal": formal},
        "reasons": reasons,
        "suggestions": suggestions,
    }
    log.info("Veredicto: %s (score %d) — %s",
             verdict, score, "; ".join(reasons[:2]) if reasons else "sin observaciones")
    return result
