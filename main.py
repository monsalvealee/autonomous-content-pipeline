"""
Orquestador del pipeline de videos de finanzas.

Uso:
    python main.py --format short          # genera y publica un Short
    python main.py --format long           # genera y publica un video largo
    python main.py --format short --dry-run  # genera pero NO publica
    python main.py --batch                 # 1 short + 1 long

Cada corrida crea output/<timestamp>/ con todos los artefactos intermedios,
así podés inspeccionar o reanudar.
"""
import argparse

from pipeline.common import get_logger, new_run_dir, save_json
from agents import (
    trend_agent, script_agent, voice_agent,
    visual_agent, thumb_agent, quality_gate_agent,
    publish_agent, feedback_agent,
)
from integrations import notify

log = get_logger("Orchestrator")


def make_one(video_format: str, dry_run: bool = False) -> dict:
    run_dir = new_run_dir()
    log.info("=== Nueva corrida (%s) en %s ===", video_format, run_dir.name)
    is_short = video_format == "short"

    # 1. Tema
    winners = feedback_agent.recent_winners()
    topic = trend_agent.pick_topic(video_format, winners)
    save_json(run_dir / "1_topic.json", topic)

    # 2. Guion
    script = script_agent.write_script(topic)
    script["_format"] = video_format  # lo necesita el VisualAgent
    save_json(run_dir / "2_script.json", script)

    # 3. Voz
    voice = voice_agent.synthesize(script, run_dir)
    save_json(run_dir / "3_voice.json", voice)

    # 4. Video
    video_path = visual_agent.build_video(script, voice, run_dir)

    # 5. Thumbnail + metadata
    metadata = thumb_agent.build_metadata(script, is_short, run_dir)
    save_json(run_dir / "5_metadata.json", metadata)

    # 5.5 Quality Gate — control anti-desmonetización ANTES de publicar
    gate = quality_gate_agent.review(script, run_dir)
    save_json(run_dir / "5b_quality_gate.json", gate)
    if gate["verdict"] == "BLOCK":
        log.warning("BLOQUEADO por QualityGate (score %d). No se publica.", gate["score"])
        for r in gate["reasons"]:
            log.warning("  - %s", r)
        notify.blocked(script.get("title", "?"), gate["score"], gate["reasons"])
        result = {"skipped": True, "reason": "quality_gate_block", "gate": gate}
        feedback_agent.record(topic, result)
        save_json(run_dir / "6_result.json", result)
        log.info("=== Corrida detenida por control de calidad ===")
        return result
    if gate["verdict"] == "REVIEW":
        log.warning("QualityGate: REVIEW (score %d). Se publicará en 'private' "
                    "para revisión humana.", gate["score"])

    # 6. Publicación
    if dry_run:
        log.info("Dry-run: video listo en %s, NO se publica.", video_path)
        result = {"skipped": True, "reason": "dry_run", "video_path": video_path}
    else:
        force_private = gate["verdict"] == "REVIEW"
        result = publish_agent.publish(video_path, metadata, is_short,
                                       force_private=force_private)
        url = result.get("url", "")
        if result.get("video_id"):
            if gate["verdict"] == "REVIEW":
                notify.review_needed(script.get("title", "?"), url, gate["score"])
            else:
                notify.published(script.get("title", "?"), url,
                                 video_format, gate["score"])

    result["gate_score"] = gate["score"]
    result["gate_verdict"] = gate["verdict"]

    # 7. Feedback
    feedback_agent.record(topic, result)
    save_json(run_dir / "6_result.json", result)

    log.info("=== Corrida completa ===")
    return result


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--format", choices=["short", "long"], default="short")
    ap.add_argument("--dry-run", action="store_true", help="genera sin publicar")
    ap.add_argument("--batch", action="store_true", help="1 short + 1 long")
    args = ap.parse_args()

    if args.batch:
        make_one("short", args.dry_run)
        make_one("long", args.dry_run)
    else:
        make_one(args.format, args.dry_run)


if __name__ == "__main__":
    main()
