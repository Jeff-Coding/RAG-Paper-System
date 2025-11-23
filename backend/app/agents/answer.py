"""Answer Agent: compose final response leveraging KG/RAG context."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Sequence

from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI

from app.config import OPENAI_API_BASE, OPENAI_API_KEY, OPENAI_MODEL
from app.models import llm_generate


@dataclass
class AnswerContext:
    question: str
    strategy: str
    reason: str
    graph_context: str
    evidence_blocks: Sequence[str]
    numbered_context: str
    references: List[Dict[str, object]]


class AnswerAgent:
    """LangChain-native answer generator with graceful degradation."""

    def __init__(self):
        self.llm = self._resolve_llm()
        self.prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    "你是学术助理。请严格遵守以下规则，用中文并用 Markdown 输出：\n"
                    "- 输出模块：**摘要**、**要点**（每条≤2句，句末标注如 [片段3]）、**证据摘录**（只放最关键的原句，最多3条）、**局限与下一步**、**参考片段**。\n"
                    "- 只依据给定证据回答，不要编造；若证据不足，请明确说明。\n"
                    "- 优先给出结论再给推理，保持语言流畅。",
                ),
                (
                    "human",
                    "【路由策略】{strategy}（原因：{reason}）\n"
                    "【知识图谱】\n{graph}\n\n【证据】\n{context}\n\n【问题】{question}\n"
                    "请用中文 Markdown 输出，引用格式使用 [片段N]。",
                ),
            ]
        )

    def _resolve_llm(self):
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

    def _fallback_snippets(self, ctx: AnswerContext) -> str:
        extracted = ["## 摘要\n当前未配置 LLM，下面提供命中的证据片段供参考。\n"]
        for idx, block in enumerate(ctx.evidence_blocks, start=1):
            snippet = block[:800].strip()
            suffix = "…" if len(block) > 800 else ""
            extracted.append(f"### 片段{idx}\n> {snippet}{suffix}")
        return "\n\n".join(extracted)

    def answer(self, ctx: AnswerContext) -> str:
        context_text = ctx.numbered_context or "（未检索到正文片段）"
        graph_text = ctx.graph_context or "（知识图谱未查询）"

        if self.llm:
            chain = (
                {
                    "question": lambda _: ctx.question,
                    "context": lambda _: context_text,
                    "graph": lambda _: graph_text,
                    "strategy": lambda _: ctx.strategy,
                    "reason": lambda _: ctx.reason,
                }
                | self.prompt
                | self.llm
                | StrOutputParser()
            )
            return chain.invoke({})

        prompt = self.prompt.format(
            question=ctx.question,
            context=context_text,
            graph=graph_text,
            strategy=ctx.strategy,
            reason=ctx.reason,
        )
        result = llm_generate(prompt)
        if result.startswith("（未配置 LLM") or result.startswith("(LLM"):
            return self._fallback_snippets(ctx)
        return result
