"""Legacy wrapper for the ingestion pipeline.

The actual implementation now lives under :mod:`app.crawler.ingest` so it can
be reused by the crawler when ``run_ingest`` is enabled.
"""

from app.crawler.ingest import main as _main, run_ingest_pipeline

__all__ = ["run_ingest_pipeline", "main"]


def main() -> int:  # pragma: no cover - simple wrapper
    return _main()


if __name__ == "__main__":
    raise SystemExit(main())
