# RAG Papers Backend (No Frontend)

A minimal, production-leaning backend to build a local RAG (Retrieval-Augmented Generation) database for papers.
This version ships **without any frontend**. It exposes a FastAPI service for search and Q&A, and a CLI `ingest.py` to index PDFs.

## Structure
```
rag-papers-backend/
├─ app/
│  ├─ query_api.py        # FastAPI service: /health, /search, /ask
│  ├─ ingest.py           # CLI for PDF -> text -> chunks -> embeddings -> indices
│  ├─ retriever.py        # Hybrid retrieval (FAISS + BM25) + rerank
│  ├─ splitter.py         # Chunking policy
│  ├─ models.py           # Embedding + optional reranker + optional LLM call
│  ├─ config.py           # Paths and settings
│  └─ utils.py            # IO helpers, tokenization, hashing
├─ data/
│  ├─ pdf/                # Put your PDFs here
│  └─ text/               # Parsed text cache
├─ index/
│  ├─ faiss/              # FAISS dense index + chunks.jsonl + meta.jsonl
│  └─ bm25/               # BM25 pickles
├─ requirements.txt
└─ README.md
```

## Quickstart

### 1) Create env & install
```bash
conda create -n ragdb python=3.11 -y
conda activate ragdb
pip install -r requirements.txt
```

### 2) Put PDFs
#### 1) 抓 100 篇 Transformer 相关论文（每个源最多100篇）
```
python paper_collector.py --query "transformer" --max-per-source 100
```

#### 2) 多关键词；限定年份；只用 arXiv 和 OpenAlex
```
python paper_collector.py --query "RAG;retrieval augmented generation" --year-min 2019 --providers arxiv,openalex
```
##### 3) 下载到自定义目录，并在完成后自动跑索引（调用 ingest）
```
python paper_collector.py --query "multimodal LLM" --out data/pdf --run-ingest
```

### 3) Build index
```bash
python -m app.ingest
```

### 4) Run API
```bash
uvicorn app.query_api:app --host 0.0.0.0 --port 8001 --reload
```
Endpoints:
- `GET /health`
- `GET /search?q=...&k=10`
- `GET /ask?q=...`

### Optional: LLM Answering
If you have an OpenAI-compatible endpoint, set:
```bash
export OPENAI_API_BASE="https://your-endpoint/v1"
export OPENAI_API_KEY="sk-..."
export OPENAI_MODEL="gpt-4o-mini"  # or your local vLLM model name
```
Otherwise the API returns a simple extractive answer from top contexts.

## Notes
- BM25 uses a simple tokenizer; for Chinese it uses `jieba` automatically.
- Reranker is optional; if models can't load, the system gracefully continues without reranking.
