# esenin-epub

Builds a curated, reflowable EPUB3 of Sergei Yesenin for a Kobo: love poems,
confessional/tavern poems, and his verse fairy tales (including «Сиротка» —
the evil stepmother and Masha — and «Сказка о пастушонке Пете»). Texts come
from Russian Wikisource; the book contains poem text only, no biography or
commentary.

## Quick start

```bash
uv sync
uv run esenin-epub fetch     # download + normalize into cache/
uv run esenin-epub build     # -> dist/esenin-love-and-tales.epub (+ .kepub.epub, manifest.json)
uv run pytest
```

`python -m esenin_epub build` works too. Useful flags for `build`:
`--offline` (cache only), `--refresh` (re-download), `--output PATH`,
`--no-cover`, `--no-kepub`.

Other commands:

```bash
uv run esenin-epub list                 # curated list in book order
uv run esenin-epub show "Сиротка"       # print one normalized work
uv run esenin-epub validate dist/esenin-love-and-tales.epub
uv run esenin-epub inspect              # ZIP members
uv run esenin-epub discover             # corpus report -> dist/discovery.md
```

`epubcheck` is used automatically if it is on PATH; it is not required.

## Editing the book

- `content/selection.yaml` — the whole editorial plan: sections, works, order.
  Each work needs only `source_title` (the Wikisource page name); optional
  `display_title`, `display_subtitle`, `year`, `cycle`, `source_revision`
  (pin a revision), `notes` (never printed).
- `content/overrides/<slug>.txt` — replace the text of one work when the
  transcription is defective; flagged `"override": true` in the manifest.
- `content/discovery.yaml` — category/decision notes feeding `discover`.

Fetching is cached in `cache/raw/` (raw MediaWiki HTML + revision id) and
`cache/normalized/` (structured stanzas). A cached page is not re-fetched
unless `--refresh` is given or its pinned revision differs.

## Sideloading to a Kobo

1. Connect the Kobo by USB and confirm the connection on the device.
2. Copy `dist/esenin-love-and-tales.epub` (or the `.kepub.epub`) into the
   mounted storage.
3. Eject cleanly. The Kobo imports the book on disconnect.

No Kobo Desktop or Adobe Digital Editions is needed; the file is DRM-free.

## Layout choices

One XHTML file per work (reliable page breaks on Kobo), EPUB3 `nav` with
Part → Poem hierarchy plus an NCX for older firmware, a linked stylesheet
that sets no font family, size, colour or justification, and a hanging
indent on wrapped verse lines.
