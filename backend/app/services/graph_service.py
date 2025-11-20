"""Helpers for loading and querying the paper knowledge graph."""
from __future__ import annotations

import json
import threading
from pathlib import Path
from typing import Dict, List, Sequence

from app.config import GRAPH_PATH
from app.utils import tokenize_for_bm25

_LOCK = threading.Lock()
_GRAPH_INDEX: "GraphSearchIndex | None" = None


class GraphSearchIndex:
    def __init__(self, graph_data: Dict[str, object]):
        self.nodes = {node["id"]: node for node in graph_data.get("nodes", [])}
        adjacency: Dict[str, List[Dict[str, object]]] = {}
        for edge in graph_data.get("edges", []):
            adjacency.setdefault(edge.get("source"), []).append(edge)
        self.entries: List[Dict[str, object]] = []
        for node_id, node in self.nodes.items():
            attrs = node.get("attributes", {}) or {}
            parts: List[str] = [node.get("label", ""), attrs.get("abstract", "")]
            for value in attrs.values():
                if isinstance(value, str):
                    parts.append(value)
                elif isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
                    parts.extend([str(v) for v in value])
            for edge in adjacency.get(node_id, []):
                target = self.nodes.get(edge.get("target"))
                if target:
                    parts.append(target.get("label", ""))
            self.entries.append(
                {
                    "id": node_id,
                    "label": node.get("label", ""),
                    "type": node.get("type", ""),
                    "attrs": attrs,
                    "edges": adjacency.get(node_id, []),
                    "text": " ".join(parts).lower(),
                }
            )

    def search(self, query: str, limit: int = 5) -> List[Dict[str, object]]:
        tokens = [tok for tok in tokenize_for_bm25(query) if tok]
        if not tokens:
            return []
        scored = []
        for entry in self.entries:
            score = sum(entry["text"].count(tok) for tok in tokens)
            if score:
                scored.append((score, entry))
        scored.sort(key=lambda item: item[0], reverse=True)
        out = []
        for score, entry in scored[:limit]:
            facts = {
                "label": entry["label"],
                "type": entry["type"],
                "summary": _summarize(entry["attrs"]),
                "edges": _format_edges(entry["edges"], self.nodes),
                "score": score,
            }
            out.append(facts)
        return out


def _format_edges(edges: Sequence[Dict[str, object]], nodes: Dict[str, Dict[str, object]]):
    formatted = []
    for edge in edges[:4]:
        target = nodes.get(edge.get("target"))
        if not target:
            continue
        formatted.append({
            "type": edge.get("type", ""),
            "target": target.get("label", ""),
        })
    return formatted


def _summarize(attrs: Dict[str, object]) -> str:
    abstract = attrs.get("abstract")
    if isinstance(abstract, str) and abstract.strip():
        text = abstract.strip()
        return text[:240] + ("…" if len(text) > 240 else "")
    venue = attrs.get("venue")
    year = attrs.get("year")
    doi = attrs.get("doi")
    kw_attr = attrs.get("keywords")
    keywords = kw_attr if isinstance(kw_attr, Sequence) and not isinstance(kw_attr, (str, bytes)) else []
    parts: List[str] = []
    if venue:
        parts.append(f"Venue: {venue}")
    if year:
        parts.append(f"Year: {year}")
    if doi:
        parts.append(f"DOI: {doi}")
    if keywords:
        parts.append("Keywords: " + ", ".join([str(k) for k in keywords][:5]))
    return "; ".join(parts) if parts else ""


def _load_graph_index() -> GraphSearchIndex | None:
    path = Path(GRAPH_PATH)
    if not path.exists():
        return None
    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    return GraphSearchIndex(data)


def ensure_graph_index() -> GraphSearchIndex | None:
    global _GRAPH_INDEX
    with _LOCK:
        if _GRAPH_INDEX is None:
            _GRAPH_INDEX = _load_graph_index()
        return _GRAPH_INDEX


def reload_graph_index() -> GraphSearchIndex | None:
    global _GRAPH_INDEX
    with _LOCK:
        _GRAPH_INDEX = _load_graph_index()
        return _GRAPH_INDEX


def query_graph(query: str, limit: int = 5) -> List[Dict[str, object]]:
    index = ensure_graph_index()
    if not index:
        return []
    return index.search(query, limit=limit)


def format_graph_context(facts: Sequence[Dict[str, object]]) -> str:
    if not facts:
        return "（知识图谱暂无命中）"
    lines = []
    for fact in facts:
        edges = fact.get("edges", [])
        edge_txt = ", ".join(f"{edge['type']}→{edge['target']}" for edge in edges if edge.get("target"))
        summary = fact.get("summary") or ""
        lines.append(f"- {fact['label']}（{fact['type']}）: {summary}"
                     + (f" | 关联: {edge_txt}" if edge_txt else ""))
    return "\n".join(lines)
