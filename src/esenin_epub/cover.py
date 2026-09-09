"""Simple monochrome typographic cover rendered with Pillow (optional)."""

from __future__ import annotations

from pathlib import Path

FONT_CANDIDATES = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSerif-Regular.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/TTF/DejaVuSerif.ttf",
    "/Library/Fonts/Georgia.ttf",
    "C:/Windows/Fonts/georgia.ttf",
]


def _font_path() -> str | None:
    for p in FONT_CANDIDATES:
        if Path(p).exists():
            return p
    return None


def make_cover_png(author_line: str = "СЕРГЕЙ ЕСЕНИН", title_lines: tuple[str, ...] = ("Любовь,", "исповедь", "и сказки"), size=(1200, 1600)) -> bytes | None:
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError:
        return None
    font_path = _font_path()
    if not font_path:
        return None
    import io

    w, h = size
    img = Image.new("L", size, 245)
    d = ImageDraw.Draw(img)
    margin = int(w * 0.09)
    d.rectangle([margin, margin, w - margin, h - margin], outline=40, width=4)
    d.rectangle([margin + 14, margin + 14, w - margin - 14, h - margin - 14], outline=40, width=1)

    small = ImageFont.truetype(font_path, int(w * 0.055))
    big = ImageFont.truetype(font_path, int(w * 0.12))

    y = int(h * 0.20)
    bbox = d.textbbox((0, 0), author_line, font=small)
    d.text(((w - (bbox[2] - bbox[0])) / 2, y), author_line, fill=30, font=small)
    y += int(h * 0.05)
    d.line([w * 0.3, y + 40, w * 0.7, y + 40], fill=40, width=2)

    y = int(h * 0.40)
    for line in title_lines:
        bbox = d.textbbox((0, 0), line, font=big)
        d.text(((w - (bbox[2] - bbox[0])) / 2, y), line, fill=20, font=big)
        y += int(w * 0.15)

    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return buf.getvalue()
