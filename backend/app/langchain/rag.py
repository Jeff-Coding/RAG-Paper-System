"""LangChain-native RAG and answering pipeline."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Tuple

from langchain_core.documents import Document
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.retrievers import BaseRetriever
from langchain_core.runnables import RunnablePassthrough
from langchain_openai import ChatOpenAI

from app.agents import AnswerAgent, AnswerContext
from app.config import DEFAULT_TOPK, OPENAI_API_BASE, OPENAI_API_KEY, OPENAI_MODEL
from app.services import build_context, build_numbered_context, format_reference_lines, search


class HybridLangChainRetriever(BaseRetriever):
    """Bridge the existing hybrid retriever into LangChain's interface."""

    topk: int = DEFAULT_TOPK

    def __init__(self, *, topk: int = DEFAULT_TOPK):
        super().__init__()
        self.topk = topk

    def _get_relevant_documents(self, query: str, *, run_manager=None) -> List[Document]:  # type: ignore[override]
        hits = search(query, topk=self.topk)
        return [Document(page_content=text, metadata=meta) for text, meta in hits]

    async def _aget_relevant_documents(self, query: str, *, run_manager=None) -> List[Document]:  # type: ignore[override]
        return self._get_relevant_documents(query, run_manager=run_manager)


def _resolve_llm():
    if not (OPENAI_API_BASE and OPENAI_API_KEY and OPENAI_MODEL):
        return None
    try:
        return ChatOpenAI(
            model=OPENAI_MODEL,
            api_key=OPENAI_API_KEY,
            base_url=OPENAI_API_BASE,
            temperature=0.2,
        )
    except Exception:
        return None


@dataclass
class RagResult:
    answer: str
    blocks: List[str]
    references: List[Dict[str, object]]
    numbered_context: str
    reference_notes: List[Tuple[int, int | None, str, int]]

    def reference_lines(self) -> str:
        if not self.reference_notes:
            return ""
        return "\n".join(format_reference_lines(self.reference_notes))


class LangChainRagAgent:
    """Compose retrieval + generation with LangChain primitives."""

    def __init__(self):
        self.llm = _resolve_llm()
        self.prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    "你是学术论文助理，严格依据给定的知识图谱和证据回答，输出模块含：摘要、要点、证据摘录、局限与下一步、参考片段。不要编造。",
                ),
                (
                    "human",
                    "【路由策略】{strategy}（原因：{reason}）\n"
                    "【知识图谱】\n{graph}\n\n【证据】\n{context}\n\n【问题】{question}\n"
                    "请用中文 Markdown 输出，引用格式使用 [片段N]。",
                ),
            ]
        )

    def _format_docs(self, docs: List[Document]):
        blocks, metas = build_context([(doc.page_content, doc.metadata) for doc in docs])
        numbered, notes = build_numbered_context(blocks, metas)
        return blocks, metas, numbered or "（未检索到正文片段）", notes

    def answer(
        self,
        question: str,
        *,
        graph_context: str = "",
        topk: int = DEFAULT_TOPK,
        strategy: str = "rag",
        reason: str = "",
    ) -> RagResult:
        retriever = HybridLangChainRetriever(topk=topk)
        docs = retriever.invoke(question)
        blocks, metas, numbered_context, ref_notes = self._format_docs(docs)
        graph_text = graph_context or "（知识图谱未查询）"

        if self.llm:
            chain = (
                {
                    "context": lambda _: numbered_context,
                    "graph": lambda _: graph_text,
                    "question": RunnablePassthrough(),
                    "strategy": lambda _: strategy,
                    "reason": lambda _: reason or "",
                }
                | self.prompt
                | self.llm
                | StrOutputParser()
            )
            answer = chain.invoke(question)
        else:
            ctx = AnswerContext(
                question=question,
                strategy=strategy,
                reason=reason or "未配置 LLM，回退为传统模板",
                graph_context=graph_text,
                evidence_blocks=blocks,
                numbered_context=numbered_context,
                references=metas[: len(blocks)],
            )
            answer = AnswerAgent().answer(ctx)

        return RagResult(
            answer=answer,
            blocks=blocks,
            references=metas,
            numbered_context=numbered_context,
            reference_notes=ref_notes,
        )


_rag_agent: LangChainRagAgent | None = None


def get_rag_agent() -> LangChainRagAgent:
    global _rag_agent
    if _rag_agent is None:
        _rag_agent = LangChainRagAgent()
    return _rag_agent


__all__ = ["LangChainRagAgent", "get_rag_agent", "HybridLangChainRetriever", "RagResult"]
