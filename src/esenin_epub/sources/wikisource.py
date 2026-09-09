"""Russian Wikisource MediaWiki API client with an on-disk raw cache."""

from __future__ import annotations

import json
import urllib.parse
from datetime import datetime, timezone
from pathlib import Path

import httpx

from esenin_epub import __version__
from esenin_epub.models import RawPage
from esenin_epub.slug import slugify

API_URL = "https://ru.wikisource.org/w/api.php"
PAGE_URL = "https://ru.wikisource.org/wiki/"
USER_AGENT = f"esenin-epub/{__version__} (personal EPUB builder; https://github.com/afiodorov)"


class FetchError(RuntimeError):
    pass


def page_url(title: str, revid: int | None = None) -> str:
    if revid:
        return f"https://ru.wikisource.org/w/index.php?{urllib.parse.urlencode({'title': title, 'oldid': revid})}"
    return PAGE_URL + urllib.parse.quote(title.replace(" ", "_"), safe="()/:,!")


class WikisourceClient:
    def __init__(self, cache_dir: Path, offline: bool = False, timeout: float = 30.0):
        self.raw_dir = cache_dir / "raw"
        self.raw_dir.mkdir(parents=True, exist_ok=True)
        self.offline = offline
        self._http = httpx.Client(headers={"User-Agent": USER_AGENT}, timeout=timeout, follow_redirects=True)

    # -- cache -------------------------------------------------------------
    def cache_path(self, source_title: str) -> Path:
        return self.raw_dir / f"{slugify(source_title, 80)}.json"

    def load_cached(self, source_title: str) -> RawPage | None:
        p = self.cache_path(source_title)
        if not p.exists():
            return None
        return RawPage.model_validate_json(p.read_text(encoding="utf-8"))

    def _store(self, page: RawPage) -> None:
        self.cache_path(page.source_title).write_text(page.model_dump_json(indent=1), encoding="utf-8")

    # -- api ---------------------------------------------------------------
    def _api(self, params: dict) -> dict:
        params = {"format": "json", "formatversion": "2", **params}
        try:
            r = self._http.get(API_URL, params=params)
            r.raise_for_status()
            data = r.json()
        except httpx.HTTPError as e:
            raise FetchError(f"HTTP failure talking to {API_URL}: {e}") from e
        if "error" in data:
            raise FetchError(f"API error: {data['error'].get('code')}: {data['error'].get('info')}")
        return data

    def fetch_parse(self, source_title: str, revid: int | None = None, prop: str = "text|revid|displaytitle") -> dict:
        params = {"action": "parse", "prop": prop, "disabletoc": "1", "disableeditsection": "1"}
        if revid:
            params["oldid"] = str(revid)
        else:
            params["page"] = source_title
            params["redirects"] = "1"
        data = self._api(params)
        return data["parse"]

    def get_page(self, source_title: str, pinned_revision: int | None = None, refresh: bool = False) -> RawPage:
        """Return the raw page, using the cache unless refresh or the pin mismatches."""
        cached = self.load_cached(source_title)
        if cached and not refresh and (pinned_revision is None or cached.revid == pinned_revision):
            return cached
        if self.offline:
            if cached:
                return cached
            raise FetchError(f"offline and not cached: {source_title!r} ({page_url(source_title)})")
        try:
            parsed = self.fetch_parse(source_title, revid=pinned_revision)
        except FetchError as e:
            raise FetchError(f"{source_title!r} ({page_url(source_title)}): {e}") from e
        page = RawPage(
            source_title=source_title,
            canonical_title=parsed.get("title", source_title),
            pageid=parsed.get("pageid"),
            revid=parsed.get("revid"),
            html=parsed["text"],
            fetched_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
            api_url=API_URL,
        )
        self._store(page)
        return page

    def get_wikitext(self, source_title: str, refresh: bool = False) -> tuple[str, int | None]:
        """Wikitext of a page (used for index/discovery pages), cached separately."""
        p = self.raw_dir / f"wikitext-{slugify(source_title, 80)}.json"
        if p.exists() and not refresh:
            d = json.loads(p.read_text(encoding="utf-8"))
            return d["wikitext"], d.get("revid")
        if self.offline:
            raise FetchError(f"offline and not cached: {source_title!r}")
        parsed = self.fetch_parse(source_title, prop="wikitext|revid")
        p.write_text(json.dumps({"wikitext": parsed["wikitext"], "revid": parsed.get("revid")}, ensure_ascii=False), encoding="utf-8")
        return parsed["wikitext"], parsed.get("revid")
