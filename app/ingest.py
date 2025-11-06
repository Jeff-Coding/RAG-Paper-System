import os, json
import numpy as np
import faiss
import fitz  # PyMuPDF
from tqdm import tqdm

from .config import PDF_DIR, TEXT_DIR, FAISS_DIR, FAISS_INDEX_PATH, CHUNKS_PATH, META_PATH, BM25_TOKENS_PKL, BM25_SERIALIZED, CHUNK_SIZE, CHUNK_OVERLAP
from .splitter import build_splitter
from .models import get_embed
from .utils import write_jsonl, clean_text, tokenize_for_bm25

def pdf_to_text(pdf_path: str) -> str:
    doc = fitz.open(pdf_path)
    pages = []
    for i, page in enumerate(doc):
        t = page.get_text("text")
        pages.append(f"[Page {i+1}]\n{t}".strip())
    return "\n\n".join(pages)

def ensure_text_cache(pdf_file: str) -> str:
    base = os.path.splitext(os.path.basename(pdf_file))[0]
    txt_path = os.path.join(TEXT_DIR, base + ".txt")
    if not os.path.exists(txt_path):
        raw = pdf_to_text(pdf_file)
        with open(txt_path, "w", encoding="utf-8") as f:
            f.write(raw)
    return txt_path

def main():
    os.makedirs(FAISS_DIR, exist_ok=True)
    os.makedirs(TEXT_DIR, exist_ok=True)

    # 1) Gather and parse
    pdfs = [os.path.join(PDF_DIR, f) for f in os.listdir(PDF_DIR) if f.lower().endswith(".pdf")]
    if not pdfs:
        print("No PDFs found in data/pdf/. Put some PDFs first.")
        return

    splitter = build_splitter()
    all_chunks, meta = [], []
    for pdf in tqdm(pdfs, desc="Parsing PDFs"):
        txt_path = ensure_text_cache(pdf)
        with open(txt_path, "r", encoding="utf-8") as f:
            raw = f.read()
        raw = clean_text(raw)
        chunks = splitter.split_text(raw)
        for i, c in enumerate(chunks):
            c = clean_text(c)
            if not c:
                continue
            all_chunks.append(c)
            meta.append({"source": pdf, "chunk_id": i, "title": os.path.basename(pdf)})

    if not all_chunks:
        print("No chunks produced.")
        return

    # 2) Embedding + FAISS
    print("Embedding chunks...")
    embed = get_embed()

    vecs_list = []
    rng = range(0, len(all_chunks), 128)
    for i in tqdm(rng, desc="Embedding in batches"):
        batch_texts = all_chunks[i:i+128]
        # sentence-transformers 的 encode 支持 batch，并会自动用 GPU（若模型在 CUDA）
        # normalize_embeddings=True 以便用 InnerProduct 等价 Cosine
        batch_vecs = embed.encode(
            batch_texts,
            batch_size=128,
            normalize_embeddings=True,
            convert_to_numpy=True,
            show_progress_bar=False
        )
        vecs_list.append(batch_vecs)

    vecs = np.vstack(vecs_list)
    N, dim = vecs.shape
    print(f"Total vectors: {N}, dim: {dim}, dtype: {vecs.dtype}")

    index = faiss.IndexFlatIP(dim)
    index.add(vecs)
    faiss.write_index(index, str(FAISS_INDEX_PATH))
    print(f"FAISS index written to {FAISS_INDEX_PATH}")

    # Save chunks/meta
    write_jsonl(str(CHUNKS_PATH), [{"id": i, "text": t} for i, t in enumerate(all_chunks)])
    write_jsonl(str(META_PATH), meta)
    print(f"Saved {len(all_chunks)} chunks and meta.")

    # 3) BM25 tokens
    print("Building BM25 tokens...")
    tokens = [tokenize_for_bm25(t) for t in all_chunks]
    # serialize lite format for portability
    with open(BM25_SERIALIZED, "w", encoding="utf-8") as f:
        for toks in tokens:
            f.write(" ".join(toks) + "\n")
    print(f"BM25 tokens saved to {BM25_SERIALIZED}")
    print("Ingestion completed.")

if __name__ == "__main__":
    main()
