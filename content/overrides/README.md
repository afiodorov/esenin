# Local text overrides

Drop a file named `<slug>.txt` here to replace the *text* of a work while
keeping its Wikisource metadata (title, URL, revision). The slug is the one
shown by `uv run esenin-epub list`.

Format of `<slug>.txt`: plain UTF-8, one verse line per line, a blank line
between stanzas, a line containing only `*` (or `***`, `* * *`) for an
authorial section break, and a line of the form `# Heading` for a numbered
part heading. The first line may be `subtitle: ...` to set a subtitle.

Overrides are flagged with `"override": true` in `dist/manifest.json`.
Use them only for obvious transcription defects, never to "improve" Yesenin.
