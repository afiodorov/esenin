import json
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

import pytest

from esenin_epub import curate
from esenin_epub.epub import assemble, format_date, write_epub
from esenin_epub.models import BookSpec, Line, Separator, Stanza, Work
from esenin_epub.normalize import parse_wikisource_html
from esenin_epub.validate import validate_epub

DIST_EPUB = curate.DIST_DIR / "esenin-love-and-tales.epub"
XH = "{http://www.w3.org/1999/xhtml}"


def _book():
    return BookSpec(title="Тест — Книга", author="Сергей Есенин", language="ru", identifier="urn:uuid:00000000-0000-4000-8000-000000000001")


def _work(slug, title, lines):
    return Work(slug=slug, title=title, source_title=f"{title} (Есенин)", source_url="https://ru.wikisource.org/wiki/x",
                blocks=[Stanza(lines=[Line(text=t) for t in lines]), Separator(), Stanza(lines=[Line(text="Ещё строка")])])


def test_synthetic_epub_is_valid(tmp_path, sirotka_html):
    parsed = parse_wikisource_html(sirotka_html)
    sirotka = Work(slug="sirotka", title="Сиротка", subtitle=parsed.subtitle, source_title="Сиротка (Есенин)",
                   source_url="https://ru.wikisource.org/wiki/x", blocks=parsed.blocks, date=parsed.date)
    works = [("Часть А", _work("a", "Первое", ["Раз", "Два"])), ("Часть А", _work("b", "Второе…", ["Три"])), ("Сказки", sirotka)]
    files = assemble(_book(), works, cover_png=None)
    out = tmp_path / "t.epub"
    write_epub(files, out)
    assert validate_epub(out) == []
    with zipfile.ZipFile(out) as z:
        names = z.namelist()
        assert names[0] == "mimetype"
        assert z.getinfo("mimetype").compress_type == zipfile.ZIP_STORED
        assert z.read("mimetype") == b"application/epub+zip"
        assert "META-INF/container.xml" in names
        assert all(n.isascii() and " " not in n for n in names)
        poem_files = [n for n in names if n.startswith("OEBPS/text/00")]
        assert len(poem_files) == 3  # one XHTML per work
        nav = ET.fromstring(z.read("OEBPS/text/nav.xhtml"))
        toc = [n for n in nav.iter(XH + "nav") if n.get("{http://www.idpf.org/2007/ops}type") == "toc"][0]
        top = toc.find(XH + "ol").findall(XH + "li")
        assert [li.find(XH + "a").text for li in top] == ["Часть А", "Сказки"]
        assert [a.text for a in top[0].find(XH + "ol").iter(XH + "a")] == ["Первое", "Второе…"]
        x = z.read([n for n in poem_files if "sirotka" in n][0]).decode()
        assert '<p class="subtitle">Русская сказка</p>' in x
        assert "Маша — круглая сиротка." in x
        assert x.rstrip().endswith('<p class="date">1914</p>\n</section>\n</body>\n</html>')
        assert '<link rel="stylesheet"' in x and "style=" not in x.split("<body>")[1]
        css = z.read("OEBPS/styles/poetry.css").decode()
        assert "font-family" not in css and "background" not in css
        assert "text-indent: -1.2em" in css


@pytest.mark.skipif(not DIST_EPUB.exists(), reason="dist EPUB not built")
def test_dist_epub_matches_selection():
    assert validate_epub(DIST_EPUB) == []
    sel = curate.load_selection()
    expected = len(sel.all_specs())
    with zipfile.ZipFile(DIST_EPUB) as z:
        opf = ET.fromstring(z.read("OEBPS/content.opf"))
        ns = {"opf": "http://www.idpf.org/2007/opf", "dc": "http://purl.org/dc/elements/1.1/"}
        spine = [r.get("idref") for r in opf.findall("opf:spine/opf:itemref", ns)]
        assert len([i for i in spine if i.startswith("w")]) == expected
        assert opf.findtext("opf:metadata/dc:language", namespaces=ns) == "ru"
        assert opf.findtext("opf:metadata/dc:creator", namespaces=ns) == "Сергей Александрович Есенин"
        sirotka = [n for n in z.namelist() if n.endswith("-sirotka.xhtml")]
        assert len(sirotka) == 1
        assert "Злая мачеха" in z.read(sirotka[0]).decode()
    manifest = json.loads((curate.DIST_DIR / "manifest.json").read_text(encoding="utf-8"))
    assert len(manifest["works"]) == expected
    assert all(w["source_revision"] for w in manifest["works"])
    assert manifest["works"][0]["title"].startswith("Заметался пожар голубой")


def test_format_date():
    assert format_date("1923 —› 14 ноября 1925 г.", 1925) == "1923 — 14 ноября 1925"
    assert format_date("<1914>", 1914) == "1914"
    assert format_date("Январь 1925 Батум", 1925) == "Январь 1925 Батум"
    assert format_date(None, 1916) == "1916"
    assert format_date(None, None) is None
