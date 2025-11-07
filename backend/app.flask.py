# app_flask.py
import os
import re
import json
import threading
from types import SimpleNamespace
from flask import Flask, request, jsonify
from flask_cors import CORS

# --- 兼容导入：支持 "from app.xxx" 或相对导入 ---

from app.config import (
        FAISS_INDEX_PATH, CHUNKS_PATH, META_PATH, BM25_SERIALIZED,
        DEFAULT_TOPK, FUSE_ALPHA, DENSE_TOPK, SPARSE_TOPK, RERANK_CAND
)
from app.utils import read_jsonl
from app.retriever import HybridRetriever
from app.models import llm_generate


import faiss

# -----------------------
# 全局状态
# -----------------------
app = Flask(__name__)
CORS(app)

_RETRIEVER = None
_LOAD_LOCK = threading.Lock()

def _load_state():
    """加载 FAISS 索引 + 文本/元信息 + BM25 tokens，构建 HybridRetriever。"""
    if not os.path.exists(FAISS_INDEX_PATH):
        raise RuntimeError("FAISS index not found. 请先运行: python app/ingest.py")
    index = faiss.read_index(str(FAISS_INDEX_PATH))

    chunks_rows = read_jsonl(str(CHUNKS_PATH))
    meta_rows = read_jsonl(str(META_PATH))
    id2text = {r["id"]: r["text"] for r in chunks_rows}
    texts = [id2text[i] for i in range(len(id2text))]
    meta = meta_rows

    tokens = []
    if os.path.exists(BM25_SERIALIZED):
        with open(BM25_SERIALIZED, "r", encoding="utf-8") as f:
            for line in f:
                tokens.append(line.strip().split())
    else:
        tokens = [[] for _ in texts]  # degrade

    retriever = HybridRetriever(
        faiss_index=index,
        texts=texts,
        meta=meta,
        tokens=tokens,
        alpha=FUSE_ALPHA,
        dense_topk=DENSE_TOPK,
        sparse_topk=SPARSE_TOPK,
        rerank_cand=RERANK_CAND,
    )
    return retriever

def _extract_page(text: str):
    m = re.search(r"\[Page\s+(\d+)\]", text)
    return int(m.group(1)) if m else None

def _uniq_keep_order(items):
    seen = set()
    out = []
    for x in items:
        key = hash(x)
        if key not in seen:
            seen.add(key)
            out.append(x)
    return out

def _ensure_retriever():
    global _RETRIEVER
    if _RETRIEVER is None:
        with _LOAD_LOCK:
            if _RETRIEVER is None:
                _RETRIEVER = _load_state()

# -----------------------
# 仅两个对外 API
# -----------------------

@app.route("/ask", methods=["GET", "POST"])
def ask():
    """
    问答接口：
      - GET 方式：/ask?q=你的问题&k=10
      - POST 方式：JSON {"q": "...", "k": 10}
    """
    payload = request.get_json(silent=True) or {}
    q = request.args.get("q") or payload.get("q")
    k = int(request.args.get("k") or payload.get("k") or DEFAULT_TOPK)
    if not q or not str(q).strip():
        return jsonify({"error": "q (question) is required"}), 400

    _ensure_retriever()
    hits = _RETRIEVER.search(q, topk=k)

    blocks = [t for t, _ in hits]
    metas  = [m for _, m in hits]

    # 去重 + 截断上下文
    blocks = _uniq_keep_order(blocks)
    metas = metas[:len(blocks)]
    MAX_CTX_CHARS = 12000
    ctx, total = [], 0
    for b in blocks:
        if total + len(b) > MAX_CTX_CHARS:
            break
        ctx.append(b)
        total += len(b)

    # 编号与引用
    numbered, ref_notes = [], []
    for i, (text, meta) in enumerate(zip(ctx, metas), start=1):
        page = _extract_page(text)
        title = meta.get("title", "unknown")
        cid = meta.get("chunk_id", -1)
        ref_notes.append((i, page, title, cid))
        numbered.append(f"[片段{i}] {text}")
    context = "\n\n".join(numbered)

    prompt = f"""你是学术助理。请严格遵守以下规则，用中文并用 Markdown 输出：
- 输出模块：**摘要**、**要点**（每条≤2句，句末标注如 [片段3]）、**证据摘录**（只放最关键的原句，最多3条）、**局限与下一步**、**参考片段**。
- 只依据给定证据回答，**不要编造**；若证据不足，明确指出“证据不足，无法回答该部分”。
- 优先给出结论再给推理；不要长篇堆砌。
- 术语用简洁中文，必要时给公式/定义的最小解释。

【证据】
{context}

【问题】{q}

现在开始回答：
"""
    answer = llm_generate(prompt)

    if answer.startswith("（未配置 LLM") or answer.startswith("(LLM"):
        # 抽取式降级
        out = ["## 摘要\n未配置 LLM，以下为命中的证据片段节选。\n"]
        for i, b in enumerate(ctx, start=1):
            out.append(f"### 片段{i}\n> {b[:800]}{'…' if len(b)>800 else ''}")
        answer = "\n\n".join(out)

    # 统一追加参考表
    lines = ["\n\n---\n## 参考片段"]
    for (idx, page, title, cid) in ref_notes:
        page_str = f"Page {page}" if page is not None else "Page ?"
        lines.append(f"- 片段{idx} · {page_str} · {title} · chunk_id={cid}")
    answer = f"{answer}\n" + "\n".join(lines)

    return jsonify({
        "answer": answer,
        "references": metas[:len(ctx)]
    })

@app.route("/crawl", methods=["POST"])
def crawl():
    """
    关键词抓取接口：POST JSON
    {
      "query": "transformer; RAG",
      "providers": "arxiv,openalex,semanticscholar",
      "max_per_source": 50,
      "year_min": 2018,
      "year_max": 2025,
      "run_ingest": true
    }
    - query 支持用 ';' 分隔多个关键词
    - run_ingest=true 时，抓完后自动跑 ingest（会更新 FAISS 与 BM25）
    """
    body = request.get_json(force=True, silent=False) or {}
    query          = body.get("query")
    providers      = body.get("providers", "arxiv,openalex,semanticscholar")
    max_per_source = int(body.get("max_per_source", 100))
    year_min       = body.get("year_min", None)
    year_max       = body.get("year_max", None)
    run_ingest     = bool(body.get("run_ingest", False))
    if not query or not str(query).strip():
        return jsonify({"error": "query is required"}), 400

    # 调用你现有的抓取器
    import paper_collector as pc

    args = SimpleNamespace(
        query=query,
        providers=providers,
        max_per_source=max_per_source,
        year_min=year_min,
        year_max=year_max,
        out=pc.DEFAULT_OUT_DIR,
        meta=pc.DEFAULT_META_PATH,
        run_ingest=run_ingest
    )

    try:
        pc.run(args)
        # 若触发了 ingest，则需要重载内存中的检索器
        if run_ingest:
            global _RETRIEVER
            with _LOAD_LOCK:
                _RETRIEVER = _load_state()
        return jsonify({"status": "ok", "message": "crawl finished", "ingested": run_ingest})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


if __name__ == "__main__":
    # 开发模式：python app_flask.py
    # 生产建议：gunicorn -w 2 -b 0.0.0.0:8000 app_flask:app
    app.run(host="0.0.0.0", port=8000, debug=True)
