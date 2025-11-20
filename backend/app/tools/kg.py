"""Knowledge-graph tool wrapper."""
from __future__ import annotations

from typing import Dict, List

from app.services import format_graph_context, query_graph


def run_kg_query(question: str, *, limit: int = 8) -> Dict[str, object]:
    hits = query_graph(question, limit=limit)
    return {
        "facts": hits,
        "context": format_graph_context(hits),
    }

