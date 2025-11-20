"""Question answering route."""
from flask import Blueprint, jsonify, request

from app.agents import AnswerAgent, AnswerContext, route_question
from app.config import DEFAULT_TOPK
from app.tools import format_references, run_hybrid_query, run_kg_query, run_rag_query

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

    if decision.strategy == "kg":
        graph_payload = run_kg_query(query, limit=topk)
    elif decision.strategy == "rag":
        rag = run_rag_query(query, topk=topk)
        rag_blocks = rag.blocks
        rag_metas = rag.metas
        numbered_context = rag.numbered_context
        ref_notes = rag.reference_notes
    else:
        hybrid = run_hybrid_query(query, topk=topk)
        graph_payload = hybrid["kg"]
        rag = hybrid["rag"]
        rag_blocks = rag.blocks
        rag_metas = rag.metas
        numbered_context = rag.numbered_context
        ref_notes = rag.reference_notes

    graph_context = graph_payload.get("context") or "（知识图谱暂无命中）"

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
