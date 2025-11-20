"""RAG retrieval tool wrapper."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Sequence, Tuple

from app.services import (
    build_context,
    build_numbered_context,
    format_reference_lines,
    search,
)


@dataclass
class RagResult:
    blocks: List[str]
    metas: List[Dict[str, object]]
    numbered_context: str
    reference_notes: List[Tuple[int, int | None, str, int]]


def run_rag_query(question: str, *, topk: int = 8) -> RagResult:
    hits = search(question, topk=topk)
    blocks, metas = build_context(hits)
    numbered, notes = build_numbered_context(blocks, metas)
    return RagResult(blocks=blocks, metas=metas, numbered_context=numbered, reference_notes=notes)


def format_references(notes: Sequence[Tuple[int, int | None, str, int]]) -> str:
    return "\n".join(format_reference_lines(notes))

