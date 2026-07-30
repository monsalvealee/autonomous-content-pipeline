"""
Agente 5 — ThumbAgent
Genera el thumbnail (para videos largos) y consolida la metadata de publicación.
El thumbnail se compone con PIL sobre un fondo de stock o color, texto grande.
Los Shorts no necesitan thumbnail (usan un frame del video).

Salida: dict {thumbnail_path | None, title, description, tags}
"""
from pathlib import Path

from config import settings
from pipeline.common import ask_llm, get_logger

log = get_logger("ThumbAgent")


def _thumbnail_text(title: str) -> str:
    """Pide al LLM 2-4 palabras de altísimo impacto para el thumbnail."""
    txt = ask_llm(
        f'Video title: "{title}". Give ONLY a 2-4 word punchy thumbnail phrase '
        f'in uppercase. No quotes, no explanation.',
        system="You write high-CTR YouTube thumbnail text.",
        max_tokens=30,
    )
    return txt.strip().strip('"').upper()[:30]


def build_thumbnail(script: dict, is_short: bool, run_dir: Path) -> str | None:
    if is_short:
        return None  # los Shorts no usan thumbnail custom

    from PIL import Image, ImageDraw, ImageFont

    W, H = 1280, 720
    img = Image.new("RGB", (W, H), (14, 18, 28))
    draw = ImageDraw.Draw(img)

    # barra de acento
    draw.rectangle([0, 0, 18, H], fill=(46, 196, 132))

    phrase = _thumbnail_text(script["title"])
    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 96)
    except Exception:
        font = ImageFont.load_default()

    # wrap simple
    words = phrase.split()
    lines, cur = [], ""
    for w in words:
        test = (cur + " " + w).strip()
        if draw.textlength(test, font=font) < W * 0.85:
            cur = test
        else:
            lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)

    y = H // 2 - (len(lines) * 110) // 2
    for line in lines:
        tw = draw.textlength(line, font=font)
        x = (W - tw) // 2
        # sombra
        draw.text((x + 4, y + 4), line, font=font, fill=(0, 0, 0))
        draw.text((x, y), line, font=font, fill=(255, 255, 255))
        y += 110

    path = run_dir / "thumbnail.png"
    img.save(path)
    log.info("Thumbnail generado: %s", path.name)
    return str(path)


def build_metadata(script: dict, is_short: bool, run_dir: Path) -> dict:
    thumb = build_thumbnail(script, is_short, run_dir)
    tags = script.get("tags", [])
    if is_short:
        tags = list(dict.fromkeys(tags + ["shorts", "finance", "money"]))
    return {
        "thumbnail_path": thumb,
        "title": script["title"],
        "description": script["description"],
        "tags": tags[:15],
    }
