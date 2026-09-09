from esenin_epub.models import Heading, Paragraph, Separator, Stanza
from esenin_epub.normalize import clean_line, parse_override_text, parse_wikisource_html

JUNK = ["Править", "Источник", "Категория", "Викитека", "Дата создания", "Комментарий", "ws-", "mw-", "NewPP", "Ссылки", "ранняя редакция"]


def _lines(parsed):
    return [ln.text for b in parsed.blocks if isinstance(b, Stanza) for ln in b.lines]


def test_sirotka_structure(sirotka_html):
    p = parse_wikisource_html(sirotka_html)
    assert p.title == "Сиротка"
    assert p.subtitle == "Русская сказка"
    assert p.date == "1914"
    lines = _lines(p)
    assert lines[0] == "Маша — круглая сиротка."
    assert lines[1] == "Плохо, плохо Маше жить,"
    assert "Злая мачеха" in "\n".join(lines)
    assert lines[-1] == "Повенчался сам король."
    stanzas = [b for b in p.blocks if isinstance(b, Stanza)]
    assert len(stanzas) == 31
    assert all(len(s.lines) == 4 for s in stanzas)
    assert len(lines) == 124


def test_sirotka_no_site_junk(sirotka_html):
    p = parse_wikisource_html(sirotka_html)
    text = "\n".join(_lines(p))
    for junk in JUNK:
        assert junk not in text
    assert "1914" not in text  # date is metadata, not verse


def test_chorny_chelovek_title_date_and_separators(chorny_html):
    p = parse_wikisource_html(chorny_html)
    lines = _lines(p)
    assert lines[0] == "Друг мой, друг мой,"
    assert lines[-1] == "И разбитое зеркало…"
    assert "Черный человек" not in lines[:1]
    assert "1925" in (p.date or "")
    seps = [b for b in p.blocks if isinstance(b, Separator)]
    assert len(seps) == 2
    assert all(s.text.startswith("·") for s in seps)


def test_links_section_is_dropped(tanyusha_html):
    p = parse_wikisource_html(tanyusha_html)
    lines = _lines(p)
    assert len(lines) == 16
    assert not any(isinstance(b, Heading) for b in p.blocks)
    assert "старой орфографии" not in "\n".join(lines)


def test_clean_line_keeps_typography():
    assert clean_line("Маша — круглая‎ сиротка. ") == "Маша — круглая сиротка."
    assert clean_line("Ещё «ё» и — тире…") == "Ещё «ё» и — тире…"


def test_override_text_parsing():
    sub, blocks = parse_override_text("subtitle: Русская сказка\nСтрока раз\nСтрока два\n\n*\n\n# 2\n  Отступ\n")
    assert sub == "Русская сказка"
    assert isinstance(blocks[0], Stanza) and [l.text for l in blocks[0].lines] == ["Строка раз", "Строка два"]
    assert isinstance(blocks[1], Separator)
    assert isinstance(blocks[2], Heading) and blocks[2].text == "2"
    assert isinstance(blocks[3], Stanza) and blocks[3].lines[0].indent == 1


def test_dedication_becomes_paragraph():
    html = '<div class="mw-parser-output"><div class="poem"><p>Сестре Шуре<br/></p><p>Раз<br/>Два<br/></p></div></div>'
    p = parse_wikisource_html(html, title_hint="Тест")
    assert isinstance(p.blocks[0], Paragraph) and p.blocks[0].text == "Сестре Шуре"
    assert isinstance(p.blocks[1], Stanza)
