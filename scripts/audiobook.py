"""Render the curated book as one M4B audiobook via ElevenLabs.

  uv run python scripts/audiobook.py render --voice-id ID [--model eleven_v3] [--only slug ...] [--dry-run]
  uv run python scripts/audiobook.py merge  [--tempo 0.9] [--output dist/esenin.m4b]

`render` writes audio/book/NN-slug.mp3 in manifest order and skips files that exist
(safe to rerun). `merge` pads each poem with silence, optionally slows it
(pitch-preserving atempo), and concatenates into an M4B with one chapter per poem.
Key from ELEVENLABS_API_KEY or ./.env. Uses dist/manifest.json for order, so run
`esenin-epub build` first.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

import httpx
import imageio_ffmpeg

sys.path.insert(0, str(Path(__file__).resolve().parent))
from tts_test import load_key  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()
BOOK = ROOT / "audio/book"
CHUNK_CHARS = 3800  # v3 hard limit is 5000 per request


def works() -> list[dict]:
    return json.loads((ROOT / "dist/manifest.json").read_text())["works"]


def book_meta() -> dict:
    return json.loads((ROOT / "dist/manifest.json").read_text())["book"]


def chunks_for(slug: str) -> list[str]:
    """Poem text split on stanza boundaries into <= CHUNK_CHARS pieces; title leads the first."""
    d = json.loads((ROOT / "cache/normalized" / f"{slug}.json").read_text())
    pieces = [d["title"].rstrip(".!?…") + "."]
    for b in d["blocks"]:
        if b["type"] == "stanza":
            pieces.append("\n".join(l["text"] for l in b["lines"]))
        elif b["type"] in ("heading", "paragraph"):
            pieces.append(b["text"])
    out, cur = [], ""
    for p in pieces:
        if cur and len(cur) + len(p) + 2 > CHUNK_CHARS:
            out.append(cur)
            cur = p
        else:
            cur = f"{cur}\n\n{p}" if cur else p
    if cur:
        out.append(cur)
    return out


def tts(client: httpx.Client, key: str, voice_id: str, model: str, text: str, prev: str, nxt: str, speed: float) -> bytes:
    body = {
        "text": text,
        "model_id": model,
        "language_code": "ru",
        "voice_settings": {"stability": 0.5, "similarity_boost": 0.75, "style": 0.0, "use_speaker_boost": True, "speed": speed},
    }
    if not model.startswith("eleven_v3"):  # v3 rejects these; v2 uses them for chunk continuity
        if prev:
            body["previous_text"] = prev[-600:]
        if nxt:
            body["next_text"] = nxt[:600]
    for attempt in range(4):
        r = client.post(
            f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}",
            params={"output_format": "mp3_44100_128"},
            headers={"xi-api-key": key},
            json=body,
        )
        if r.status_code == 200:
            return r.content
        if r.status_code in (429, 500, 502, 503) and attempt < 3:
            import time

            time.sleep(5 * (attempt + 1))
            continue
        sys.exit(f"TTS failed {r.status_code}: {r.text[:300]}")
    raise AssertionError


def concat_mp3(parts: list[Path], out: Path) -> None:
    lst = out.with_suffix(".txt")
    lst.write_text("".join(f"file '{p.resolve()}'\n" for p in parts))
    subprocess.run([FFMPEG, "-loglevel", "error", "-y", "-f", "concat", "-safe", "0", "-i", str(lst), "-c", "copy", str(out)], check=True)
    lst.unlink()


def cmd_render(a: argparse.Namespace) -> None:
    key = load_key()
    BOOK.mkdir(parents=True, exist_ok=True)
    (BOOK / "parts").mkdir(exist_ok=True)
    todo = [w for w in works() if not a.only or w["slug"] in a.only]
    credits = 0
    with httpx.Client(timeout=600) as c:
        for w in todo:
            out = BOOK / f"{w['order']:02d}-{w['slug']}.mp3"
            ch = chunks_for(w["slug"])
            n = sum(len(x) for x in ch)
            if out.exists():
                print(f"skip  {out.name}")
                continue
            credits += n
            print(f"{'plan' if a.dry_run else 'render'}  {out.name}  {n} chars in {len(ch)} chunk(s)", flush=True)
            if a.dry_run:
                continue
            parts = []
            for i, text in enumerate(ch):
                p = BOOK / "parts" / f"{w['order']:02d}-{w['slug']}.p{i}.mp3"
                if not p.exists():
                    prev = ch[i - 1] if i else ""
                    nxt = ch[i + 1] if i + 1 < len(ch) else ""
                    p.write_bytes(tts(c, key, a.voice_id, a.model, text, prev, nxt, a.speed))
                parts.append(p)
            if len(parts) == 1:
                parts[0].rename(out)
            else:
                concat_mp3(parts, out)
    print(f"credits {'needed' if a.dry_run else 'used'} ~{credits}")


def duration(path: Path) -> float:
    r = subprocess.run([FFMPEG, "-i", str(path), "-f", "null", "-"], capture_output=True, text=True)
    m = re.findall(r"time=(\d+):(\d+):([\d.]+)", r.stderr)
    h, mi, s = m[-1]
    return int(h) * 3600 + int(mi) * 60 + float(s)


def cmd_merge(a: argparse.Namespace) -> None:
    ws = [w for w in works() if not a.only or w["slug"] in a.only]
    meta = book_meta()
    stage = BOOK / "m4a"
    stage.mkdir(parents=True, exist_ok=True)
    ffmeta = [";FFMETADATA1", f"title={meta['title']}", f"artist={meta['author']}", f"album={meta['title']}", "genre=Audiobook", "language=rus"]
    concat_list, t = [], 0.0
    for w in ws:
        src = BOOK / f"{w['order']:02d}-{w['slug']}.mp3"
        if not src.exists():
            sys.exit(f"missing {src.name}; run render first")
        dst = stage / f"{src.stem}.m4a"
        af = f"apad=pad_dur={a.gap}" + (f",atempo={a.tempo}" if a.tempo != 1.0 else "")
        if not dst.exists() or dst.stat().st_mtime < src.stat().st_mtime:
            subprocess.run([FFMPEG, "-loglevel", "error", "-y", "-i", str(src), "-af", af, "-c:a", "aac", "-b:a", "96k", "-ac", "1", str(dst)], check=True)
        d = duration(dst)
        ffmeta += ["[CHAPTER]", "TIMEBASE=1/1000", f"START={int(t * 1000)}", f"END={int((t + d) * 1000)}", f"title={w['section']} — {w['title']}"]
        concat_list.append(dst)
        t += d
        print(f"{w['order']:02d} {d:7.1f}s  {w['title']}")
    lst = stage / "concat.txt"
    lst.write_text("".join(f"file '{p.resolve()}'\n" for p in concat_list))
    metaf = stage / "ffmeta.txt"
    metaf.write_text("\n".join(ffmeta) + "\n")
    cover = stage / "cover.png"
    if not cover.exists():
        from esenin_epub.cover import make_cover_png

        png = make_cover_png()
        if png:
            cover.write_bytes(png)
    out = ROOT / a.output
    out.parent.mkdir(parents=True, exist_ok=True)
    cmd = [FFMPEG, "-loglevel", "error", "-y", "-f", "concat", "-safe", "0", "-i", str(lst), "-i", str(metaf)]
    if cover.exists():
        cmd += ["-i", str(cover), "-map", "0:a", "-map", "2:v", "-c:v", "png", "-disposition:v", "attached_pic"]
    else:
        cmd += ["-map", "0:a"]
    cmd += ["-map_metadata", "1", "-map_chapters", "1", "-c:a", "copy", "-movflags", "+faststart", "-f", "mp4", str(out)]
    subprocess.run(cmd, check=True)
    print(f"wrote {out.relative_to(ROOT)}  {t / 60:.1f} min  {out.stat().st_size // 1024 // 1024} MB")


def main() -> None:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("render")
    r.add_argument("--voice-id", required=True)
    r.add_argument("--model", default="eleven_v3")
    r.add_argument("--speed", type=float, default=1.0, help="v2 only; v3 ignores it")
    r.add_argument("--only", nargs="*", default=[])
    r.add_argument("--dry-run", action="store_true")
    r.set_defaults(fn=cmd_render)
    m = sub.add_parser("merge")
    m.add_argument("--tempo", type=float, default=1.0, help="atempo factor, e.g. 0.9 to slow down")
    m.add_argument("--gap", type=float, default=1.5, help="seconds of silence after each poem")
    m.add_argument("--output", default="dist/esenin-love-and-tales.m4b")
    m.add_argument("--only", nargs="*", default=[], help="subset, for testing")
    m.set_defaults(fn=cmd_merge)
    a = ap.parse_args()
    a.fn(a)


if __name__ == "__main__":
    main()
