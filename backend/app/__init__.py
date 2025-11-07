"""Application factory for the backend service."""
from flask import Flask
from flask_cors import CORS

from app.routes import register_routes


def create_app() -> Flask:
    """Create and configure the Flask application."""

    app = Flask(__name__)
    CORS(app)
    register_routes(app)
    return app


app = create_app()

__all__ = ["create_app", "app"]
