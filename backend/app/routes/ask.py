"""Question answering route."""
from flask import Blueprint, jsonify, request

from app.agents import AnswerAgent, AnswerContext, route_question
from app.config import DEFAULT_TOPK
from app.langchain import RagResult, get_rag_agent
from app.tools import format_references, run_kg_query

ask_bp = Blueprint("ask", __name__)


@ask_bp.route("/ask", methods=["GET", "POST"])
def ask():
    """Router Agent → Tool → Answer Agent."""

    payload = request.get_json(silent=True) or {}
    query = request.args.get("q") or payload.get("q")
    topk_raw = request.args.get("k") or payload.get("k")
    try:
        topk = int(topk_raw) if topk_raw is not None else DEFAULT_TOPK
    except (TypeError, ValueError):
        topk = DEFAULT_TOPK

    if not query or not str(query).strip():
        return jsonify({"error": "q (question) is required"}), 400

    decision = route_question(str(query))

    graph_payload = {"facts": [], "context": "（知识图谱未查询）"}
    rag_blocks = []
    rag_metas = []
    numbered_context = "（未检索到正文片段）"
    ref_notes = []
    rag_result: RagResult | None = None

    rag_agent = get_rag_agent()

    if decision.strategy == "kg":
        graph_payload = run_kg_query(query, limit=topk)
    elif decision.strategy == "rag":
        rag_result = rag_agent.answer(
            str(query), graph_context="", topk=topk, strategy=decision.strategy, reason=decision.reason
        )
    else:
        graph_payload = run_kg_query(query, limit=topk)
        rag_result = rag_agent.answer(
            str(query),
            graph_context=graph_payload.get("context") or "（知识图谱未查询）",
            topk=topk,
            strategy=decision.strategy,
            reason=decision.reason,
        )

    if rag_result:
        rag_blocks = rag_result.blocks
        rag_metas = rag_result.references
        numbered_context = rag_result.numbered_context
        ref_notes = rag_result.reference_notes

    graph_context = graph_payload.get("context") or "（知识图谱暂无命中）"

    if rag_result:
        answer = rag_result.answer
        reference_lines = rag_result.reference_lines()
    else:
        ctx = AnswerContext(
            question=str(query),
            strategy=decision.strategy,
            reason=decision.reason,
            graph_context=graph_context,
            evidence_blocks=rag_blocks,
            numbered_context=numbered_context,
            references=rag_metas[: len(rag_blocks)],
        )

        agent = AnswerAgent()
        answer = agent.answer(ctx)
        reference_lines = format_references(ref_notes) if ref_notes else ""

    if reference_lines:
        answer = f"{answer}\n\n---\n## 参考片段\n{reference_lines}"

    return jsonify(
        {
            "answer": answer,
            "references": rag_metas[: len(rag_blocks)],
            "graph": graph_payload.get("facts", []),
            "strategy": decision.strategy,
            "reason": decision.reason,
            "cues": decision.cues,
        }
    )
