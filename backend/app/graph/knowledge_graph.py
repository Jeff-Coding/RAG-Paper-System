"""Minimal knowledge-graph representation derived from paper metadata."""
from __future__ import annotations

import json
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Dict, Iterable, List, Mapping, MutableMapping, Optional, Sequence

from app.config import GRAPH_PATH
from app.utils import extract_keywords, md5


@dataclass
class GraphNode:
    id: str
    type: str
    label: str
    attributes: Dict[str, object]


@dataclass
class GraphEdge:
    source: str
    target: str
    type: str
    weight: float = 1.0


class KnowledgeGraph:
    """Lightweight in-memory graph composed of nodes + edges."""

    def __init__(self, *, search_terms: Optional[Sequence[str]] = None):
        self.nodes: Dict[str, GraphNode] = {}
        self.edges: List[GraphEdge] = []
        self._search_terms = list(search_terms or [])

    # -- mutation helpers -------------------------------------------------
    def add_node(self, node: GraphNode):
        self.nodes[node.id] = node

    def add_edge(self, edge: GraphEdge):
        if edge.source in self.nodes and edge.target in self.nodes:
            self.edges.append(edge)

    # -- serialization ----------------------------------------------------
    def to_dict(self) -> Dict[str, object]:
        return {
            "meta": {"search_terms": self._search_terms},
            "nodes": [asdict(node) for node in self.nodes.values()],
            "edges": [asdict(edge) for edge in self.edges],
        }

    def dump(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")

    # -- convenience ------------------------------------------------------
    def __len__(self) -> int:
        return len(self.nodes)


class KnowledgeGraphBuilder:
    """Create a :class:`KnowledgeGraph` from crawler metadata rows."""

    def __init__(self, *, search_terms: Optional[Sequence[str]] = None):
        self.search_terms = list(search_terms or [])

    def build(self, rows: Iterable[Mapping[str, object]]) -> KnowledgeGraph:
        graph = KnowledgeGraph(search_terms=self.search_terms)
        for row in rows:
            self._add_paper(graph, row)
        return graph

    # ------------------------------------------------------------------
    def _add_paper(self, graph: KnowledgeGraph, row: Mapping[str, object]):
        title = str(row.get("title") or "").strip()
        if not title:
            return
        pid = md5(f"paper::{title}")
        abstract = str(row.get("abstract") or "").strip()
        authors = [a.strip() for a in row.get("authors", []) if isinstance(a, str) and a.strip()]
        venue = str(row.get("venue") or "").strip() or None
        doi = str(row.get("doi") or "").strip() or None
        year = row.get("year")
        keywords = row.get("keywords") or extract_keywords(f"{title} {abstract}", boost=self.search_terms)
        paper_node = GraphNode(
            id=pid,
            type="paper",
            label=title,
            attributes={
                "abstract": abstract,
                "year": year,
                "venue": venue,
                "doi": doi,
                "keywords": keywords,
                "source": row.get("source"),
                "url_pdf": row.get("url_pdf"),
                "url_landing": row.get("url_landing"),
            },
        )
        graph.add_node(paper_node)

        for author in authors:
            aid = md5(f"author::{author}")
            graph.add_node(
                GraphNode(
                    id=aid,
                    type="author",
                    label=author,
                    attributes={"name": author},
                )
            )
            graph.add_edge(GraphEdge(source=pid, target=aid, type="AUTHORED_BY"))

        if venue:
            vid = md5(f"venue::{venue}")
            graph.add_node(
                GraphNode(
                    id=vid,
                    type="venue",
                    label=venue,
                    attributes={"name": venue},
                )
            )
            graph.add_edge(GraphEdge(source=pid, target=vid, type="PUBLISHED_AT"))

        if isinstance(keywords, Iterable) and not isinstance(keywords, (str, bytes)):
            for kw in keywords:
                kw = str(kw).strip()
                if not kw:
                    continue
                kid = md5(f"keyword::{kw}")
                graph.add_node(
                    GraphNode(
                        id=kid,
                        type="keyword",
                        label=kw,
                        attributes={"keyword": kw},
                    )
                )
                graph.add_edge(GraphEdge(source=pid, target=kid, type="DESCRIBED_AS"))

        if year:
            yid = md5(f"year::{year}")
            graph.add_node(
                GraphNode(
                    id=yid,
                    type="year",
                    label=str(year),
                    attributes={"value": year},
                )
            )
            graph.add_edge(GraphEdge(source=pid, target=yid, type="PUBLISHED_IN"))


def build_graph_from_metadata(
    meta_path: Path | str,
    *,
    graph_path: Path | str | None = None,
    search_terms: Optional[Sequence[str]] = None,
) -> Dict[str, object]:
    """Build and persist a knowledge graph derived from crawler metadata."""

    meta_path = Path(meta_path)
    graph_path = Path(graph_path) if graph_path else GRAPH_PATH
    if not meta_path.exists():
        return {"graph_path": str(graph_path), "nodes": 0, "edges": 0}

    rows: List[MutableMapping[str, object]] = []
    with meta_path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue

    builder = KnowledgeGraphBuilder(search_terms=search_terms)
    graph = builder.build(rows)
    graph.dump(graph_path)
    return {
        "graph_path": str(graph_path),
        "nodes": len(graph.nodes),
        "edges": len(graph.edges),
        "search_terms": list(search_terms or []),
    }
