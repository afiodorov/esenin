"""Structural EPUB validation without external tools (epubcheck is optional)."""

from __future__ import annotations

import posixpath
import re
import shutil
import subprocess
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

NS = {
    "opf": "http://www.idpf.org/2007/opf",
    "dc": "http://purl.org/dc/elements/1.1/",
    "c": "urn:oasis:names:tc:opendocument:xmlns:container",
    "x": "http://www.w3.org/1999/xhtml",
    "epub": "http://www.idpf.org/2007/ops",
}
_ASCII_PATH = re.compile(r"^[A-Za-z0-9_./-]+$")
JUNK_PATTERNS = ["Править", "Источник:", "Категория:", "Викитека", "Дата создания", "См. также", "Комментарий", "mw-", "NewPP"]


def validate_epub(path: Path) -> list[str]:
    """Return a list of problems; empty means structurally OK."""
    problems: list[str] = []
    if not path.exists():
        return [f"missing file: {path}"]
    with zipfile.ZipFile(path) as z:
        names = z.namelist()
        if not names or names[0] != "mimetype":
            problems.append("first zip member must be 'mimetype'")
        else:
            info = z.getinfo("mimetype")
            if info.compress_type != zipfile.ZIP_STORED:
                problems.append("mimetype must be stored uncompressed")
            if z.read("mimetype") != b"application/epub+zip":
                problems.append("mimetype content wrong")
        for n in names:
            if not _ASCII_PATH.match(n):
                problems.append(f"non-ASCII or space in internal path: {n!r}")
        if "META-INF/container.xml" not in names:
            problems.append("META-INF/container.xml missing")
            return problems
        container = ET.fromstring(z.read("META-INF/container.xml"))
        rootfile = container.find(".//c:rootfile", NS)
        opf_path = rootfile.get("full-path") if rootfile is not None else None
        if not opf_path or opf_path not in names:
            problems.append(f"OPF missing: {opf_path}")
            return problems
        opf = ET.fromstring(z.read(opf_path))
        opf_dir = posixpath.dirname(opf_path)
        lang = opf.findtext("opf:metadata/dc:language", namespaces=NS)
        if lang != "ru":
            problems.append(f"dc:language is {lang!r}, expected 'ru'")
        if not opf.findtext("opf:metadata/dc:title", namespaces=NS):
            problems.append("dc:title missing")
        if not opf.findtext("opf:metadata/dc:identifier", namespaces=NS):
            problems.append("dc:identifier missing")
        manifest = {it.get("id"): it for it in opf.findall("opf:manifest/opf:item", NS)}
        nav_items = [it for it in manifest.values() if "nav" in (it.get("properties") or "").split()]
        if len(nav_items) != 1:
            problems.append("exactly one manifest item with properties='nav' required")
        for it in manifest.values():
            full = posixpath.normpath(posixpath.join(opf_dir, it.get("href")))
            if full not in names:
                problems.append(f"manifest href not in zip: {it.get('href')}")
        spine = [ref.get("idref") for ref in opf.findall("opf:spine/opf:itemref", NS)]
        if not spine:
            problems.append("empty spine")
        for idref in spine:
            if idref not in manifest:
                problems.append(f"spine idref not in manifest: {idref}")
        # XHTML well-formedness, link resolution, junk detection
        for it in manifest.values():
            if it.get("media-type") != "application/xhtml+xml":
                continue
            full = posixpath.normpath(posixpath.join(opf_dir, it.get("href")))
            if full not in names:
                continue
            data = z.read(full)
            try:
                doc = ET.fromstring(data)
            except ET.ParseError as e:
                problems.append(f"{full}: not well-formed XML: {e}")
                continue
            base = posixpath.dirname(full)
            for a in doc.iter("{http://www.w3.org/1999/xhtml}a"):
                href = a.get("href") or ""
                if href.startswith(("http:", "https:", "mailto:")):
                    problems.append(f"{full}: external link in book: {href}")
                    continue
                target = posixpath.normpath(posixpath.join(base, href.split("#")[0])) if href else None
                if target and target not in names:
                    problems.append(f"{full}: broken link {href}")
            for tag in ("link", "img"):
                for el in doc.iter("{http://www.w3.org/1999/xhtml}" + tag):
                    ref = el.get("href") or el.get("src") or ""
                    target = posixpath.normpath(posixpath.join(base, ref))
                    if target not in names:
                        problems.append(f"{full}: unresolved {tag} {ref}")
            text = "".join(doc.itertext())
            for junk in JUNK_PATTERNS:
                if junk in text and "colophon" not in full:
                    problems.append(f"{full}: source junk leaked: {junk!r}")
        if nav_items:
            nav_full = posixpath.normpath(posixpath.join(opf_dir, nav_items[0].get("href")))
            nav = ET.fromstring(z.read(nav_full))
            tocs = [n for n in nav.iter("{http://www.w3.org/1999/xhtml}nav") if n.get("{http://www.idpf.org/2007/ops}type") == "toc"]
            if not tocs:
                problems.append("nav document has no <nav epub:type='toc'>")
    return problems


def run_epubcheck(path: Path) -> tuple[bool | None, str]:
    """(passed, output). passed=None when epubcheck is not installed."""
    exe = shutil.which("epubcheck")
    if not exe:
        return None, "epubcheck not installed"
    proc = subprocess.run([exe, str(path)], capture_output=True, text=True)
    return proc.returncode == 0, (proc.stdout + proc.stderr).strip()
