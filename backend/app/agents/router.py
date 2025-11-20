"""Router Agent: choose KG / RAG / Hybrid strategy for a query.

The routing logic is intentionally light-weight and rule-based so it works
without external LLM calls. It inspects the user question for structural
keywords (适合知识图谱), content keywords (适合 RAG) and synthesis terms that
benefit from组合检索 (Hybrid).
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import List


STRUCTURE_TERMS = {
    "关系",
    "合作",
    "谁",
    "作者",
    "机构",
    "图谱",
    "关联",
    "网络",
    "trend",
    "graph",
}

SYNTHESIS_TERMS = {
    "综述",
    "对比",
    "比较",
    "review",
    "survey",
    "benchmark",
}

CONTENT_TERMS = {
    "结果",
    "实验",
    "细节",
    "实现",
    "方法",
    "效果",
    "性能",
    "evaluation",
    "ablation",
    "dataset",
    "code",
}


@dataclass
class RouterDecision:
    strategy: str  # "kg" | "rag" | "hybrid"
    reason: str
    cues: List[str]


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip().lower()


def _match_terms(text: str, terms) -> List[str]:
    return [t for t in terms if t in text]


def route_question(question: str) -> RouterDecision:
    """Select retrieval strategy based on heuristics."""

    norm = _normalize(question)
    if not norm:
        return RouterDecision(strategy="rag", reason="空问题，默认使用正文检索", cues=[])

    syn_hits = _match_terms(norm, SYNTHESIS_TERMS)
    struct_hits = _match_terms(norm, STRUCTURE_TERMS)
    content_hits = _match_terms(norm, CONTENT_TERMS)

    cues = syn_hits + struct_hits + content_hits

    if syn_hits and struct_hits:
        return RouterDecision(
            strategy="hybrid",
            reason="检测到综述/对比需求且包含结构性实体，先找图谱再检索正文",
            cues=cues,
        )

    if syn_hits:
        return RouterDecision(
            strategy="hybrid",
            reason="综述/对比类问题需要结合结构与正文",
            cues=cues,
        )

    if struct_hits and not content_hits:
        return RouterDecision(
            strategy="kg",
            reason="命中结构化关键词，优先使用知识图谱",
            cues=cues,
        )

    if content_hits:
        return RouterDecision(
            strategy="rag",
            reason="关注实验/实现细节，直接走正文检索",
            cues=cues,
        )

    # Default: hybrid for safety when intent unclear
    return RouterDecision(
        strategy="hybrid",
        reason="未命中特定模式，采用混合检索保证召回",
        cues=cues,
    )

