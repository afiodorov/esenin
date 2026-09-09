"""Load the curated selection and turn each entry into a normalized Work."""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

import yaml

from esenin_epub.models import Selection, Work, WorkSpec
from esenin_epub.normalize import parse_override_text, parse_wikisource_html, year_from_date
from esenin_epub.slug import slugify
from esenin_epub.sources.wikisource import WikisourceClient, page_url

ROOT = Path(__file__).resolve().parents[2]
CONTENT_DIR = ROOT / "content"
SELECTION_PATH = CONTENT_DIR / "selection.yaml"
OVERRIDES_DIR = CONTENT_DIR / "overrides"
CACHE_DIR = ROOT / "cache"
DIST_DIR = ROOT / "dist"


class SelectionError(ValueError):
    pass


def load_selection(path: Path = SELECTION_PATH) -> Selection:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    sel = Selection.model_validate(data)
    titles = Counter(w.source_title for _, w in sel.all_specs())
    dupes = [t for t, n in titles.items() if n > 1]
    if dupes:
        raise SelectionError(f"duplicate works in selection: {dupes}")
    slugs = Counter(slugify(w.source_title) for _, w in sel.all_specs())
    dupes = [t for t, n in slugs.items() if n > 1]
    if dupes:
        raise SelectionError(f"slug collision in selection: {dupes}")
    if not sel.sections:
        raise SelectionError("selection has no sections")
    return sel


def override_path(slug: str) -> Path:
    return OVERRIDES_DIR / f"{slug}.txt"


def normalized_path(slug: str, cache_dir: Path = CACHE_DIR) -> Path:
    return cache_dir / "normalized" / f"{slug}.json"


def build_work(spec: WorkSpec, client: WikisourceClient, refresh: bool = False) -> Work:
    """Fetch (or load from cache), normalize, apply override. Fails loudly."""
    slug = slugify(spec.source_title)
    page = client.get_page(spec.source_title, pinned_revision=spec.source_revision, refresh=refresh)
    try:
        parsed = parse_wikisource_html(page.html, title_hint=spec.display_title or _title_from_source(spec.source_title))
    except Exception as e:  # noqa: BLE001
        raise RuntimeError(f"failed to parse {spec.source_title!r} ({page_url(spec.source_title)}): {e}") from e

    subtitle = spec.display_subtitle or parsed.subtitle
    blocks = parsed.blocks
    override = False
    op = override_path(slug)
    if op.exists():
        o_sub, o_blocks = parse_override_text(op.read_text(encoding="utf-8"))
        if not o_blocks:
            raise RuntimeError(f"override {op} is empty")
        blocks = o_blocks
        subtitle = spec.display_subtitle or o_sub or subtitle
        override = True

    title = spec.display_title or parsed.title or _title_from_source(spec.source_title)
    if subtitle and title and subtitle.lower() == title.lower():
        subtitle = None
    return Work(
        slug=slug,
        title=title,
        subtitle=subtitle,
        source_title=page.canonical_title or spec.source_title,
        source_url=spec.source_url or page_url(page.canonical_title or spec.source_title, page.revid),
        source_revision=page.revid,
        year=spec.year or year_from_date(parsed.date),
        date=parsed.date,
        cycle=spec.cycle,
        override=override,
        blocks=blocks,
    )


def _title_from_source(source_title: str) -> str:
    t = source_title.split("/")[0]
    if t.endswith("(Есенин)"):
        t = t[: -len("(Есенин)")].strip()
    return t


def save_normalized(work: Work, cache_dir: Path = CACHE_DIR) -> Path:
    p = normalized_path(work.slug, cache_dir)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(work.model_dump_json(indent=1), encoding="utf-8")
    return p


def load_normalized(slug: str, cache_dir: Path = CACHE_DIR) -> Work | None:
    p = normalized_path(slug, cache_dir)
    if not p.exists():
        return None
    return Work.model_validate_json(p.read_text(encoding="utf-8"))


def collect_works(
    selection: Selection,
    client: WikisourceClient,
    refresh: bool = False,
    log=print,
) -> list[tuple[str, Work]]:
    """Return [(section_title, Work)] in book order, writing normalized cache."""
    out: list[tuple[str, Work]] = []
    for section, spec in selection.all_specs():
        work = build_work(spec, client, refresh=refresh)
        save_normalized(work, client.raw_dir.parent)
        log(f"  {section.title[:28]:<28} {work.title[:48]:<48} rev={work.source_revision} lines={len(work.lines())}" + ("  [override]" if work.override else ""))
        out.append((section.title, work))
    return out


def write_manifest(selection: Selection, works: list[tuple[str, Work]], path: Path) -> None:
    entries = []
    for i, (section, w) in enumerate(works, 1):
        entries.append(
            {
                "order": i,
                "section": section,
                "title": w.title,
                "subtitle": w.subtitle,
                "slug": w.slug,
                "source_title": w.source_title,
                "source_url": w.source_url,
                "source_revision": w.source_revision,
                "year": w.year,
                "date": w.date,
                "cycle": w.cycle,
                "override": w.override,
                "lines": len(w.lines()),
            }
        )
    manifest = {
        "book": selection.book.model_dump(),
        "sections": [s.title for s in selection.sections],
        "works": entries,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(manifest, ensure_ascii=False, indent=1), encoding="utf-8")
