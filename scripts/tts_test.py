"""Bake-off: render a few poems with ElevenLabs so voices/models can be compared by ear.

Usage: uv run python scripts/tts_test.py [--model eleven_v3] [--voices name=id,...] [slug ...]
Key comes from ELEVENLABS_API_KEY or ./.env.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]

# ElevenLabs stock voices (English-native, multilingual under v3).
DEFAULT_VOICES = {
    "george": "JBFqnCBsd6RMkjVDRZzb",
    "daniel": "onwK4e9ZLuTAKqWW03F9",
}


def load_key() -> str:
    if k := os.environ.get("ELEVENLABS_API_KEY"):
        return k
    for line in (ROOT / ".env").read_text().splitlines():
        if line.startswith("ELEVENLABS_API_KEY="):
            return line.split("=", 1)[1].strip().strip('"')
    sys.exit("ELEVENLABS_API_KEY not set")


def poem_text(slug: str, max_stanzas: int | None = None, line_break: float = 0.0) -> str:
    d = json.loads((ROOT / "cache/normalized" / f"{slug}.json").read_text())
    parts, n = [d["title"].rstrip(".!?…") + "."], 0
    for b in d["blocks"]:
        if b["type"] == "stanza":
            if max_stanzas is not None and n >= max_stanzas:
                break
            sep = f' <break time="{line_break}s" />\n' if line_break else "\n"
            parts.append(sep.join(l["text"] for l in b["lines"]))
            n += 1
        elif b["type"] in ("heading", "paragraph"):
            parts.append(b["text"])
    return "\n\n".join(parts)


def render(client: httpx.Client, key: str, voice_id: str, model: str, text: str, out: Path, speed: float = 1.0) -> None:
    r = client.post(
        f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}",
        params={"output_format": "mp3_44100_128"},
        headers={"xi-api-key": key},
        json={
            "text": text,
            "model_id": model,
            "language_code": "ru",
            "voice_settings": {"stability": 0.5, "similarity_boost": 0.75, "style": 0.0, "use_speaker_boost": True, "speed": speed},
        },
    )
    if r.status_code != 200:
        sys.exit(f"{out.name}: {r.status_code} {r.text[:300]}")
    out.write_bytes(r.content)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="eleven_v3")
    ap.add_argument("--voices", default=",".join(f"{k}={v}" for k, v in DEFAULT_VOICES.items()))
    ap.add_argument("--max-stanzas", type=int, default=None, help="cap long poems (test only)")
    ap.add_argument("--out", default="audio/test")
    ap.add_argument("--speed", type=float, default=1.0, help="0.7..1.2 (v2 only; v3 ignores it)")
    ap.add_argument("--prefix", default="", help="text/audio tag prepended, e.g. '[slowly]'")
    ap.add_argument("--line-break", type=float, default=0.0, help="insert <break> of N s after each line")
    ap.add_argument("--tag", default="", help="extra suffix for output filename")
    ap.add_argument("slugs", nargs="*", default=["shagane-ty-moya-shagane", "pismo-materi", "sirotka"])
    a = ap.parse_args()
    key = load_key()
    voices = dict(v.split("=", 1) for v in a.voices.split(","))
    outdir = ROOT / a.out
    outdir.mkdir(parents=True, exist_ok=True)
    total = 0
    with httpx.Client(timeout=300) as c:
        for slug in a.slugs:
            text = poem_text(slug, a.max_stanzas, a.line_break)
            if a.prefix:
                text = a.prefix + " " + text
            total += len(text) * len(voices)
            for name, vid in voices.items():
                tag = (f"__s{a.speed}" if a.speed != 1.0 else "") + (f"__{a.tag}" if a.tag else "")
                out = outdir / f"{slug}__{a.model}__{name}{tag}.mp3"
                render(c, key, vid, a.model, text, out, a.speed)
                print(f"{out.relative_to(ROOT)}  {len(text)} chars  {out.stat().st_size // 1024} KB")
    print(f"total credits ~{total}")


if __name__ == "__main__":
    main()
