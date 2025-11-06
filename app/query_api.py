from fastapi import FastAPI, Query
from typing import List, Dict, Any
import os
import re
import faiss

from .config import FAISS_INDEX_PATH, CHUNKS_PATH, META_PATH, BM25_SERIALIZED, DEFAULT_TOPK, FUSE_ALPHA, DENSE_TOPK, SPARSE_TOPK, RERANK_CAND
from .utils import read_jsonl
from .retriever import HybridRetriever
from .models import llm_generate

app = FastAPI(title="RAG Papers Backend", version="0.1.0")


def _load_state():
    if not os.path.exists(FAISS_INDEX_PATH):
        raise RuntimeError("FAISS index not found. Run `python app/ingest.py` first.")
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

def _extract_page(text: str) -> int | None:
    # 从 chunk 文本中提取首次出现的 [Page N]
    m = re.search(r"\[Page\s+(\d+)\]", text)
    return int(m.group(1)) if m else None

def _uniq_keep_order(items):
    seen = set()
    out = []
    for x in items:
        key = hash(x)  # 简单去重；也可 md5(x) 更稳
        if key not in seen:
            seen.add(key)
            out.append(x)
    return out

RETRIEVER = None

@app.on_event("startup")
def on_startup():
    global RETRIEVER
    RETRIEVER = _load_state()

@app.get("/health")
def health():
    return {"status": "ok"}

@app.get("/search")
def search(q: str = Query(..., description="query"), k: int = DEFAULT_TOPK):
    hits = RETRIEVER.search(q, topk=k)
    results = []
    for text, meta in hits:
        results.append({"text": text, "meta": meta})
    return {"results": results}

@app.get("/ask")
def ask(q: str = Query(..., description="question"), k: int = DEFAULT_TOPK):
    hits = RETRIEVER.search(q, topk=k)
    # 1) 取文本与元信息
    blocks = [t for t, _ in hits]
    metas = [m for _, m in hits]

    # 2) 去重（按文本指纹）
    blocks = _uniq_keep_order(blocks)
    metas = metas[:len(blocks)]

    # 3) 限制上下文总长度，避免极长 prompt 影响可读性（按字符数）
    MAX_CTX_CHARS = 12000
    ctx = []
    total = 0
    for b in blocks:
        if total + len(b) > MAX_CTX_CHARS:
            break
        ctx.append(b)
        total += len(b)

    # 4) 给每段标序号，并抽页码（用于回答内联引用与末尾参考表）
    numbered_blocks = []
    ref_notes = []  # [(idx, page, title, chunk_id)]
    for i, (text, meta) in enumerate(zip(ctx, metas), start=1):
        page = _extract_page(text)
        title = meta.get("title", "unknown")
        chunk_id = meta.get("chunk_id", -1)
        ref_notes.append((i, page, title, chunk_id))
        numbered_blocks.append(f"[片段{i}] {text}")

    context = "\n\n".join(numbered_blocks)

    # 5) 结构化提示词（带微型示例），强制 Markdown + 每条要点内联引用
    prompt = f"""你是学术助理。请严格遵守以下规则，用中文并用 Markdown 输出：
- 输出模块：**摘要**、**要点**（每条≤2句，句末标注如 [片段3]）、**证据摘录**（只放最关键的原句，最多3条）、**局限与下一步**、**参考片段**。
- 只依据给定证据回答，**不要编造**；若证据不足，明确指出“证据不足，无法回答该部分”。
- 优先给出结论再给推理；不要长篇堆砌。
- 术语用简洁中文，必要时给公式/定义的最小解释。

【证据】
{context}

【问题】{q}

【示例（示意风格，不是答案模板）】
- 要点：模型使用了自注意力以并行化序列建模 [片段2]。
- 证据摘录：
  - “Transformer 依赖自注意力而非 RNN/卷积” [片段2]。

现在开始回答：
"""

    answer = llm_generate(prompt)

    # 6) 若未配置 LLM 或调用失败，则回退到可读的抽取式结果（比原始拼接更友好）
    if answer.startswith("（未配置 LLM") or answer.startswith("(LLM"):
        fallback = ["## 摘要\n未配置 LLM，下面为命中的证据片段原文节选。\n"]
        for i, b in enumerate(ctx, start=1):
            fallback.append(f"### 片段{i}\n> {b[:800]}{'…' if len(b)>800 else ''}")
        answer = "\n\n".join(fallback)

    # 7) 在答案末尾统一追加“参考片段”表，映射编号->页码/标题/chunk_id
    #    便于读者核查；LLM 已内联 [片段i]，这里是完整索引。
    lines = ["\n\n---\n## 参考片段"]
    for (idx, page, title, cid) in ref_notes:
        page_str = f"Page {page}" if page is not None else "Page ?"
        lines.append(f"- 片段{idx} · {page_str} · {title} · chunk_id={cid}")
    lines_str = "\n".join(lines)
    answer = f"{answer}\n{lines_str}"

    refs = metas[:len(ctx)]
    return {"answer": answer, "references": refs}