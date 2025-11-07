"""Utilities for loading and querying the hybrid retriever."""
from __future__ import annotations

import os
import re
import threading
from typing import Iterable, List, Sequence, Tuple

import faiss

from app.config import (
    BM25_SERIALIZED,
    CHUNKS_PATH,
    DEFAULT_TOPK,
    DENSE_TOPK,
    FAISS_INDEX_PATH,
    FUSE_ALPHA,
    META_PATH,
    RERANK_CAND,
    SPARSE_TOPK,
)
from app.retriever import HybridRetriever
from app.utils import read_jsonl

MAX_CTX_CHARS = 12_000

_RETRIEVER: HybridRetriever | None = None
_LOAD_LOCK = threading.Lock()


def _load_state() -> HybridRetriever:
    if not os.path.exists(FAISS_INDEX_PATH):
        raise RuntimeError("FAISS index not found. 请先运行: python app/ingest.py")

    index = faiss.read_index(str(FAISS_INDEX_PATH))

    chunks_rows = read_jsonl(str(CHUNKS_PATH))
    meta_rows = read_jsonl(str(META_PATH))
    id2text = {row["id"]: row["text"] for row in chunks_rows}
    texts = [id2text[i] for i in range(len(id2text))]
    meta = meta_rows

    tokens: List[List[str]] = []
    if os.path.exists(BM25_SERIALIZED):
        with open(BM25_SERIALIZED, "r", encoding="utf-8") as handle:
            for line in handle:
                tokens.append(line.strip().split())
    else:
        tokens = [[] for _ in texts]

    return HybridRetriever(
        faiss_index=index,
        texts=texts,
        meta=meta,
        tokens=tokens,
        alpha=FUSE_ALPHA,
        dense_topk=DENSE_TOPK,
        sparse_topk=SPARSE_TOPK,
        rerank_cand=RERANK_CAND,
    )


def ensure_retriever() -> HybridRetriever:
    global _RETRIEVER
    if _RETRIEVER is None:
        with _LOAD_LOCK:
            if _RETRIEVER is None:
                _RETRIEVER = _load_state()
    return _RETRIEVER


def reload_retriever() -> HybridRetriever:
    global _RETRIEVER
    with _LOAD_LOCK:
        _RETRIEVER = _load_state()
    return _RETRIEVER


def search(query: str, topk: int = DEFAULT_TOPK):
    retriever = ensure_retriever()
    return retriever.search(query, topk=topk)


def _extract_page(text: str) -> int | None:
    match = re.search(r"\[Page\s+(\d+)\]", text)
    return int(match.group(1)) if match else None


def build_context(hits: Sequence[Tuple[str, dict]], max_chars: int = MAX_CTX_CHARS) -> Tuple[List[str], List[dict]]:
    seen = set()
    blocks: List[str] = []
    metas: List[dict] = []
    total = 0
    for text, meta in hits:
        token = hash(text)
        if token in seen:
            continue
        seen.add(token)
        if total + len(text) > max_chars:
            break
        blocks.append(text)
        metas.append(meta)
        total += len(text)
    return blocks, metas


def build_numbered_context(blocks: Sequence[str], metas: Sequence[dict]) -> Tuple[str, List[Tuple[int, int | None, str, int]]]:
    numbered: List[str] = []
    ref_notes: List[Tuple[int, int | None, str, int]] = []
    for idx, (text, meta) in enumerate(zip(blocks, metas), start=1):
        page = _extract_page(text)
        title = meta.get("title", "unknown")
        chunk_id = meta.get("chunk_id", -1)
        ref_notes.append((idx, page, title, chunk_id))
        numbered.append(f"[片段{idx}] {text}")
    return "\n\n".join(numbered), ref_notes


def format_reference_lines(ref_notes: Iterable[Tuple[int, int | None, str, int]]) -> List[str]:
    lines = ["\n\n---\n## 参考片段"]
    for idx, page, title, chunk_id in ref_notes:
        page_str = f"Page {page}" if page is not None else "Page ?"
        lines.append(f"- 片段{idx} · {page_str} · {title} · chunk_id={chunk_id}")
    return lines
