"""Service layer utilities for the backend application."""
from .retriever_service import (
    build_context,
    build_numbered_context,
    ensure_retriever,
    format_reference_lines,
    reload_retriever,
    search,
)

__all__ = [
    "build_context",
    "build_numbered_context",
    "ensure_retriever",
    "format_reference_lines",
    "reload_retriever",
    "search",
]
