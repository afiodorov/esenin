"""esenin-epub command line."""

from __future__ import annotations

import sys
import zipfile
from pathlib import Path

import typer

from esenin_epub import curate
from esenin_epub.models import Selection
from esenin_epub.sources.wikisource import FetchError, WikisourceClient

app = typer.Typer(help="Build a curated Sergei Yesenin EPUB3 for Kobo.", no_args_is_help=True)

DEFAULT_OUTPUT = curate.DIST_DIR / "esenin-love-and-tales.epub"


def _selection(path: Path | None) -> Selection:
    try:
        return curate.load_selection(path or curate.SELECTION_PATH)
    except Exception as e:  # noqa: BLE001
        typer.secho(f"selection error: {e}", fg="red", err=True)
        raise typer.Exit(2)


def _collect(sel: Selection, offline: bool, refresh: bool):
    client = WikisourceClient(curate.CACHE_DIR, offline=offline)
    try:
        return curate.collect_works(sel, client, refresh=refresh, log=lambda s: typer.echo(s))
    except (FetchError, RuntimeError) as e:
        typer.secho(f"\nFAILED: {e}", fg="red", err=True)
        raise typer.Exit(1)


@app.command()
def fetch(
    refresh: bool = typer.Option(False, "--refresh", help="Re-download even if cached."),
    selection: Path | None = typer.Option(None, "--selection", help="Alternative selection.yaml."),
):
    """Fetch every selected work from Wikisource into cache/ and normalize it."""
    sel = _selection(selection)
    works = _collect(sel, offline=False, refresh=refresh)
    typer.echo(f"fetched {len(works)} works into {curate.CACHE_DIR}")


@app.command()
def build(
    output: Path = typer.Option(DEFAULT_OUTPUT, "--output", "-o", help="EPUB output path."),
    offline: bool = typer.Option(False, "--offline", help="Never touch the network; use cache only."),
    refresh: bool = typer.Option(False, "--refresh", help="Re-download sources before building."),
    no_cover: bool = typer.Option(False, "--no-cover", help="Skip cover generation."),
    kepub: bool = typer.Option(True, "--kepub/--no-kepub", help="Also write a .kepub.epub next to the EPUB."),
    selection: Path | None = typer.Option(None, "--selection", help="Alternative selection.yaml."),
):
    """Build dist/esenin-love-and-tales.epub (+ manifest.json)."""
    from esenin_epub.epub import assemble, write_epub
    from esenin_epub.validate import run_epubcheck, validate_epub

    sel = _selection(selection)
    works = _collect(sel, offline=offline, refresh=refresh)
    cover_png = None
    if not no_cover:
        from esenin_epub.cover import make_cover_png

        cover_png = make_cover_png()
        if cover_png is None:
            typer.secho("cover: Pillow or a TrueType font not available; building without cover", fg="yellow")
    files = assemble(sel.book, works, cover_png)
    write_epub(files, output)
    curate.write_manifest(sel, works, output.parent / "manifest.json")
    problems = validate_epub(output)
    if problems:
        typer.secho("structural validation FAILED:", fg="red", err=True)
        for p in problems:
            typer.echo(f"  - {p}", err=True)
        raise typer.Exit(1)
    typer.secho(f"wrote {output} ({output.stat().st_size // 1024} KiB, {len(works)} works) — structure OK", fg="green")
    if kepub:
        from esenin_epub.kepub import write_kepub

        kpath = output.with_name(output.name.replace(".epub", ".kepub.epub"))
        try:
            write_kepub(output, kpath)
            typer.echo(f"wrote {kpath}")
        except Exception as e:  # noqa: BLE001
            typer.secho(f"kepub conversion skipped: {e}", fg="yellow")
    ok, out = run_epubcheck(output)
    if ok is None:
        typer.echo("epubcheck not installed; skipped")
    elif ok:
        typer.secho("epubcheck: no errors", fg="green")
    else:
        typer.secho("epubcheck reported problems:", fg="red")
        typer.echo(out)


@app.command("list")
def list_cmd(selection: Path | None = typer.Option(None, "--selection")):
    """Show the curated list in book order."""
    sel = _selection(selection)
    n = 0
    for section in sel.sections:
        typer.echo(f"\n== {section.title}")
        for w in section.works:
            n += 1
            from esenin_epub.slug import slugify

            typer.echo(f"  {n:3d}. {w.display_title or w.source_title}  [{slugify(w.source_title)}]" + (f"  ({w.year})" if w.year else ""))
    typer.echo(f"\n{n} works in {len(sel.sections)} sections")


@app.command()
def show(
    query: str = typer.Argument(..., help="Part of a title or slug."),
    offline: bool = typer.Option(True, "--offline/--online"),
    selection: Path | None = typer.Option(None, "--selection"),
):
    """Print one normalized work to stdout."""
    sel = _selection(selection)
    q = query.lower()
    matches = [(s, w) for s, w in sel.all_specs() if q in w.source_title.lower() or q in (w.display_title or "").lower()]
    if not matches:
        typer.secho(f"no work matches {query!r}", fg="red", err=True)
        raise typer.Exit(1)
    if len(matches) > 1:
        typer.echo("several matches, showing the first: " + "; ".join(w.source_title for _, w in matches), err=True)
    section, spec = matches[0]
    client = WikisourceClient(curate.CACHE_DIR, offline=offline)
    try:
        work = curate.build_work(spec, client)
    except (FetchError, RuntimeError) as e:
        typer.secho(str(e), fg="red", err=True)
        raise typer.Exit(1)
    typer.echo(f"{work.title}" + (f"\n({work.subtitle})" if work.subtitle else ""))
    typer.echo(f"[{section.title}] {work.source_url} rev={work.source_revision} date={work.date} override={work.override}\n")
    typer.echo(work.plain_text())


@app.command()
def validate(path: Path = typer.Argument(DEFAULT_OUTPUT)):
    """Run structural checks (and epubcheck if installed) on an EPUB."""
    from esenin_epub.validate import run_epubcheck, validate_epub

    problems = validate_epub(path)
    for p in problems:
        typer.echo(f"  - {p}")
    ok, out = run_epubcheck(path)
    if ok is None:
        typer.echo("epubcheck not installed")
    else:
        typer.echo(out or "epubcheck: no output")
    if problems or ok is False:
        raise typer.Exit(1)
    typer.secho("OK", fg="green")


@app.command()
def inspect(path: Path = typer.Argument(DEFAULT_OUTPUT)):
    """List the ZIP members of an EPUB."""
    with zipfile.ZipFile(path) as z:
        for info in z.infolist():
            comp = "stored" if info.compress_type == zipfile.ZIP_STORED else "deflate"
            typer.echo(f"{info.file_size:8d}  {comp:7s}  {info.filename}")


@app.command()
def discover(
    refresh: bool = typer.Option(False, "--refresh"),
    offline: bool = typer.Option(False, "--offline"),
    output: Path = typer.Option(curate.DIST_DIR / "discovery.md", "--output", "-o"),
    selection: Path | None = typer.Option(None, "--selection"),
):
    """Enumerate the Wikisource corpus and write dist/discovery.md."""
    from esenin_epub.discover import discover as _discover
    from esenin_epub.discover import load_annotations, render_markdown

    sel = _selection(selection)
    client = WikisourceClient(curate.CACHE_DIR, offline=offline)
    ann = load_annotations(curate.CONTENT_DIR / "discovery.yaml")
    try:
        cands = _discover(client, sel, ann, refresh=refresh)
    except FetchError as e:
        typer.secho(str(e), fg="red", err=True)
        raise typer.Exit(1)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(render_markdown(cands), encoding="utf-8")
    inc = sum(c.decision == "include" for c in cands)
    maybe = sum(c.decision == "maybe" for c in cands)
    typer.echo(f"wrote {output}: {len(cands)} candidates, include={inc}, maybe={maybe}")


if __name__ == "__main__":
    app()
