# Handoff: Build a curated Sergei Yesenin poetry + fairy-tale EPUB for Kobo

## 0. Mission

Build a small, reproducible Python project that creates a **clean, reflowable EPUB3 for Kobo** containing a curated selection of Sergei Yesenin's works.

The reader preference is very specific:

- prioritize **love, women, relationships, longing, separation, loneliness, confession, tavern/city life, mortality**
- include the strongest introspective/life poems even when they are not strictly love poems
- **minimize nature-only / landscape-only poetry**
- include Yesenin's **fairy-tale / narrative verse**, especially the story remembered as "the evil stepmother and Masha"
- **no biography, criticism, introductions, academic commentary, source footnotes, or editorial essays** in the reading flow
- this is a book to *read as poetry*, not a scholarly edition

The Masha work has been identified and is mandatory:

> **«Сиротка (Русская сказка)»**  
> Begins: «Маша — круглая сиротка. / Плохо, плохо Маше жить, / Злая мачеха сердито...»

Also mandatory:

> **«Сказка о пастушонке Пете, его комиссарстве и коровьем царстве»**

The final artifact should feel like a deliberately edited personal collection, not a scraped website dump.

---

## 1. Deliverables

Primary output:

```text
dist/esenin-love-and-tales.epub
```

Optional secondary output if it can be produced cleanly without introducing a non-Python hard dependency:

```text
dist/esenin-love-and-tales.kepub.epub
```

A standard EPUB3 is the required artifact. Do **not** block the project on KEPUB conversion; Kobo supports standard EPUB.

Also produce:

```text
dist/manifest.json
```

The manifest should contain the exact ordered list of included works, canonical title, section, source URL, source revision ID if available, and any known year/cycle.

Project should be runnable with:

```bash
uv sync
uv run python -m esenin_epub build
```

Prefer also exposing:

```bash
uv run esenin-epub build
uv run esenin-epub fetch
uv run esenin-epub inspect
```

---

## 2. Tech constraints

Use:

- Python 3.12+
- `uv` for dependency/project management
- `pyproject.toml`
- UTF-8 everywhere
- tests with `pytest`

Suggested libraries:

- `httpx` — fetching
- `beautifulsoup4` and/or `lxml` — sanitizing parsed MediaWiki HTML
- `pydantic` — content metadata/schema if useful
- `PyYAML` — curated selection file
- `typer` — CLI
- `ebooklib` **or** a small internal EPUB writer using `zipfile`

Either EPUB approach is acceptable. Prefer correctness and transparent output over cleverness.

Avoid requiring:

- Pandoc
- Calibre
- Node
- Docker
- a browser
- a database

Optional validation with external `epubcheck` is welcome if present on the machine, but the build must work without it.

---

## 3. Repository shape

Suggested structure:

```text
.
├── pyproject.toml
├── README.md
├── content/
│   ├── selection.yaml
│   └── overrides/
│       └── README.md
├── src/
│   └── esenin_epub/
│       ├── __init__.py
│       ├── __main__.py
│       ├── cli.py
│       ├── models.py
│       ├── sources/
│       │   ├── __init__.py
│       │   └── wikisource.py
│       ├── normalize.py
│       ├── curate.py
│       ├── epub.py
│       └── validate.py
├── cache/
│   └── .gitkeep
├── dist/
│   └── .gitkeep
└── tests/
    ├── test_normalize.py
    ├── test_selection.py
    └── test_epub.py
```

`cache/` and `dist/` can be gitignored.

---

## 4. Content source strategy

### Primary source: Russian Wikisource

Use Russian Wikisource as the primary acquisition source because:

- texts are public-domain works
- there are stable work pages
- MediaWiki exposes machine-readable APIs
- revision IDs can be stored for reproducibility

Main author page:

```text
https://ru.wikisource.org/wiki/Автор:Сергей_Александрович_Есенин
```

Relevant mandatory pages:

```text
https://ru.wikisource.org/wiki/Сиротка_(Есенин)

https://ru.wikisource.org/wiki/Сказка_о_пастушонке_Пете,_его_комиссарстве_и_коровьем_царстве_(Есенин)/Версия_2
```

Use the MediaWiki API rather than scraping rendered site chrome when practical.

Suggested API direction:

```text
https://ru.wikisource.org/w/api.php
```

Possible approach:

```text
action=parse
page=<title>
prop=text|displaytitle|revid
format=json
formatversion=2
```

Pin/store the `revid` in the cache/manifest when available.

### Secondary verification source

When a Wikisource transcription looks suspicious, compare against the Fundamental Digital Library / FEB edition of Yesenin's complete works.

For «Сиротка»:

```text
https://feb-web.ru/feb/esenin/texts/e74/e74-075-.htm
```

Do not automatically mix punctuation from multiple editions. Pick a primary text and only create a local override when there is an obvious transcription defect.

### Source policy

The book must contain the **poem/story text only**.

Strip:

- site navigation
- Wikisource headers
- publication metadata rendered outside the work
- categories
- "Источник"
- edit links
- notes/commentary unless they are literally part of Yesenin's text
- bibliography
- academic apparatus
- page numbers from print editions

Keep:

- title
- subtitle if authored (e.g. «Русская сказка»)
- epigraph if genuinely part of the work
- stanza/line structure
- authorial section breaks (`*`, `***`, etc.)
- authored date/location only if it is customarily printed as part of the poem; otherwise metadata is enough

---

## 5. Curation philosophy

This is **not** "Complete Yesenin."

The desired reading experience is approximately:

1. love / erotic / relationship poetry
2. separation, regret, loneliness
3. personal / confessional / mortality poems
4. tavern / hooligan / urban emotional material
5. fairy-tale and strongly narrative verse
6. only a small amount of nature poetry where it overlaps strongly with the above

Do not optimize for historical representativeness.

Optimize for: **"I enjoy Yesenin when he is talking about people and his inner life more than when he is describing birches."**

---

## 6. Initial book structure

Use this as the initial editorial plan. Keep the list in `content/selection.yaml` so it can be edited without changing code.

### Part I — Любовь хулигана

Include the complete authorial cycle even though the reader has already read it. It belongs in the permanent collection.

Mandatory cycle:

- «Заметался пожар голубой…»
- «Ты такая ж простая, как все…»
- «Пускай ты выпита другим…»
- «Дорогая, сядем рядом…»
- «Мне грустно на тебя смотреть…»
- «Ты прохладой меня не мучай…»
- «Вечер чёрные брови насопил…»

Preserve cycle order.

### Part II — Персидские мотивы

Include the **complete cycle**, preserving established cycle order.

Do not cherry-pick only the famous poems. This cycle is sufficiently close to the target taste that it should remain intact.

### Part III — Любовь, женщины, расставания

Seed list to verify and include:

- «Письмо к женщине»
- «Ну, целуй меня, целуй…»
- «Ты меня не любишь, не жалеешь…»
- «Я помню, любимая, помню…»
- «Не криви улыбку, руки теребя…»
- «Не бродить, не мять в кустах багряных…»
- «Видно, так заведено навеки…»
- «Какая ночь! Я не могу…»
- «Голубая кофта. Синие глаза…»
- «Сукин сын»

Agent task:

1. verify canonical titles / first-line titles
2. verify source pages
3. remove duplicates with cycles
4. add additional strong relationship poems found during discovery
5. target roughly **15–30 works** in this part

### Part IV — Кабак, одиночество, исповедь

Seed list:

- «Мне осталась одна забава…»
- «Не жалею, не зову, не плачу…»
- «Несказанное, синее, нежное…»
- «Мы теперь уходим понемногу…»
- «До свиданья, друг мой, до свиданья»
- «Черный человек» — include as a separate longer work unless there is a compelling technical reason not to
- selected pieces from «Москва кабацкая» not already duplicated elsewhere

Target mood: inward-looking, personal, dark, adult Yesenin.

Avoid padding this section with poems that are primarily political or scenic.

### Part V — Сказки и повествовательные вещи

Mandatory:

1. **«Сиротка (Русская сказка)»**
2. **«Сказка о пастушонке Пете, его комиссарстве и коровьем царстве»**

Also discover works by Yesenin explicitly labelled:

- `сказка`
- `русская сказка`
- `сказание`

Candidate:

- «Сказание о Евпатии Коловрате…»

For additional narrative works, use editorial judgment. Prefer relatively self-contained pieces that are pleasant to read in a mixed poetry collection.

Do **not** silently add every long poem merely because it has a plot.

Keep large dramatic works such as `Пугачёв` or `Страна негодяев` out of the first edition unless explicitly requested later.

### Part VI — Несколько вещей просто потому, что они великие

Allow a short "best of" appendix for poems that are not quite on-theme but are too strong to omit.

Keep this small: ideally **5–10 poems maximum**.

Nature-only pieces should generally land here or be excluded.

---

## 7. Discovery step

Before finalizing `selection.yaml`, programmatically enumerate or inspect Yesenin's Wikisource corpus.

The agent should produce an intermediate report:

```text
dist/discovery.md
```

with:

- candidate title
- year if known
- source URL
- likely category:
  - love
  - relationship
  - confessional
  - tavern/hooligan
  - mortality
  - fairy-tale/narrative
  - nature
  - politics/revolution
  - religion
  - other
- include / maybe / exclude
- one-sentence reason

This can use an LLM only if one is readily available in the coding environment, but **must not require an LLM**.

A simple keyword/title/manual curation workflow is enough.

The final selection should remain explicit and human-readable in YAML.

---

## 8. Suggested `selection.yaml`

Design something like:

```yaml
book:
  title: "Сергей Есенин — Любовь, исповедь и сказки"
  author: "Сергей Есенин"
  language: "ru"
  description: "Личная подборка стихотворений и стихотворных сказок Сергея Есенина."

sections:
  - title: "Любовь хулигана"
    works:
      - source_title: "Заметался пожар голубой (Есенин)"
      - source_title: "Ты такая ж простая, как все (Есенин)"

  - title: "Персидские мотивы"
    works:
      - source_title: "..."

  - title: "Любовь, женщины, расставания"
    works:
      - source_title: "Письмо к женщине (Есенин)"
      - source_title: "..."

  - title: "Сказки"
    works:
      - source_title: "Сиротка (Есенин)"
        display_subtitle: "Русская сказка"
      - source_title: "Сказка о пастушонке Пете, его комиссарстве и коровьем царстве (Есенин)/Версия 2"
```

If Wikisource canonical page names differ, use the actual canonical API titles.

Allow optional fields:

```yaml
display_title:
display_subtitle:
year:
source_url:
source_revision:
notes:
```

`notes` are build/editor notes and should **not** be printed into the EPUB.

---

## 9. Text normalization

Poetry formatting is a first-class requirement.

The normalization pipeline must preserve:

- every poetic line break
- blank lines between stanzas
- section separators
- punctuation
- em dashes
- Russian quotation marks where present
- `ё` exactly as supplied by the chosen edition; do not globally convert `е ↔ ё`

Normalize:

- CRLF → LF
- non-breaking spaces where they are accidental
- repeated blank lines
- stray page numbers
- HTML presentation artifacts
- invisible edit anchors

Do not "correct" Yesenin's spelling or punctuation algorithmically.

### Internal representation

Prefer a structured model rather than storing one giant HTML blob:

```python
class Work:
    title: str
    subtitle: str | None
    source_title: str
    source_url: str
    source_revision: int | None
    year: int | None
    blocks: list[Block]
```

Possible block types:

```python
Stanza(lines=list[str])
Separator(text="*")
Paragraph(text=str)
```

This makes EPUB rendering deterministic and testable.

---

## 10. Kobo / EPUB requirements

Target: **reflowable EPUB3**, optimized for a Kobo eInk reader.

Kobo documentation notes that it supports EPUB2/EPUB3 and recommends a proper EPUB3 `nav` table of contents. It also warns that CSS page-break behavior varies across Kobo platforms; a new XHTML/HTML file is the most reliable page break.

Therefore:

### One work = one XHTML spine item

Every poem or story should be rendered into its **own XHTML file**.

Example:

```text
OEBPS/text/001-zametalsya-pozhar-goluboy.xhtml
OEBPS/text/002-ty-takaya-zh-prostaya.xhtml
...
```

This guarantees a fresh page for every work on Kobo much more reliably than CSS-only page breaks.

Use ASCII-safe internal filenames. Do not use spaces or Cyrillic in EPUB internal paths.

### Table of contents

EPUB3 navigation is mandatory:

```html
<nav epub:type="toc">
```

Hierarchy:

```text
Part
  Poem
  Poem
Part
  Poem
```

Also include a visible contents page if easy, but the device navigation TOC is the important one.

### Typography

Do not fight the Kobo user's reader settings.

Do **not** set:

- body font-family
- background color
- fixed body font size
- forced text color
- justification

Recommended poem rendering:

```html
<section class="poem">
  <h1>Ты меня не любишь, не жалеешь…</h1>

  <div class="stanza">
    <p class="line">...</p>
    <p class="line">...</p>
  </div>

  <div class="stanza">
    ...
  </div>
</section>
```

Suggested CSS:

```css
body {
  margin: 0;
  padding: 0;
}

section.poem {
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

div.stanza {
  margin: 0 0 1em 0;
}

p.line {
  margin: 0;
  padding-left: 1.2em;
  text-indent: -1.2em;
  text-align: left;
}

div.separator {
  margin: 1.25em 0;
  text-align: center;
}
```

The hanging indent on wrapped poetic lines is intentional: if a long verse line wraps on the Kobo screen, continuation lines should be visually distinguishable from new verse lines.

Test that this does not look excessive on a typical 6–7" eInk display.

### CSS implementation details

- use a linked stylesheet, not inline styles
- avoid background colors
- avoid overly specific layout dimensions
- avoid `%` as a base font size
- use semantic HTML
- let Kobo control font family and base size

Kobo reference:

```text
https://github.com/epubknowledge/kobo-epub-spec
https://kobowritinglife.zendesk.com/hc/en-us/articles/360059385611-EPUB-Best-Practices
```

---

## 11. EPUB metadata

At minimum:

```text
dc:title       Сергей Есенин — Любовь, исповедь и сказки
dc:creator     Сергей Александрович Есенин
dc:language    ru
dc:identifier  stable project UUID/URN
```

Set a modified timestamp during build.

Do not falsely claim a publisher.

Optional:

```text
dc:description Личная тематическая подборка произведений Сергея Есенина.
```

For personal use, do not clutter the book with legal boilerplate.

A minimal colophon at the end is acceptable:

```text
Тексты: общественное достояние.
Основной электронный источник: Викитека.
Сборка EPUB: персональная подборка.
```

No biography.

---

## 12. Cover

Create a very simple typographic cover as SVG or generated PNG.

Text only is sufficient:

```text
СЕРГЕЙ ЕСЕНИН

Любовь,
исповедь
и сказки
```

No need to hunt for a portrait.

Prefer a restrained monochrome/eInk-friendly design.

If generating a raster cover in Python, use Pillow.

The project must still build if cover generation is disabled.

---

## 13. Fetch/cache/reproducibility

Fetching should be deterministic enough that a build does not hammer Wikisource.

Implement:

```text
uv run esenin-epub fetch
```

It should:

1. read `selection.yaml`
2. fetch each source page
3. store raw source response in `cache/raw/`
4. store parsed normalized work in `cache/normalized/`
5. record source revision IDs
6. avoid re-fetching unchanged pinned revisions unless `--refresh`

Then:

```text
uv run esenin-epub build
```

should be able to build from cache.

Useful flags:

```text
--refresh
--offline
--output PATH
--no-cover
```

If a page fails to parse, fail loudly with the title and URL rather than silently omitting it.

---

## 14. Local overrides

Sometimes public-domain transcriptions contain markup or transcription oddities.

Support optional local overrides:

```text
content/overrides/<slug>.txt
```

or:

```text
content/overrides/<slug>.yaml
```

If an override exists, it should replace only the normalized text while preserving source metadata.

Every override should be visible in `manifest.json`:

```json
{
  "override": true
}
```

Do not silently patch source text in code.

---

## 15. Validation / tests

### Structural tests

At minimum:

- EPUB ZIP exists
- first ZIP member is `mimetype`
- `mimetype` is stored uncompressed
- correct value: `application/epub+zip`
- `META-INF/container.xml` exists
- OPF exists
- EPUB3 nav exists
- every spine item exists in manifest
- every selection entry appears exactly once in the spine
- all XHTML parses as XML
- all internal links resolve
- no Cyrillic/spaces in internal EPUB filenames
- book language is `ru`

### Poetry integrity tests

For a few fixtures including `Сиротка`:

- first line survives
- known stanza breaks survive
- line count is plausible / stable
- source-navigation text does not leak into output
- no `Править`, `Источник`, `Категория`, page numbers, etc.

For `Сиротка`, assert normalized text contains:

```text
Маша — круглая сиротка.
```

and:

```text
Злая мачеха
```

Do not assert large copyrighted-like excerpts from modern editions; the source work itself is public domain, but keep tests concise anyway.

### EPUB validation

If `epubcheck` is installed:

```bash
epubcheck dist/esenin-love-and-tales.epub
```

should return zero errors.

Make this optional in the automated test suite.

---

## 16. Quality check on Kobo

The EPUB should be manually sideloadable to Kobo.

Acceptance checklist:

- book opens normally
- Cyrillic renders correctly
- cover appears
- title/author metadata appears
- Kobo TOC shows parts and works
- selecting a poem from TOC goes directly to it
- every poem starts on a fresh page
- stanza breaks are obvious
- poetic line breaks are preserved
- wrapped long lines use hanging indent
- changing Kobo font face still works
- changing Kobo font size still works
- changing line spacing/margins still works reasonably
- dark/background modes are not broken by CSS
- no website junk appears
- no biography/commentary appears

If available, test on the actual Kobo rather than treating a desktop EPUB viewer as authoritative.

---

## 17. Editorial acceptance criteria

The first edition should probably contain roughly **50–80 works**, but quality beats count.

Before final output:

- remove exact duplicates
- avoid duplicated poems that occur both inside a cycle and another section
- preserve authorial cycle order
- do not alphabetize poetry
- sequence sections for emotional reading flow
- avoid 20 nature poems in a row
- do not insert generated explanations between works

The book should read like an anthology assembled by a person with a taste preference.

---

## 18. Nice-to-have CLI

Examples:

```bash
# fetch/update texts
uv run esenin-epub fetch

# show curated list
uv run esenin-epub list

# render one normalized work to stdout
uv run esenin-epub show "Сиротка"

# build book
uv run esenin-epub build

# build without network
uv run esenin-epub build --offline

# basic internal validation
uv run esenin-epub validate dist/esenin-love-and-tales.epub
```

---

## 19. README instructions

README should be short and practical.

Expected quick start:

```bash
git clone ...
cd ...
uv sync
uv run esenin-epub fetch
uv run esenin-epub build
open dist/
```

Also document sideloading at a high level:

1. connect Kobo by USB
2. copy `.epub` into the mounted Kobo storage
3. eject cleanly
4. Kobo imports the book

Do not make Kobo Desktop or Adobe Digital Editions a requirement for this DRM-free personal EPUB.

---

## 20. Implementation order

Recommended coding-agent sequence:

### Phase A — Skeleton

1. `uv init`
2. add dependencies
3. CLI skeleton
4. selection schema
5. tests

### Phase B — Source acquisition

1. MediaWiki API client
2. caching
3. revision metadata
4. parser for one simple poem
5. parser fixture for `Сиротка`

### Phase C — Normalization

1. stanza/line model
2. strip site markup
3. section separators
4. source overrides
5. regression tests

### Phase D — Curation

1. populate mandatory cycles
2. populate love/relationship seed list
3. discover candidate works
4. add fairy tales
5. output `dist/discovery.md`
6. finalize `content/selection.yaml`

### Phase E — EPUB

1. EPUB3 package
2. one XHTML per work
3. linked stylesheet
4. nested nav TOC
5. metadata
6. optional cover
7. manifest

### Phase F — QA

1. run tests
2. inspect ZIP structure
3. run `epubcheck` if available
4. open in an EPUB reader
5. sideload to Kobo
6. fix Kobo-specific layout issues

---

## 21. Decisions the agent should make autonomously

Do not stop to ask for trivial preferences.

Use good defaults for:

- exact Python package choices
- cache format
- slug format
- UUID generation
- XML helper library
- cover dimensions
- exact number of anthology items within the 50–80 target
- which additional love/confessional poems deserve inclusion

Only preserve the core editorial preference:

> More love, people, loneliness, confession and narrative; less pure landscape/nature.

If uncertain whether a work fits, include it in `discovery.md` as `maybe` rather than bloating the first EPUB.

---

## 22. Definition of done

The task is done when:

```bash
uv sync
uv run esenin-epub fetch
uv run esenin-epub build
uv run pytest
```

succeeds from a clean checkout, and:

```text
dist/esenin-love-and-tales.epub
```

is a valid, navigable, pleasant-to-read Russian EPUB3 suitable for sideloading to Kobo, containing:

- complete `Любовь хулигана`
- complete `Персидские мотивы`
- a substantial curated love/relationship selection
- a smaller confessional/dark selection
- `Сиротка (Русская сказка)`
- `Сказка о пастушонке Пете, его комиссарстве и коровьем царстве`
- no biography or web/editorial clutter

The EPUB itself is the product. The scraper/build system exists only to make the book reproducible and easy to refine later.
