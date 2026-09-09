"""Turn a rendered Wikisource page into a structured Work (title, subtitle, blocks).

Everything here is rule-based. Wikisource renders every poem template
(poemx, poem, f1, poem-on/off, <poem>, <pre>) into the same shape: a run of
verse lines separated by <br/>, stanza breaks as blank lines or <p> boundaries,
authorial separators as centred '*', a title heading, and a right-aligned date.
We keep the verse and drop everything else.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from bs4 import BeautifulSoup, Comment, NavigableString, Tag

from esenin_epub.models import Block, Heading, Line, Paragraph, Separator, Stanza

# Elements that are site chrome / apparatus, never Yesenin's text.
STRIP_SELECTORS = [
    ".ws-noexport", "#headertemplate", ".headertemplate", ".header_notes", "table.header_notes",
    ".dablink", ".mw-editsection", "sup.reference", ".reflist", ".mw-references-wrap",
    "ol.references", ".catlinks", ".navbox", "#ws-footer", "#extra_nav", ".noprint",
    "style", "script", ".mw-empty-elt", ".versions", ".printfooter", ".ws-summary",
    "#toc", ".toc", "#otherVersions", "[style*='display: none']", "[style*='display:none']", ".mw-cite-backlink", ".mw-indicators", "span.textquality", ".ws-license",
]
NOTE_HEADINGS = {"примечания", "примечание", "комментарии", "комментарий", "варианты", "другие редакции", "ссылки", "см. также", "источник", "источники", "литература"}

BLOCK_TAGS = {"p", "div", "center", "table", "tbody", "tr", "td", "th", "pre", "li", "ul", "ol",
              "blockquote", "section", "hr", "h1", "h2", "h3", "h4", "h5", "h6", "dd", "dl", "dt"}

_MONTHS = "январ|феврал|март|апрел|ма[йя]|июн|июл|август|сентябр|октябр|ноябр|декабр"
_SEP_RE = re.compile(r"^(?:[\*·•\.•·…\s]+|[—–\-_]{3,})$")
_NUM_HEADING_RE = re.compile(r"^(?:\d{1,2}|[IVXLC]{1,6})\.?$")
_INVISIBLE_RE = re.compile("[​‌‍‎‏﻿⁠­]")
_PAGE_NUM_RE = re.compile(r"^\[?\s*(?:стр\.?\s*)?\d{1,4}\s*\]?$")


def _is_date_line(text: str) -> bool:
    t = text.strip()
    if not re.search(r"1[89]\d\d", t):
        return False
    rest = re.sub(r"(?:" + _MONTHS + r")[а-яё]*", " ", t, flags=re.I)
    rest = re.sub(r"\bг\.|\bгод[а-я]*|\d+|[‹›<>()\[\]/,.;:—–\-\s*]", " ", rest)
    words = rest.split()
    # Only place names / a stray word may remain ("Батум", "Баку", "Тифлис").
    return len(words) <= 3 and all(w[:1].isupper() for w in words)


def clean_line(text: str) -> str:
    text = _INVISIBLE_RE.sub("", text)
    text = text.replace(" ", " ").replace(" ", " ").replace(" ", " ")
    text = re.sub(r"[ \t]+", " ", text)
    return text.strip()


@dataclass
class _Tok:
    kind: str  # line | blank | heading | sep | date | subtitle
    text: str = ""
    indent: int = 0


@dataclass
class _Walker:
    tokens: list[_Tok] = field(default_factory=list)
    buf: list[str] = field(default_factory=list)
    indent: int = 0
    italic_only: bool = True
    _in_i: int = 0

    def flush(self) -> None:
        text = clean_line("".join(self.buf))
        if text:
            if _SEP_RE.match(text):
                self.tokens.append(_Tok("sep", text))
            elif _PAGE_NUM_RE.match(text) and False:  # page numbers handled at block stage
                pass
            else:
                self.tokens.append(_Tok("line", text, self.indent))
        self.buf = []
        self.indent = 0
        self.italic_only = True

    def blank(self) -> None:
        self.flush()
        if self.tokens and self.tokens[-1].kind != "blank":
            self.tokens.append(_Tok("blank"))

    def walk(self, node) -> None:
        if isinstance(node, Comment):
            return
        if isinstance(node, NavigableString):
            s = str(node)
            if "\n" in s and node.find_parent("pre") is not None:
                parts = s.split("\n")
                for i, part in enumerate(parts):
                    if i:
                        self.flush()
                    stripped = part.lstrip(" ")
                    if stripped and not self.buf:
                        self.indent = min(3, (len(part) - len(stripped)) // 4)
                    self.buf.append(stripped)
                return
            s = s.replace("\n", " ")
            if not self.buf and s.strip():
                lead = len(s) - len(s.lstrip("  "))
                if lead >= 4:
                    self.indent = max(self.indent, min(3, lead // 4))
            if s.strip() and self._in_i == 0:
                self.italic_only = False
            self.buf.append(s)
            return
        if not isinstance(node, Tag):
            return
        name = node.name.lower()
        if name == "br":
            if not "".join(self.buf).strip() and self.tokens and self.tokens[-1].kind == "line":
                self.blank()  # <br/><br/> = stanza break
            else:
                self.flush()
            return
        if name == "hr":
            self.blank()
            return
        if name in {"h1", "h2", "h3", "h4", "h5", "h6"}:
            self.blank()
            text = clean_line(node.get_text(" "))
            self.tokens.append(_Tok("heading", text))
            self.tokens.append(_Tok("blank"))
            return
        style = (node.get("style") or "").replace(" ", "").lower()
        if name == "span" and "margin-left" in style:
            m = re.search(r"margin-left:(\d+(?:\.\d+)?)(ex|em|px)", style)
            if m:
                val = float(m.group(1))
                unit = m.group(2)
                ex = val if unit == "ex" else val * 2 if unit == "em" else val / 8
                if not "".join(self.buf).strip():
                    self.indent = max(self.indent, min(3, int(round(ex / 4)) or 1))
        if name == "center" or (name in {"div", "p"} and "text-align:center" in style):
            self.blank()
            text = clean_line(node.get_text(" "))
            if _SEP_RE.match(text):
                self.tokens.append(_Tok("sep", text))
            elif _NUM_HEADING_RE.match(text):
                self.tokens.append(_Tok("heading", text))
            elif re.fullmatch(r"\(.+\)", text) and node.find("i") is not None:
                self.tokens.append(_Tok("subtitle", text[1:-1].strip()))
            elif text:
                self.tokens.append(_Tok("line", text))
            self.tokens.append(_Tok("blank"))
            return
        if name in {"div", "p"} and "text-align:right" in style:
            self.blank()
            text = clean_line(node.get_text(" "))
            if _is_date_line(text):
                self.tokens.append(_Tok("date", text))
            elif text:
                self.tokens.append(_Tok("line", text))
            self.tokens.append(_Tok("blank"))
            return
        if name in {"i", "em"}:
            self._in_i += 1
            for child in node.children:
                self.walk(child)
            self._in_i -= 1
            return
        if name in BLOCK_TAGS:
            self.blank()
            for child in node.children:
                self.walk(child)
            self.blank()
            return
        for child in node.children:
            self.walk(child)


@dataclass
class ParsedPage:
    title: str | None
    subtitle: str | None
    date: str | None
    blocks: list[Block]


def _tokens_to_blocks(tokens: list[_Tok], title: str | None) -> tuple[list[Block], str | None, str | None]:
    subtitle: str | None = None
    date: str | None = None
    blocks: list[Block] = []
    cur: list[Line] = []
    seen_title_heading = False
    dropping_notes = False

    def close() -> None:
        nonlocal cur
        if cur:
            blocks.append(Stanza(lines=cur))
            cur = []

    norm_title = _norm(title) if title else None
    for i, tok in enumerate(tokens):
        if dropping_notes:
            continue
        if tok.kind == "blank":
            close()
        elif tok.kind == "heading":
            close()
            low = tok.text.lower().strip(" :.")
            if low in NOTE_HEADINGS:
                dropping_notes = True
                continue
            if not seen_title_heading and not blocks and (
                norm_title is None or _norm(tok.text) == norm_title or _norm(tok.text) in {"* * *", "***", "*"}
                or (norm_title and _norm(tok.text).startswith(norm_title[:20]))
            ):
                seen_title_heading = True
                continue
            if tok.text:
                blocks.append(Heading(text=tok.text))
        elif tok.kind == "sep":
            close()
            blocks.append(Separator(text=_normalize_sep(tok.text)))
        elif tok.kind == "date":
            close()
            date = date or tok.text.strip("‹›<>() ")
        elif tok.kind == "subtitle":
            close()
            if subtitle is None and not blocks:
                subtitle = tok.text
            else:
                blocks.append(Paragraph(text=f"({tok.text})"))
        elif tok.kind == "line":
            if _PAGE_NUM_RE.match(tok.text):
                continue
            # First plain line equal to the title (f1 template renders the title as a line).
            if not blocks and not cur and not seen_title_heading and norm_title and _norm(tok.text) == norm_title:
                seen_title_heading = True
                continue
            # A trailing italic date inside the last paragraph (f1 template).
            remaining = []
            for t in tokens[i + 1:]:
                if t.kind == "heading" and t.text.lower().strip(" :.") in NOTE_HEADINGS:
                    break
                if t.kind == "line":
                    remaining.append(t)
            if not remaining and _is_date_line(tok.text):
                close()
                date = date or tok.text.strip("‹›<>() ")
                continue
            if not blocks and not cur and subtitle is None and re.fullmatch(r"\(.+\)", tok.text):
                subtitle = tok.text[1:-1].strip()
                continue
            cur.append(Line(text=tok.text, indent=tok.indent))
    close()
    # Drop leading/trailing separators and merge doubled separators.
    out: list[Block] = []
    for b in blocks:
        if isinstance(b, Separator) and (not out or isinstance(out[-1], Separator)):
            continue
        out.append(b)
    while out and isinstance(out[-1], Separator):
        out.pop()
    # A lone first line before the verse proper is a dedication ("Сестре Шуре").
    if len(out) > 1 and isinstance(out[0], Stanza) and len(out[0].lines) == 1 and isinstance(out[1], Stanza):
        out[0] = Paragraph(text=out[0].lines[0].text)
    return out, subtitle, date


def _norm(s: str) -> str:
    s = clean_line(s).lower()
    s = re.sub(r"[«»\"'“”„…\.,!?:;\-—–()]", "", s)
    return re.sub(r"\s+", " ", s).strip()


def _normalize_sep(text: str) -> str:
    t = text.strip()
    if set(t) <= set("* "):
        return "*" if t.count("*") == 1 else "* * *"
    return t


def parse_wikisource_html(html: str, title_hint: str | None = None) -> ParsedPage:
    soup = BeautifulSoup(html, "lxml")
    root = soup.select_one(".mw-parser-output") or soup

    ws_title = root.select_one("#ws-title")
    ws_sub = root.select_one("#ws-subtitle")
    ws_created = root.select_one("#ws-created")
    header_title = clean_line(ws_title.get_text(" ")) if ws_title else None
    header_sub = clean_line(ws_sub.get_text(" ")) if ws_sub else None
    header_date = clean_line(ws_created.get_text(" ")) if ws_created else None

    for sel in STRIP_SELECTORS:
        for el in root.select(sel):
            el.decompose()
    for c in root.find_all(string=lambda s: isinstance(s, Comment)):
        c.extract()

    title = header_title or title_hint
    w = _Walker()
    w.walk(root)
    w.blank()
    blocks, subtitle, date = _tokens_to_blocks(w.tokens, title)
    if not subtitle and header_sub:
        subtitle = header_sub
    if not blocks:
        raise ValueError("no verse found in page")
    return ParsedPage(title=title, subtitle=subtitle or None, date=date or header_date, blocks=blocks)


def parse_override_text(text: str) -> tuple[str | None, list[Block]]:
    """content/overrides/<slug>.txt -> (subtitle, blocks)."""
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    lines = text.split("\n")
    subtitle = None
    if lines and lines[0].lower().startswith("subtitle:"):
        subtitle = lines.pop(0).split(":", 1)[1].strip()
    blocks: list[Block] = []
    cur: list[Line] = []

    def close() -> None:
        nonlocal cur
        if cur:
            blocks.append(Stanza(lines=cur))
            cur = []

    for raw in lines:
        stripped = raw.lstrip(" ")
        indent = min(3, (len(raw) - len(stripped)) // 2)
        t = clean_line(stripped)
        if not t:
            close()
        elif t.startswith("# "):
            close()
            blocks.append(Heading(text=t[2:].strip()))
        elif _SEP_RE.match(t):
            close()
            blocks.append(Separator(text=_normalize_sep(t)))
        else:
            cur.append(Line(text=t, indent=indent))
    close()
    return subtitle, blocks


def year_from_date(date: str | None) -> int | None:
    if not date:
        return None
    m = re.search(r"1[89]\d\d", date)
    return int(m.group(0)) if m else None
