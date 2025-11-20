from typing import Optional, List, Tuple
import os
from typing import List, Optional

import numpy as np

# Embedding via sentence-transformers
from sentence_transformers import SentenceTransformer

# Optional reranker (cross-encoder). Gracefully degrade if not available.
from transformers import AutoTokenizer, AutoModelForSequenceClassification
import torch

from .config import OPENAI_API_BASE, OPENAI_API_KEY, OPENAI_MODEL

_embed_model: Optional[SentenceTransformer] = None
_rerank_tok = None
_rerank_model = None
_rerank_device = "cpu" 

def get_embed() -> SentenceTransformer:
    global _embed_model
    if _embed_model is None:
        _embed_model = SentenceTransformer("BAAI/bge-m3", device="cuda" if torch.cuda.is_available() else "cpu")
    return _embed_model

def get_reranker():
    """初始化交叉重排器，优先使用CUDA，可回退CPU"""
    global _rerank_tok, _rerank_model, _rerank_device
    if _rerank_model is None:
        name = "BAAI/bge-reranker-base"
        _rerank_tok = AutoTokenizer.from_pretrained(name)
        _rerank_model = AutoModelForSequenceClassification.from_pretrained(name)
        _rerank_model.eval()
        if torch.cuda.is_available():
            _rerank_device = "cuda"
            _rerank_model.to(_rerank_device)
        else:
            _rerank_device = "cpu"
    return _rerank_tok, _rerank_model, _rerank_device

def _to_device(batch, device: str):
    """把 tokenizer 输出统一搬到指定 device"""
    out = {}
    for k, v in batch.items():
        # 某些 tokenizer 字段可能是 list，需要转张量
        if not torch.is_tensor(v):
            v = torch.as_tensor(v)
        out[k] = v.to(device, non_blocking=True)
    return out

def rerank_cross_encoder(query: str, texts: List[str], topk: int) -> List[int]:
    """返回按分数从高到低的索引列表（长度=topk）"""
    tok, model, device = get_reranker()
    n = len(texts)
    if tok is None or model is None or n == 0:
        return list(range(min(topk, n)))

    # 构造 batch（限制长度可减小显存 & 加速）
    enc = tok(
        [query] * n,
        texts,
        return_tensors="pt",
        padding=True,
        truncation=True,
        max_length=256,
    )

    # ---- 首次尝试：在模型所在 device 上推理 ----
    try:
        batch = _to_device(enc, device)
        with torch.inference_mode():
            logits = model(**batch).logits  # [n, 1]
        scores = logits.squeeze(-1).detach().float().cpu().numpy().tolist()
    except RuntimeError as e:
        # 若是设备不一致/显存相关异常，安全回退到 CPU 再跑一次
        if "Expected all tensors to be on the same device" in str(e) or "CUDA" in str(e):
            cpu_batch = _to_device(enc, "cpu")
            with torch.inference_mode():
                logits = model.to("cpu")(**cpu_batch).logits
            scores = logits.squeeze(-1).detach().float().numpy().tolist()
        else:
            raise

    order = sorted(range(n), key=lambda i: scores[i], reverse=True)[: min(topk, n)]
    return order

# Optional: call an OpenAI-compatible endpoint if available
def llm_generate(prompt: str) -> str:
    if not (OPENAI_API_BASE and OPENAI_API_KEY):
        # Fallback: return prompt tail marker to indicate no LLM configured.
        return "（未配置 LLM：返回的是检索片段的摘要/拼接结果。请设置 OPENAI_API_BASE 与 OPENAI_API_KEY 以获得生成式答案。）"
    import requests
    headers = {"Authorization": f"Bearer {OPENAI_API_KEY}"}
    payload = {
        "model": OPENAI_MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.2,
    }
    try:
        r = requests.post(f"{OPENAI_API_BASE.rstrip('/')}/chat/completions", json=payload, headers=headers, timeout=120)
        r.raise_for_status()
        data = r.json()
        return data["choices"][0]["message"]["content"].strip()
    except Exception as e:
        return f"(LLM 调用失败: {e})"
