"""Hybrid retrieval: combine KG cues + RAG chunks."""
from __future__ import annotations

from typing import Dict, List

from app.tools.kg import run_kg_query
from app.tools.rag import RagResult, run_rag_query


def _augment_query(question: str, graph_facts: List[Dict[str, object]], *, max_items: int = 5) -> str:
    if not graph_facts:
        return question
    labels = [fact.get("label", "") for fact in graph_facts if fact.get("label")]
    edges = []
    for fact in graph_facts:
        for edge in fact.get("edges", []) or []:
            tgt = edge.get("target")
            if tgt:
                edges.append(tgt)
    extra = labels[:max_items] + edges[:max_items]
    extras = " ".join(extra)
    return f"{question} {extras}".strip()


def run_hybrid_query(question: str, *, topk: int = 8):
    kg = run_kg_query(question, limit=topk)
    augmented_query = _augment_query(question, kg.get("facts", []))
    rag: RagResult = run_rag_query(augmented_query, topk=topk)
    return {"kg": kg, "rag": rag}

