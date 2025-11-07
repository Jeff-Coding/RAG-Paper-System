"""Ingestion pipeline helpers used by the crawler."""
from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Union

import faiss  # type: ignore
import fitz  # type: ignore
import numpy as np
from tqdm import tqdm

from ..config import (
    BM25_SERIALIZED,
    CHUNKS_PATH,
    FAISS_DIR,
    FAISS_INDEX_PATH,
    META_PATH,
    PDF_DIR,
    TEXT_DIR,
)
from ..models import get_embed
from ..splitter import build_splitter
from ..utils import clean_text, tokenize_for_bm25, write_jsonl

LOGGER = logging.getLogger(__name__)


def _iter_with_progress(items: Sequence[Path], *, desc: str, enable: bool) -> Iterable[Path]:
    if enable and len(items) > 1:
        return tqdm(items, desc=desc)
    return items


def pdf_to_text(pdf_path: Path) -> str:
    doc = fitz.open(str(pdf_path))
    pages: List[str] = []
    for i, page in enumerate(doc):
        text = page.get_text("text")
        pages.append(f"[Page {i + 1}]\n{text}".strip())
    return "\n\n".join(pages)


def ensure_text_cache(pdf_path: Path) -> Path:
    base = pdf_path.stem
    txt_path = TEXT_DIR / f"{base}.txt"
    if not txt_path.exists():
        txt_path.parent.mkdir(parents=True, exist_ok=True)
        raw = pdf_to_text(pdf_path)
        txt_path.write_text(raw, encoding="utf-8")
    return txt_path


def run_ingest_pipeline(
    *,
    pdf_dir: Optional[Union[os.PathLike[str], str]] = None,
    progress: bool = False,
) -> Dict[str, object]:
    """Run the ingestion pipeline and return a summary dictionary."""

    pdf_root = Path(pdf_dir) if pdf_dir is not None else Path(PDF_DIR)
    pdf_root = pdf_root.resolve()
    pdf_root.mkdir(parents=True, exist_ok=True)

    LOGGER.info("Starting ingestion from %s", pdf_root)
    FAISS_DIR.mkdir(parents=True, exist_ok=True)
    TEXT_DIR.mkdir(parents=True, exist_ok=True)
    CHUNKS_PATH.parent.mkdir(parents=True, exist_ok=True)
    META_PATH.parent.mkdir(parents=True, exist_ok=True)
    Path(BM25_SERIALIZED).parent.mkdir(parents=True, exist_ok=True)

    pdfs = sorted(p for p in pdf_root.glob("*.pdf") if p.is_file())
    if not pdfs:
        LOGGER.warning("No PDF files found under %s", pdf_root)
        return {
            "pdf_root": str(pdf_root),
            "pdf_count": 0,
            "chunk_count": 0,
            "chunks_path": str(CHUNKS_PATH),
            "meta_path": str(META_PATH),
            "faiss_index": str(FAISS_INDEX_PATH),
            "bm25_path": str(BM25_SERIALIZED),
        }

    splitter = build_splitter()
    all_chunks: List[str] = []
    meta: List[Dict[str, object]] = []

    for pdf in _iter_with_progress(pdfs, desc="Parsing PDFs", enable=progress):
        txt_path = ensure_text_cache(pdf)
        raw = txt_path.read_text(encoding="utf-8")
        raw = clean_text(raw)
        chunks = splitter.split_text(raw)
        for i, chunk in enumerate(chunks):
            chunk = clean_text(chunk)
            if not chunk:
                continue
            all_chunks.append(chunk)
            meta.append({"source": str(pdf), "chunk_id": i, "title": pdf.name})

    if not all_chunks:
        LOGGER.warning("No text chunks generated from PDFs in %s", pdf_root)
        return {
            "pdf_root": str(pdf_root),
            "pdf_count": len(pdfs),
            "chunk_count": 0,
            "chunks_path": str(CHUNKS_PATH),
            "meta_path": str(META_PATH),
            "faiss_index": str(FAISS_INDEX_PATH),
            "bm25_path": str(BM25_SERIALIZED),
        }

    LOGGER.info("Embedding %s chunks", len(all_chunks))
    embed = get_embed()

    vectors: List[np.ndarray] = []
    batch_size = 128
    for start in range(0, len(all_chunks), batch_size):
        batch = all_chunks[start : start + batch_size]
        vecs = embed.encode(
            batch,
            batch_size=batch_size,
            normalize_embeddings=True,
            convert_to_numpy=True,
            show_progress_bar=progress,
        )
        vectors.append(vecs)

    matrix = np.vstack(vectors)
    count, dimension = matrix.shape
    LOGGER.info("Built dense matrix with %s vectors (dim=%s)", count, dimension)

    index = faiss.IndexFlatIP(dimension)
    index.add(matrix)
    faiss.write_index(index, str(FAISS_INDEX_PATH))
    LOGGER.info("FAISS index written to %s", FAISS_INDEX_PATH)

    write_jsonl(str(CHUNKS_PATH), [{"id": i, "text": text} for i, text in enumerate(all_chunks)])
    write_jsonl(str(META_PATH), meta)
    LOGGER.info("Saved %s chunks metadata to %s", len(all_chunks), META_PATH)

    tokens = [" ".join(tokenize_for_bm25(text)) for text in all_chunks]
    with open(BM25_SERIALIZED, "w", encoding="utf-8") as fh:
        fh.write("\n".join(tokens))
    LOGGER.info("BM25 tokens serialized to %s", BM25_SERIALIZED)

    return {
        "pdf_root": str(pdf_root),
        "pdf_count": len(pdfs),
        "chunk_count": len(all_chunks),
        "chunks_path": str(CHUNKS_PATH),
        "meta_path": str(META_PATH),
        "faiss_index": str(FAISS_INDEX_PATH),
        "bm25_path": str(BM25_SERIALIZED),
    }


def main(progress: bool = True) -> int:
    """CLI entrypoint used by legacy scripts."""

    summary = run_ingest_pipeline(progress=progress)
    return 0 if summary.get("chunk_count", 0) else 1


if __name__ == "__main__":
    raise SystemExit(main())
