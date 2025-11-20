from pathlib import Path
import os

# ---- Paths ---------------------------------------------------------------
ROOT = Path(__file__).resolve().parents[1]

# Raw assets
DATA_DIR = ROOT / "data"
RAW_PDF_DIR = DATA_DIR / "raw_pdfs"
RAW_METADATA_DIR = DATA_DIR / "metadata"
PAPER_METADATA_PATH = RAW_METADATA_DIR / "papers.jsonl"

# Legacy aliases (older modules still import these names)
PDF_DIR = RAW_PDF_DIR

# Parsed artifacts
PARSED_DIR = DATA_DIR / "parsed"
TEXT_DIR = PARSED_DIR / "text"
META_DIR = PARSED_DIR / "meta"

# Knowledge graph
GRAPH_DIR = DATA_DIR / "graph"
GRAPH_PATH = GRAPH_DIR / "papers_graph.json"
GRAPH_INDEX_PATH = GRAPH_DIR / "graph_index.json"

# Retrieval index
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
OPENAI_API_BASE = os.getenv("OPENAI_API_BASE", "http://localhost:11434/v1").strip()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "EMPTY").strip()
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-oss:20b")
