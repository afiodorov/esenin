"""Enumerate Yesenin's Wikisource corpus and write dist/discovery.md.

No LLM involved: the index pages give title + year; content/discovery.yaml
holds hand-written category/decision/reason notes; anything unannotated gets a
keyword guess and 'exclude'. Works present in selection.yaml are 'include'.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import yaml

from esenin_epub.models import Selection
from esenin_epub.sources.wikisource import WikisourceClient, page_url

INDEX_PAGES = [
    "Сергей Александрович Есенин/Стихотворения 1910—1915",
    "Сергей Александрович Есенин/Стихотворения 1916—1923",
    "Сергей Александрович Есенин/Стихотворения 1924—1925",
    "Автор:Сергей Александрович Есенин",
]
CATEGORIES = ["love", "relationship", "confessional", "tavern/hooligan", "mortality", "fairy-tale/narrative", "nature", "politics/revolution", "religion", "other"]
_KEYWORDS = {
    "love": ["любим", "люб", "целу", "милая", "дорогая", "ты ", "тебя", "женщин", "девушк", "глаза", "кофта"],
    "fairy-tale/narrative": ["сказ", "песнь о", "баллада", "сиротка", "лебёдушка", "королева", "разбойник", "русалка", "колдунья"],
    "religion": ["бог", "молитв", "господь", "инок", "иисус", "микола", "радуниц", "богомолк", "октоих", "пришествие", "преображение", "иорданск", "часослов", "пантократор", "исус", "егорий"],
    "politics/revolution": ["русь советская", "ленин", "капитан земли", "1 мая", "баллада о двадцати", "поэма о 36", "великом походе", "небесный барабанщик", "товарищ", "певущий зов", "инония", "кантата", "стансы", "заря востока", "пугач"],
    "tavern/hooligan": ["кабац", "хулиган", "пьют", "гармоник", "гитар", "спирт", "водк", "забав"],
    "mortality": ["покойник", "могил", "смерт", "уходим", "прощай", "до свиданья", "поминки", "отговорила"],
    "nature": ["берёз", "роща", "заря", "вечер", "ночь", "поле", "туч", "луна", "месяц", "снег", "зима", "весн", "осен", "ветер", "ветры", "дожд", "пурга", "метель", "вьюга", "звёзд", "черёмух", "листв", "рябин", "озер", "тростник", "пороша", "восход", "равнин", "степь", "клён", "ковыль", "лунн", "синий", "голуб", "сани", "кон"],
}


@dataclass
class Candidate:
    title: str
    label: str
    year: str
    section: str
    category: str = "other"
    decision: str = "exclude"
    reason: str = ""


_LINK_RE = re.compile(r"\[\[([^\]|#]+?)(?:#[^\]|]*)?\|([^\]]+)\]\]")
_TPL_RE = re.compile(r"\{\{2О\|([^|}]+)\|([^}]+)\}\}")


def parse_index(wikitext: str, section_name: str) -> list[Candidate]:
    out: list[Candidate] = []
    year = ""
    for raw in wikitext.splitlines():
        line = raw.strip()
        m = re.match(r"^==+\s*(.+?)\s*==+$", line)
        if m:
            year = m.group(1).strip()
            continue
        if not line.startswith(("*", "#")):
            continue
        if "ранняя редакция" in line or "редакция" in line and line.startswith("**") and "''" in line:
            continue
        links = [(m.group(1).strip(), m.group(2).strip()) for m in _LINK_RE.finditer(line)]
        links += [(m.group(1).strip(), m.group(2).strip()) for m in _TPL_RE.finditer(line)]
        for title, label in links:
            if title.startswith(("Файл:", ":", "Автор:", "Категория:")) or "Есенин" not in title and section_name != "author":
                continue
            if "/" in title and "Есенин)" not in title.split("/")[0]:
                continue
            label = re.sub(r"''+", "", label).strip()
            yr = year
            m2 = re.search(r"''\(?(\d{4}(?:—\d{4})?)\)?''", line)
            if m2:
                yr = m2.group(1)
            out.append(Candidate(title=title, label=label, year=yr, section=section_name))
    return out


def guess_category(label: str) -> str:
    low = label.lower()
    for cat in ["politics/revolution", "religion", "fairy-tale/narrative", "tavern/hooligan", "mortality", "love", "nature"]:
        if any(k in low for k in _KEYWORDS[cat]):
            return cat
    return "other"


def load_annotations(path: Path) -> dict[str, dict]:
    if not path.exists():
        return {}
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return {k: (v or {}) for k, v in data.items()}


def discover(client: WikisourceClient, selection: Selection, annotations: dict[str, dict], refresh: bool = False) -> list[Candidate]:
    selected = {w.source_title: s.title for s, w in selection.all_specs()}
    seen: dict[str, Candidate] = {}
    for page in INDEX_PAGES:
        wt, _ = client.get_wikitext(page, refresh=refresh)
        name = page.split("/")[-1] if "/" in page else "author"
        for c in parse_index(wt, name):
            if c.title in seen:
                continue
            seen[c.title] = c
    for title, section in selected.items():
        if title not in seen:
            spec = next(w for _, w in selection.all_specs() if w.source_title == title)
            seen[title] = Candidate(title=title, label=spec.display_title or title.replace(" (Есенин)", ""), year=str(spec.year or ""), section="selection")
    for c in seen.values():
        ann = annotations.get(c.title, {})
        c.category = ann.get("category") or guess_category(c.label)
        if c.title in selected:
            c.decision = "include"
            c.reason = ann.get("reason") or f"in selection: {selected[c.title]}"
        else:
            c.decision = ann.get("decision", "exclude")
            c.reason = ann.get("reason") or ("unannotated; category guessed from title" if not ann else "")
    return list(seen.values())


def render_markdown(cands: list[Candidate]) -> str:
    counts: dict[str, int] = {}
    for c in cands:
        counts[c.decision] = counts.get(c.decision, 0) + 1
    out = ["# Discovery: Yesenin on Russian Wikisource\n"]
    out.append("Source index pages: " + ", ".join(f"[{p}]({page_url(p)})" for p in INDEX_PAGES) + "\n")
    out.append("Decisions: " + ", ".join(f"{k}={v}" for k, v in sorted(counts.items())) + f" (total {len(cands)})\n")
    out.append("| # | Title | Year | Category | Decision | Reason | Source |")
    out.append("|---|-------|------|----------|----------|--------|--------|")
    for i, c in enumerate(cands, 1):
        out.append(f"| {i} | {c.label} | {c.year} | {c.category} | **{c.decision}** | {c.reason} | [ws]({page_url(c.title)}) |")
    return "\n".join(out) + "\n"
