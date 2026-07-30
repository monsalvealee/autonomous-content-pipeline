"""
Agente 3 — VoiceAgent
Genera la locución con TTS local (Kokoro por defecto — gratis, corre en GPU).
Produce un WAV por segmento y devuelve duraciones para sincronizar visuales.

Kokoro-82M: modelo TTS open source, calidad muy alta para su tamaño.
  pip install kokoro soundfile
Alternativas: piper (más liviano), azure (pago, barato).

Salida: dict {audio_files[], durations[], total_seconds}
"""
import wave
from pathlib import Path

from config import settings
from pipeline.common import get_logger

log = get_logger("VoiceAgent")


def _wav_duration(path: Path) -> float:
    with wave.open(str(path), "rb") as w:
        return w.getnframes() / float(w.getframerate())


def _synth_kokoro(segments, out_dir: Path):
    from kokoro import KPipeline
    import soundfile as sf

    pipe = KPipeline(lang_code="a", device=settings.TTS_DEVICE)  # 'a' = American English
    files = []
    for i, seg in enumerate(segments):
        text = seg["narration"]
        audio_chunks = []
        for _, _, audio in pipe(text, voice=settings.TTS_VOICE):
            audio_chunks.append(audio)
        import numpy as np
        audio = np.concatenate(audio_chunks) if audio_chunks else np.zeros(1)
        path = out_dir / f"seg_{i:03d}.wav"
        sf.write(str(path), audio, 24000)
        files.append(path)
    return files


def _synth_piper(segments, out_dir: Path):
    import subprocess
    files = []
    for i, seg in enumerate(segments):
        path = out_dir / f"seg_{i:03d}.wav"
        subprocess.run(
            ["piper", "--model", "en_US-amy-medium", "--output_file", str(path)],
            input=seg["narration"].encode(), check=True,
        )
        files.append(path)
    return files


def synthesize(script: dict, run_dir: Path) -> dict:
    audio_dir = run_dir / "audio"
    audio_dir.mkdir(exist_ok=True)
    segments = script["segments"]

    log.info("Sintetizando %d segmentos con %s...", len(segments), settings.TTS_ENGINE)
    if settings.TTS_ENGINE == "kokoro":
        files = _synth_kokoro(segments, audio_dir)
    elif settings.TTS_ENGINE == "piper":
        files = _synth_piper(segments, audio_dir)
    else:
        raise ValueError(f"TTS_ENGINE no soportado: {settings.TTS_ENGINE}")

    durations = [_wav_duration(f) for f in files]
    total = sum(durations)
    log.info("Audio listo: %.1fs totales", total)
    return {
        "audio_files": [str(f) for f in files],
        "durations": durations,
        "total_seconds": total,
    }
