"""Flask blueprints for the backend APIs."""
from flask import Flask

from .ask import ask_bp
from .crawl import crawl_bp


def register_routes(app: Flask) -> None:
    """Register all API blueprints on the provided Flask app."""

    app.register_blueprint(ask_bp)
    app.register_blueprint(crawl_bp)


__all__ = ["register_routes", "ask_bp", "crawl_bp"]
