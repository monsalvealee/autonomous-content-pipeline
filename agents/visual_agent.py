"""
Agente 4 — VisualAgent
Arma el video final: descarga b-roll de stock (Pexels/Pixabay, gratis),
lo recorta al formato correcto, superpone subtítulos y concatena con el audio.

Usa moviepy + ffmpeg. Sin costo de API.

Salida: ruta al video.mp4
"""
import io
import random
from pathlib import Path

import requests

from config import settings
from pipeline.common import get_logger

log = get_logger("VisualAgent")

PEXELS_VIDEO_URL = "https://api.pexels.com/videos/search"


def _fetch_stock_clip(query: str, dest: Path, vertical: bool) -> Path | None:
    """Descarga un clip de stock de Pexels. Devuelve la ruta o None."""
    if not settings.PEXELS_API_KEY:
        return None
    try:
        r = requests.get(
            PEXELS_VIDEO_URL,
            headers={"Authorization": settings.PEXELS_API_KEY},
            params={"query": query, "per_page": 5,
                    "orientation": "portrait" if vertical else "landscape"},
            timeout=20,
        )
        r.raise_for_status()
        videos = r.json().get("videos", [])
        if not videos:
            return None
        video = random.choice(videos)
        # elegir un archivo de resolución media (más liviano)
        files = sorted(video["video_files"], key=lambda f: f.get("width", 0))
        chosen = files[len(files) // 2]
        clip_data = requests.get(chosen["link"], timeout=60).content
        dest.write_bytes(clip_data)
        return dest
    except Exception as e:
        log.warning("Fallo al bajar stock '%s': %s", query, e)
        return None


def build_video(script: dict, voice: dict, run_dir: Path) -> str:
    from moviepy.editor import (
        AudioFileClip, VideoFileClip, ColorClip, CompositeVideoClip,
        TextClip, concatenate_videoclips,
    )

    # el formato real se pasa por el script en el orquestador (_format)
    fmt = settings.SHORT if script.get("_format") == "short" else settings.LONG
    W, H = fmt["width"], fmt["height"]
    vertical = fmt["name"] == "short"

    clips_dir = run_dir / "clips"
    clips_dir.mkdir(exist_ok=True)
    segment_clips = []

    for i, seg in enumerate(script["segments"]):
        dur = voice["durations"][i]
        audio = AudioFileClip(voice["audio_files"][i])

        # fondo: stock o color sólido de respaldo
        raw = _fetch_stock_clip(seg["visual_query"], clips_dir / f"bg_{i:03d}.mp4", vertical)
        if raw and raw.exists():
            try:
                bg = VideoFileClip(str(raw)).without_audio()
                bg = bg.resize(height=H) if bg.h < H else bg.resize(width=W)
                bg = bg.crop(x_center=bg.w / 2, y_center=bg.h / 2, width=W, height=H)
                bg = bg.loop(duration=dur) if bg.duration < dur else bg.subclip(0, dur)
            except Exception as e:
                log.warning("Clip inválido, uso fondo sólido: %s", e)
                bg = ColorClip((W, H), color=(18, 22, 30), duration=dur)
        else:
            bg = ColorClip((W, H), color=(18, 22, 30), duration=dur)

        # subtítulo en pantalla
        caption = seg.get("on_screen_text", "")
        layers = [bg.set_duration(dur)]
        if caption:
            try:
                txt = (TextClip(caption, fontsize=int(H * 0.05), color="white",
                                font="DejaVu-Sans-Bold", stroke_color="black",
                                stroke_width=2, method="caption", size=(int(W * 0.9), None))
                       .set_duration(dur)
                       .set_position(("center", "center" if vertical else 0.8), relative=True))
                layers.append(txt)
            except Exception as e:
                log.warning("No pude renderizar subtítulo: %s", e)

        seg_clip = CompositeVideoClip(layers, size=(W, H)).set_audio(audio)
        segment_clips.append(seg_clip)

    final = concatenate_videoclips(segment_clips, method="compose")
    out_path = run_dir / "video.mp4"
    final.write_videofile(
        str(out_path), fps=30, codec="libx264", audio_codec="aac",
        threads=4, preset="medium", logger=None,
    )
    log.info("Video renderizado: %s (%.1fs)", out_path.name, final.duration)
    return str(out_path)
