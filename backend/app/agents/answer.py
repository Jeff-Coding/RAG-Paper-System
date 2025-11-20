"""Answer Agent: compose final response leveraging KG/RAG context."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Sequence

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
    """Format prompts and handle graceful degradation when no LLM is set."""

    def build_prompt(self, ctx: AnswerContext) -> str:
        return f"""你是学术助理。请严格遵守以下规则，用中文并用 Markdown 输出：
- 输出模块：**摘要**、**要点**（每条≤2句，句末标注如 [片段3]）、**证据摘录**（只放最关键的原句，最多3条）、**局限与下一步**、**参考片段**。
- 只依据给定证据回答，**不要编造**；若证据不足，明确指出“证据不足，无法回答该部分”。
- 优先给出结论再给推理；不要长篇堆砌。
- 术语用简洁中文，必要时给公式/定义的最小解释。
- 语言需自然流畅，段落之间使用恰当衔接词（如“此外”“因此”“与此同时”），避免生硬罗列或堆砌原句。
- 每个模块给出清晰的主题句，再补充精炼解释，让读者可以顺畅阅读。

【路由策略】{ctx.strategy}（原因：{ctx.reason}）
【知识图谱】
{ctx.graph_context}

【证据】
{ctx.numbered_context}

【问题】{ctx.question}

现在开始回答：
"""

    def answer(self, ctx: AnswerContext) -> str:
        prompt = self.build_prompt(ctx)
        result = llm_generate(prompt)
        if result.startswith("（未配置 LLM") or result.startswith("(LLM"):
            # graceful degradation: return extracted evidence
            extracted = ["## 摘要\n当前未配置 LLM，下面提供命中的证据片段供参考。\n"]
            for idx, block in enumerate(ctx.evidence_blocks, start=1):
                snippet = block[:800].strip()
                suffix = "…" if len(block) > 800 else ""
                extracted.append(f"### 片段{idx}\n> {snippet}{suffix}")
            result = "\n\n".join(extracted)
        return result

