"""Make a YouTube-ready MP4 (cover over the audiobook audio) plus a description with chapter timestamps.

  uv run python scripts/youtube_video.py  ->  dist/youtube/esenin.mp4, dist/youtube/description.txt
Reads the per-poem m4a files staged by `audiobook.py merge`, so run that first.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from audiobook import BOOK, FFMPEG, ROOT, duration, works  # noqa: E402

OUT = ROOT / "dist/youtube"


def hms(t: float) -> str:
    t = int(t)
    return f"{t // 3600}:{t % 3600 // 60:02d}:{t % 60:02d}" if t >= 3600 else f"{t // 60}:{t % 60:02d}"


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    stage = BOOK / "m4a"
    lines, t, section = [], 0.0, None
    for w in works():
        if w["section"] != section:
            section = w["section"]
            lines.append(f"\n— {section} —")
        lines.append(f"{hms(t)} {w['title']}")
        t += duration(stage / f"{w['order']:02d}-{w['slug']}.m4a")
    lines[1] = lines[1].replace(hms(0), "0:00")  # YouTube needs the first chapter at 0:00
    desc = (
        "Аудиокнига: 77 стихотворений и стихотворных сказок Сергея Есенина — «Любовь хулигана», «Персидские мотивы», "
        "исповедальная и кабацкая лирика, «Анна Снегина», «Чёрный человек», сказки «Сиротка» и «Сказка о пастушонке Пете».\n\n"
        "⚠️ Озвучено нейросетью (ElevenLabs Eleven v3, голос George), не живым чтецом. Тексты — Русская Викитека, "
        "общественное достояние.\n\n"
        "Скачать в формате M4B (одна глава на стихотворение) и посмотреть, как это сделано:\n"
        "https://github.com/afiodorov/esenin/releases/tag/audiobook-v1\n\n"
        "Содержание:" + "\n".join(lines) + "\n"
    )
    (OUT / "description.txt").write_text(desc)
    (OUT / "title.txt").write_text("Сергей Есенин — Любовь, исповедь и сказки. Аудиокнига, 77 стихотворений (нейросетевая озвучка)\n")
    cover = stage / "cover.png"
    m4b = ROOT / "dist/esenin-love-and-tales.m4b"
    subprocess.run(
        [FFMPEG, "-loglevel", "error", "-y", "-loop", "1", "-framerate", "1", "-i", str(cover), "-i", str(m4b),
         "-map", "0:v", "-map", "1:a",
         "-vf", "scale=-2:1080,pad=1920:1080:(ow-iw)/2:0:color=#111111,format=yuv420p",
         "-c:v", "libx264", "-preset", "veryfast", "-tune", "stillimage", "-r", "1", "-g", "30",
         "-c:a", "aac", "-b:a", "128k", "-ac", "2", "-shortest", "-movflags", "+faststart", str(OUT / "esenin.mp4")],
        check=True,
    )
    print(f"wrote {OUT.relative_to(ROOT)}/esenin.mp4 {(OUT / 'esenin.mp4').stat().st_size >> 20} MB, {len(lines)} description lines")


if __name__ == "__main__":
    main()
