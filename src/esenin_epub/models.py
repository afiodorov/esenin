"""Data model: a Work is a list of typed blocks, never one HTML blob."""

from __future__ import annotations

from typing import Annotated, Literal, Union

from pydantic import BaseModel, Field


class Line(BaseModel):
    text: str
    indent: int = 0


class Stanza(BaseModel):
    type: Literal["stanza"] = "stanza"
    lines: list[Line]


class Separator(BaseModel):
    type: Literal["separator"] = "separator"
    text: str = "*"


class Heading(BaseModel):
    type: Literal["heading"] = "heading"
    text: str


class Paragraph(BaseModel):
    type: Literal["paragraph"] = "paragraph"
    text: str


Block = Annotated[Union[Stanza, Separator, Heading, Paragraph], Field(discriminator="type")]


class Work(BaseModel):
    slug: str
    title: str
    subtitle: str | None = None
    source_title: str
    source_url: str
    source_revision: int | None = None
    year: int | None = None
    date: str | None = None
    cycle: str | None = None
    override: bool = False
    blocks: list[Block]

    def lines(self) -> list[str]:
        out: list[str] = []
        for b in self.blocks:
            if isinstance(b, Stanza):
                out.extend(ln.text for ln in b.lines)
        return out

    def plain_text(self) -> str:
        parts: list[str] = []
        for b in self.blocks:
            if isinstance(b, Stanza):
                parts.append("\n".join(("  " * ln.indent) + ln.text for ln in b.lines))
            elif isinstance(b, Separator):
                parts.append(b.text)
            elif isinstance(b, Heading):
                parts.append(f"# {b.text}")
            else:
                parts.append(b.text)
        return "\n\n".join(parts) + "\n"


class WorkSpec(BaseModel):
    """One entry of selection.yaml."""

    source_title: str
    display_title: str | None = None
    display_subtitle: str | None = None
    year: int | None = None
    cycle: str | None = None
    source_url: str | None = None
    source_revision: int | None = None
    notes: str | None = None


class SectionSpec(BaseModel):
    title: str
    works: list[WorkSpec]


class BookSpec(BaseModel):
    title: str
    author: str
    language: str = "ru"
    description: str | None = None
    identifier: str


class Selection(BaseModel):
    book: BookSpec
    sections: list[SectionSpec]

    def all_specs(self) -> list[tuple[SectionSpec, WorkSpec]]:
        return [(s, w) for s in self.sections for w in s.works]


class RawPage(BaseModel):
    """Raw MediaWiki parse response, cached verbatim-ish."""

    source_title: str
    canonical_title: str
    pageid: int | None = None
    revid: int | None = None
    html: str
    fetched_at: str
    api_url: str
