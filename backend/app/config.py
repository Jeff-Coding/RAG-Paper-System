from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

DATA_DIR = ROOT / "data"
PDF_DIR = DATA_DIR / "pdf"
TEXT_DIR = DATA_DIR / "text"

INDEX_DIR = ROOT / "index"
FAISS_DIR = INDEX_DIR / "faiss"
BM25_DIR = INDEX_DIR / "bm25"

# files
FAISS_INDEX_PATH = FAISS_DIR / "dense.faiss"
CHUNKS_PATH = FAISS_DIR / "chunks.jsonl"
META_PATH = FAISS_DIR / "meta.jsonl"

# bm25 pickles
BM25_TOKENS_PKL = BM25_DIR / "tokens.pkl"
BM25_SERIALIZED = BM25_DIR / "bm25.jsonl"  # lite format

# chunking
CHUNK_SIZE = 800
CHUNK_OVERLAP = 120

# retrieval
FUSE_ALPHA = 0.6     # dense weight
DENSE_TOPK = 50
SPARSE_TOPK = 50
RERANK_CAND = 100
DEFAULT_TOPK = 10

# llm
import os
OPENAI_API_BASE = os.getenv("OPENAI_API_BASE", "http://localhost:11434/v1").strip()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "EMPTY").strip()
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-oss:20b")
