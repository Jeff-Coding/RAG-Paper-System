"""Paper crawling route."""
from flask import Blueprint, jsonify, request

from app.crawler.collector import (
    CrawlerConfig,
    DEFAULT_MAX_PER_SOURCE,
    DEFAULT_PROVIDERS,
    run,
)
from app.services import reload_retriever

crawl_bp = Blueprint("crawl", __name__)


@crawl_bp.route("/crawl", methods=["POST"])
def crawl():
    """Trigger the crawler with the provided configuration."""

    body = request.get_json(force=True, silent=False) or {}
    query = body.get("query")
    if not query or not str(query).strip():
        return jsonify({"error": "query is required"}), 400

    config_data = {
        "query": query,
        "providers": body.get("providers", DEFAULT_PROVIDERS),
        "max_per_source": body.get("max_per_source", DEFAULT_MAX_PER_SOURCE),
        "year_min": body.get("year_min"),
        "year_max": body.get("year_max"),
        "run_ingest": bool(body.get("run_ingest", False)),
    }
    if "out" in body:
        config_data["out"] = body["out"]
    if "meta" in body:
        config_data["meta"] = body["meta"]

    try:
        summary = run(CrawlerConfig.from_mapping(config_data))
        if summary.get("ingest_ran"):
            reload_retriever()
        return jsonify({"status": "ok", "summary": summary})
    except Exception as exc:  # pragma: no cover - defensive
        return jsonify({"status": "error", "message": str(exc)}), 500
