"""Compatibility wrapper around :mod:`app.crawler.collector`."""
from app.crawler.collector import main

if __name__ == "__main__":
    raise SystemExit(main())
