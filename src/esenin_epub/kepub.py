"""Optional Kobo KEPUB flavour: wrap text runs in koboSpan spans (pure Python)."""

from __future__ import annotations

import copy
import re
import zipfile
from pathlib import Path

from lxml import etree

XHTML = "http://www.w3.org/1999/xhtml"
TEXT_TAGS = {"p", "h1", "h2", "h3", "h4", "h5", "h6", "div", "li", "td", "th", "blockquote", "figcaption", "span"}


def _kepubify_xhtml(data: bytes) -> bytes:
    parser = etree.XMLParser(remove_blank_text=False)
    root = etree.fromstring(data, parser)
    body = root.find(f"{{{XHTML}}}body")
    if body is None:
        return data
    para = 0
    for el in body.iter():
        if not isinstance(el.tag, str):
            continue
        tag = etree.QName(el).localname
        if tag not in TEXT_TAGS:
            continue
        if any(etree.QName(a).localname in TEXT_TAGS for a in el.iterancestors() if isinstance(a.tag, str) and etree.QName(a).localname in {"p", "h1", "h2", "h3", "h4", "h5", "h6", "li"}):
            continue
        if el.get("class") == "koboSpan":
            continue
        has_text = (el.text or "").strip() or any((c.tail or "").strip() for c in el)
        if not has_text and tag != "span":
            continue
        para += 1
        seg = 0
        if el.text and el.text.strip():
            seg += 1
            span = etree.SubElement(el, f"{{{XHTML}}}span")
            span.set("class", "koboSpan")
            span.set("id", f"kobo.{para}.{seg}")
            span.text = el.text
            el.text = None
            el.remove(span)
            el.insert(0, span)
        for child in list(el):
            if child.get("class") == "koboSpan":
                continue
            if child.tail and child.tail.strip():
                seg += 1
                span = etree.Element(f"{{{XHTML}}}span")
                span.set("class", "koboSpan")
                span.set("id", f"kobo.{para}.{seg}")
                span.text = child.tail
                child.tail = None
                child.addnext(span)
    # Kobo wrapper divs
    inner = etree.Element(f"{{{XHTML}}}div", id="book-inner")
    for child in list(body):
        inner.append(child)
    columns = etree.SubElement(body, f"{{{XHTML}}}div", id="book-columns")
    columns.append(inner)
    return etree.tostring(root, xml_declaration=True, encoding="utf-8", doctype="<!DOCTYPE html>")


def write_kepub(epub_path: Path, kepub_path: Path) -> None:
    with zipfile.ZipFile(epub_path) as src, zipfile.ZipFile(kepub_path, "w") as dst:
        for info in src.infolist():
            data = src.read(info.filename)
            if info.filename == "mimetype":
                dst.writestr(zipfile.ZipInfo("mimetype"), data, compress_type=zipfile.ZIP_STORED)
                continue
            if info.filename.endswith(".xhtml") and not info.filename.endswith("nav.xhtml"):
                data = _kepubify_xhtml(data)
            ni = zipfile.ZipInfo(info.filename, date_time=(1980, 1, 1, 0, 0, 0))
            ni.compress_type = zipfile.ZIP_DEFLATED
            dst.writestr(ni, data)
