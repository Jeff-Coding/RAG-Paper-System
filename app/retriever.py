from typing import List, Tuple, Dict, Any
import faiss
import numpy as np
from rank_bm25 import BM25Okapi
from .models import get_embed, rerank_cross_encoder
from .utils import tokenize_for_bm25

class HybridRetriever:
    def __init__(self, faiss_index: faiss.Index, texts: List[str], meta: List[Dict[str, Any]], tokens: List[List[str]],
                 alpha: float = 0.6, dense_topk: int = 50, sparse_topk: int = 50, rerank_cand: int = 100):
        self.index = faiss_index
        self.texts = texts
        self.meta = meta
        self.alpha = alpha
        self.dense_topk = dense_topk
        self.sparse_topk = sparse_topk
        self.rerank_cand = rerank_cand
        self.embed = get_embed()
        self.bm25 = BM25Okapi(tokens)

    def _dense_search(self, query: str) -> Dict[int, float]:
        qv = self.embed.encode([query], normalize_embeddings=True).astype("float32")
        D, I = self.index.search(qv, self.dense_topk)
        return {int(i): float(s) for i, s in zip(I[0], D[0]) if i != -1}

    def _sparse_search(self, query: str) -> Dict[int, float]:
        q_tokens = tokenize_for_bm25(query)
        scores = self.bm25.get_scores(q_tokens)
        top = np.argsort(scores)[-self.sparse_topk:][::-1]
        return {int(i): float(scores[i]) for i in top}

    def search(self, query: str, topk: int = 10) -> List[Tuple[str, Dict[str, Any]]]:
        dense_scores = self._dense_search(query)
        sparse_scores = self._sparse_search(query)
        keys = set(dense_scores) | set(sparse_scores)
        fused = []
        for k in keys:
            ds = dense_scores.get(k, 0.0)
            ss = sparse_scores.get(k, 0.0)
            fused.append((k, self.alpha * ds + (1 - self.alpha) * ss))
        fused.sort(key=lambda x: x[1], reverse=True)
        cand = [i for i, _ in fused[:self.rerank_cand]]
        cand_texts = [self.texts[i] for i in cand]
        order = rerank_cross_encoder(query, cand_texts, max(topk, 1))
        final_ids = [cand[i] for i in order][:topk]
        return [(self.texts[i], self.meta[i]) for i in final_ids]
