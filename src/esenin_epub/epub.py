"""Minimal, transparent EPUB3 writer: one XHTML per work, nested nav, linked CSS."""

from __future__ import annotations

import re
import zipfile
from dataclasses import dataclass
from datetime import datetime, timezone
from html import escape
from pathlib import Path

from esenin_epub.models import BookSpec, Heading, Paragraph, Separator, Stanza, Work
from esenin_epub.slug import slugify

CSS = """\
body {
  margin: 0;
  padding: 0;
}

section.poem, section.part, section.front {
  margin: 0;
}

h1 {
  margin: 0 0 1.5em 0;
  text-align: left;
  font-size: 1.35em;
  font-weight: normal;
}

p.subtitle {
  margin: -0.8em 0 1.5em 0;
  font-style: italic;
}

h2.part-number {
  margin: 3em 0 0.5em 0;
  font-size: 1em;
  font-weight: normal;
  text-align: center;
}

h1.part-title {
  text-align: center;
  font-size: 1.6em;
  margin: 0 0 2em 0;
}

h2.section {
  margin: 1.5em 0 1em 0;
  text-align: center;
  font-size: 1.1em;
  font-weight: normal;
}

div.stanza {
  margin: 0 0 1em 0;
}

p.line {
  margin: 0;
  padding-left: 1.2em;
  text-indent: -1.2em;
  text-align: left;
}

p.line.indent1 { padding-left: 2.4em; }
p.line.indent2 { padding-left: 3.6em; }
p.line.indent3 { padding-left: 4.8em; }

div.separator {
  margin: 1.25em 0;
  text-align: center;
}

p.date {
  margin: 1.5em 0 0 0;
  text-align: right;
  font-style: italic;
}

p.prose {
  margin: 0 0 1.5em 0;
  text-align: left;
  font-style: italic;
}

section.front h1.book-title {
  text-align: center;
  font-size: 1.7em;
  margin: 3em 0 0.5em 0;
}

section.front p.book-author {
  text-align: center;
  font-size: 1.2em;
  margin: 0 0 3em 0;
}

nav ol {
  list-style: none;
  padding-left: 0;
  margin: 0;
}

nav ol ol {
  padding-left: 1.2em;
  margin: 0.3em 0 1em 0;
}

nav li {
  margin: 0.25em 0;
}

nav > ol > li > a {
  font-weight: bold;
}

section.colophon p {
  margin: 0 0 0.6em 0;
  text-align: left;
}
"""

XHTML_HEAD = """<?xml version="1.0" encoding="utf-8"?>
<!DOCTYPE html>
<html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops" xml:lang="{lang}" lang="{lang}">
<head>
<meta charset="utf-8"/>
<title>{title}</title>
<link rel="stylesheet" type="text/css" href="../styles/poetry.css"/>
</head>
<body>
"""
XHTML_TAIL = "</body>\n</html>\n"


@dataclass
class SpineItem:
    id: str
    href: str  # relative to OEBPS/
    content: str
    title: str
    nav: bool = True  # appear in TOC
    part: bool = False


def render_work_xhtml(work: Work, lang: str = "ru") -> str:
    out = [XHTML_HEAD.format(lang=lang, title=escape(work.title))]
    out.append('<section class="poem" epub:type="chapter">\n')
    out.append(f"<h1>{escape(work.title)}</h1>\n")
    if work.subtitle:
        out.append(f'<p class="subtitle">{escape(work.subtitle)}</p>\n')
    for b in work.blocks:
        if isinstance(b, Stanza):
            out.append('<div class="stanza">\n')
            for ln in b.lines:
                cls = "line" + (f" indent{ln.indent}" if ln.indent else "")
                out.append(f'<p class="{cls}">{escape(ln.text)}</p>\n')
            out.append("</div>\n")
        elif isinstance(b, Separator):
            out.append(f'<div class="separator">{escape(b.text)}</div>\n')
        elif isinstance(b, Heading):
            out.append(f'<h2 class="section">{escape(b.text)}</h2>\n')
        elif isinstance(b, Paragraph):
            out.append(f'<p class="prose">{escape(b.text)}</p>\n')
    date = format_date(work.date, work.year)
    if date:
        out.append(f'<p class="date">{escape(date)}</p>\n')
    out.append("</section>\n")
    out.append(XHTML_TAIL)
    return "".join(out)


def format_date(date: str | None, year: int | None) -> str | None:
    """Printed date line: the source's creation date, tidied; else the year."""
    if not date:
        return str(year) if year else None
    d = date.strip()
    d = d.replace("‹", "").replace("›", "").replace("<", "").replace(">", "")
    d = re.sub(r"\s*\bг\.\s*$", "", d)
    d = re.sub(r"\s+—\s*(?=\d)", " — ", d)
    d = re.sub(r"\s+", " ", d).strip(" ,;")
    return d or (str(year) if year else None)


def render_part_xhtml(number: int, title: str, lang: str = "ru") -> str:
    roman = _roman(number)
    return (
        XHTML_HEAD.format(lang=lang, title=escape(title))
        + '<section class="part" epub:type="part">\n'
        + f'<h2 class="part-number">{roman}</h2>\n'
        + f'<h1 class="part-title">{escape(title)}</h1>\n'
        + "</section>\n"
        + XHTML_TAIL
    )


def render_titlepage_xhtml(book: BookSpec) -> str:
    author = book.author
    title = book.title
    if " — " in title:
        title = title.split(" — ", 1)[1]
    return (
        XHTML_HEAD.format(lang=book.language, title=escape(book.title))
        + '<section class="front" epub:type="titlepage">\n'
        + f'<h1 class="book-title">{escape(title)}</h1>\n'
        + f'<p class="book-author">{escape(author)}</p>\n'
        + "</section>\n"
        + XHTML_TAIL
    )


def render_colophon_xhtml(lang: str = "ru") -> str:
    lines = [
        "Тексты: общественное достояние.",
        "Основной электронный источник: Викитека (ru.wikisource.org).",
        "Сборка EPUB: персональная подборка.",
    ]
    body = "".join(f"<p>{escape(t)}</p>\n" for t in lines)
    return (
        XHTML_HEAD.format(lang=lang, title="Колофон")
        + '<section class="colophon" epub:type="colophon">\n'
        + body
        + "</section>\n"
        + XHTML_TAIL
    )


def render_cover_xhtml(lang: str, image_href: str) -> str:
    return (
        XHTML_HEAD.format(lang=lang, title="Обложка")
        + '<section epub:type="cover" style="text-align:center;margin:0;padding:0">\n'
        + f'<img src="../{image_href}" alt="Обложка" style="max-width:100%;max-height:100%"/>\n'
        + "</section>\n"
        + XHTML_TAIL
    )


def render_nav_xhtml(book: BookSpec, items: list[SpineItem], cover_href: str | None) -> str:
    out = [
        XHTML_HEAD.format(lang=book.language, title="Содержание"),
        '<nav epub:type="toc" id="toc">\n<h1>Содержание</h1>\n<ol>\n',
    ]
    open_part = False
    for it in items:
        if not it.nav:
            continue
        href = it.href.split("/", 1)[1] if it.href.startswith("text/") else "../" + it.href
        if it.part:
            if open_part:
                out.append("</ol>\n</li>\n")
            out.append(f'<li><a href="{href}">{escape(it.title)}</a>\n<ol>\n')
            open_part = True
        else:
            if not open_part:
                out.append(f'<li><a href="{href}">{escape(it.title)}</a></li>\n')
            else:
                out.append(f'<li><a href="{href}">{escape(it.title)}</a></li>\n')
    if open_part:
        out.append("</ol>\n</li>\n")
    out.append("</ol>\n</nav>\n")
    # landmarks
    out.append('<nav epub:type="landmarks" hidden="hidden">\n<ol>\n')
    if cover_href:
        out.append('<li><a epub:type="cover" href="cover.xhtml">Обложка</a></li>\n')
    out.append('<li><a epub:type="toc" href="nav.xhtml">Содержание</a></li>\n')
    first = next((i for i in items if i.nav and i.part), None) or next((i for i in items if i.nav), None)
    if first:
        out.append(f'<li><a epub:type="bodymatter" href="{first.href.split("/",1)[1]}">Начало</a></li>\n')
    out.append("</ol>\n</nav>\n")
    out.append(XHTML_TAIL)
    return "".join(out)


def render_ncx(book: BookSpec, items: list[SpineItem]) -> str:
    out = [
        '<?xml version="1.0" encoding="utf-8"?>\n',
        '<ncx xmlns="http://www.daisy.org/z3986/2005/ncx/" version="2005-1" xml:lang="{}">\n'.format(book.language),
        f'<head><meta name="dtb:uid" content="{escape(book.identifier)}"/><meta name="dtb:depth" content="2"/>'
        '<meta name="dtb:totalPageCount" content="0"/><meta name="dtb:maxPageNumber" content="0"/></head>\n',
        f"<docTitle><text>{escape(book.title)}</text></docTitle>\n<navMap>\n",
    ]
    n = 0
    open_part = False
    for it in items:
        if not it.nav:
            continue
        n += 1
        if it.part:
            if open_part:
                out.append("</navPoint>\n")
            out.append(f'<navPoint id="np{n}" playOrder="{n}"><navLabel><text>{escape(it.title)}</text></navLabel><content src="{it.href}"/>\n')
            open_part = True
        else:
            out.append(f'<navPoint id="np{n}" playOrder="{n}"><navLabel><text>{escape(it.title)}</text></navLabel><content src="{it.href}"/></navPoint>\n')
    if open_part:
        out.append("</navPoint>\n")
    out.append("</navMap>\n</ncx>\n")
    return "".join(out)


def render_opf(book: BookSpec, items: list[SpineItem], cover_href: str | None, modified: str) -> str:
    manifest = [
        '<item id="nav" href="text/nav.xhtml" media-type="application/xhtml+xml" properties="nav"/>',
        '<item id="ncx" href="toc.ncx" media-type="application/x-dtbncx+xml"/>',
        '<item id="css" href="styles/poetry.css" media-type="text/css"/>',
    ]
    if cover_href:
        manifest.append(f'<item id="cover-image" href="{cover_href}" media-type="image/png" properties="cover-image"/>')
    spine = []
    for it in items:
        if it.id == "nav":
            spine.append('<itemref idref="nav"/>')
            continue
        manifest.append(f'<item id="{it.id}" href="{it.href}" media-type="application/xhtml+xml"/>')
        spine.append(f'<itemref idref="{it.id}"/>')
    meta = [
        f'<dc:identifier id="pub-id">{escape(book.identifier)}</dc:identifier>',
        f'<dc:title>{escape(book.title)}</dc:title>',
        f'<dc:creator id="creator">{escape(book.author)}</dc:creator>',
        '<meta refines="#creator" property="role" scheme="marc:relators">aut</meta>',
        f'<dc:language>{escape(book.language)}</dc:language>',
        f'<meta property="dcterms:modified">{modified}</meta>',
    ]
    if book.description:
        meta.append(f'<dc:description>{escape(book.description)}</dc:description>')
    if cover_href:
        meta.append('<meta name="cover" content="cover-image"/>')
    return (
        '<?xml version="1.0" encoding="utf-8"?>\n'
        '<package xmlns="http://www.idpf.org/2007/opf" version="3.0" unique-identifier="pub-id" xml:lang="{lang}">\n'
        '<metadata xmlns:dc="http://purl.org/dc/elements/1.1/">\n{meta}\n</metadata>\n'
        "<manifest>\n{manifest}\n</manifest>\n"
        '<spine toc="ncx">\n{spine}\n</spine>\n'
        "</package>\n"
    ).format(lang=book.language, meta="\n".join(meta), manifest="\n".join(manifest), spine="\n".join(spine))


CONTAINER_XML = """<?xml version="1.0" encoding="utf-8"?>
<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">
  <rootfiles>
    <rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/>
  </rootfiles>
</container>
"""


def _roman(n: int) -> str:
    vals = [(10, "X"), (9, "IX"), (5, "V"), (4, "IV"), (1, "I")]
    out = ""
    for v, s in vals:
        while n >= v:
            out += s
            n -= v
    return out


def assemble(
    book: BookSpec,
    works: list[tuple[str, Work]],
    cover_png: bytes | None,
) -> dict[str, bytes]:
    """Return {zip path: bytes} for the whole package (mimetype first)."""
    items: list[SpineItem] = []
    files: dict[str, bytes] = {}
    cover_href = "images/cover.png" if cover_png else None
    if cover_png:
        files["OEBPS/images/cover.png"] = cover_png
        items.append(SpineItem("cover", "text/cover.xhtml", render_cover_xhtml(book.language, cover_href), "Обложка", nav=False))
    items.append(SpineItem("titlepage", "text/titlepage.xhtml", render_titlepage_xhtml(book), "Титул", nav=False))
    items.append(SpineItem("nav", "text/nav.xhtml", "", "Содержание", nav=False))

    n = 0
    part_no = 0
    current_section = None
    for section, work in works:
        if section != current_section:
            current_section = section
            part_no += 1
            pid = f"part-{part_no:02d}"
            items.append(SpineItem(pid, f"text/{pid}.xhtml", render_part_xhtml(part_no, section, book.language), section, part=True))
        n += 1
        wid = f"w{n:03d}"
        href = f"text/{n:03d}-{slugify(work.slug, 48)}.xhtml"
        items.append(SpineItem(wid, href, render_work_xhtml(work, book.language), work.title))
    items.append(SpineItem("colophon", "text/colophon.xhtml", render_colophon_xhtml(book.language), "Колофон", nav=False))

    modified = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    files["mimetype"] = b"application/epub+zip"
    files["META-INF/container.xml"] = CONTAINER_XML.encode("utf-8")
    files["OEBPS/content.opf"] = render_opf(book, items, cover_href, modified).encode("utf-8")
    files["OEBPS/toc.ncx"] = render_ncx(book, items).encode("utf-8")
    files["OEBPS/styles/poetry.css"] = CSS.encode("utf-8")
    for it in items:
        if it.id == "nav":
            files["OEBPS/" + it.href] = render_nav_xhtml(book, items, cover_href).encode("utf-8")
        else:
            files["OEBPS/" + it.href] = it.content.encode("utf-8")
    return files


def write_epub(files: dict[str, bytes], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, "w") as z:
        z.writestr(zipfile.ZipInfo("mimetype"), files["mimetype"], compress_type=zipfile.ZIP_STORED)
        for name, data in files.items():
            if name == "mimetype":
                continue
            info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            z.writestr(info, data)
