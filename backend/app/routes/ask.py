"""Question answering route."""
from flask import Blueprint, jsonify, request

from app.config import DEFAULT_TOPK
from app.models import llm_generate
from app.services import (
    build_context,
    build_numbered_context,
    format_reference_lines,
    search,
)

ask_bp = Blueprint("ask", __name__)


@ask_bp.route("/ask", methods=["GET", "POST"])
def ask():
    """Hybrid retrieval QA endpoint."""

    payload = request.get_json(silent=True) or {}
    query = request.args.get("q") or payload.get("q")
    topk_raw = request.args.get("k") or payload.get("k")
    try:
        topk = int(topk_raw) if topk_raw is not None else DEFAULT_TOPK
    except (TypeError, ValueError):
        topk = DEFAULT_TOPK

    if not query or not str(query).strip():
        return jsonify({"error": "q (question) is required"}), 400

    hits = search(query, topk=topk)
    blocks, metas = build_context(hits)
    numbered_context, ref_notes = build_numbered_context(blocks, metas)

    prompt = f"""你是学术助理。请严格遵守以下规则，用中文并用 Markdown 输出：
- 输出模块：**摘要**、**要点**（每条≤2句，句末标注如 [片段3]）、**证据摘录**（只放最关键的原句，最多3条）、**局限与下一步**、**参考片段**。
- 只依据给定证据回答，**不要编造**；若证据不足，明确指出“证据不足，无法回答该部分”。
- 优先给出结论再给推理；不要长篇堆砌。
- 术语用简洁中文，必要时给公式/定义的最小解释。

【证据】
{numbered_context}

【问题】{query}

现在开始回答：
"""

    answer = llm_generate(prompt)

    if answer.startswith("（未配置 LLM") or answer.startswith("(LLM"):
        # 抽取式降级
        extracted = ["## 摘要\n未配置 LLM，以下为命中的证据片段节选。\n"]
        for idx, block in enumerate(blocks, start=1):
            suffix = "…" if len(block) > 800 else ""
            extracted.append(f"### 片段{idx}\n> {block[:800]}{suffix}")
        answer = "\n\n".join(extracted)

    answer = f"{answer}\n" + "\n".join(format_reference_lines(ref_notes))
    return jsonify({"answer": answer, "references": metas[: len(blocks)]})
