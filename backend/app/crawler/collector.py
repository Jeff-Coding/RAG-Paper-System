"""Paper crawler rebuilt on top of crawl4ai with knowledge-graph hooks."""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import inspect
import json
import logging
import os
import re
from dataclasses import asdict, dataclass
from types import SimpleNamespace
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Union
from urllib.parse import quote_plus

import feedparser

from app.config import GRAPH_PATH, PAPER_METADATA_PATH, RAW_PDF_DIR
from app.graph import build_graph_from_metadata
from app.utils import extract_keywords

LOGGER = logging.getLogger(__name__)

BACKEND_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
DEFAULT_OUT_DIR = str(RAW_PDF_DIR)
DEFAULT_META_PATH = str(PAPER_METADATA_PATH)
DEFAULT_PROVIDERS = "arxiv,openalex,semanticscholar"
DEFAULT_MAX_PER_SOURCE = 50

REQ_TIMEOUT = 20


@dataclass
class Paper:
    source: str
    title: str
    year: Optional[int]
    url_pdf: Optional[str]
    url_landing: Optional[str]
    authors: List[str]
    venue: Optional[str]
    doi: Optional[str]
    abstract: Optional[str]
    query: str
    keywords: List[str]

    def to_record(self, pdf_path: Optional[str] = None) -> Dict[str, Any]:
        rec = asdict(self)
        if pdf_path:
            rec["pdf_path"] = pdf_path
        return rec


@dataclass
class CrawlerConfig:
    query: str
    providers: str = DEFAULT_PROVIDERS
    max_per_source: int = DEFAULT_MAX_PER_SOURCE
    year_min: Optional[int] = None
    year_max: Optional[int] = None
    out: str = DEFAULT_OUT_DIR
    meta: str = DEFAULT_META_PATH
    run_ingest: bool = False

    @classmethod
    def from_mapping(cls, data: Mapping[str, Any]) -> "CrawlerConfig":
        normalized = {k.replace("-", "_"): v for k, v in dict(data).items()}
        year_min = normalized.get("year_min")
        year_max = normalized.get("year_max")
        year_min = int(year_min) if year_min not in (None, "", "null") else None
        year_max = int(year_max) if year_max not in (None, "", "null") else None
        run_ingest = normalized.get("run_ingest", False)
        if isinstance(run_ingest, str):
            run_ingest = run_ingest.lower() in {"1", "true", "yes", "y"}
        return cls(
            query=str(normalized["query"]).strip(),
            providers=normalized.get("providers", DEFAULT_PROVIDERS),
            max_per_source=int(normalized.get("max_per_source", DEFAULT_MAX_PER_SOURCE)),
            year_min=year_min,
            year_max=year_max,
            out=normalized.get("out", DEFAULT_OUT_DIR),
            meta=normalized.get("meta", DEFAULT_META_PATH),
            run_ingest=bool(run_ingest),
        )

    @classmethod
    def from_any(
        cls,
        config: Union["CrawlerConfig", argparse.Namespace, SimpleNamespace, Mapping[str, Any]],
    ) -> "CrawlerConfig":
        if isinstance(config, cls):
            return config
        if isinstance(config, (argparse.Namespace, SimpleNamespace)):
            return cls.from_mapping(vars(config))
        if isinstance(config, Mapping):
            return cls.from_mapping(config)
        raise TypeError(f"Unsupported crawler config: {type(config)!r}")


class Crawl4AIClient:
    """Wrapper around crawl4ai with graceful fallback to requests.

    The official tutorial (https://crawl4ai.docslib.dev/) recommends the async
    crawler API, so we expose synchronous helpers backed by ``asyncio`` and only
    fall back to plain ``requests`` when crawl4ai is not available.
    """

    def __init__(self):
        self._headers = {
            "User-Agent": "RAG-Paper-Crawler/1.0 (+https://github.com/)",
            "Accept": "*/*",
        }
        self._crawl4ai = None
        self._async_crawler_cls = None
        self._browser_cfg_cls = None
        self._run_cfg_cls = None
        self._cache_mode = None
        self._import_crawl4ai()

    def _import_crawl4ai(self):
        try:
            import crawl4ai  # type: ignore
        except Exception as exc:  # pragma: no cover - optional dependency
            LOGGER.warning("crawl4ai not available, fallback to requests: %s", exc)
            self._crawl4ai = None
            return
        self._crawl4ai = crawl4ai
        self._async_crawler_cls = getattr(crawl4ai, "AsyncWebCrawler", None)
        self._browser_cfg_cls = getattr(crawl4ai, "BrowserConfig", None)
        self._run_cfg_cls = getattr(crawl4ai, "CrawlerRunConfig", None)
        self._cache_mode = getattr(crawl4ai, "CacheMode", None)

    # ------------------------------------------------------------------
    def fetch_text(self, url: str, *, timeout: int = REQ_TIMEOUT) -> str:
        if self._async_crawler_cls is not None:
            try:
                return asyncio.run(self._fetch_text_via_crawl4ai(url, timeout=timeout))
            except Exception as exc:  # pragma: no cover - defensive
                LOGGER.warning("crawl4ai fetch_text fallback for %s: %s", url, exc)
        return self._fetch_text_via_requests(url, timeout=timeout)

    def fetch_binary(self, url: str, *, timeout: int = REQ_TIMEOUT) -> bytes:
        # crawl4ai focuses on HTML crawling; PDF fetching is more reliable via requests
        # but we still honor the async crawler if it is available
        if self._async_crawler_cls is not None:
            try:
                return asyncio.run(self._fetch_bytes_via_crawl4ai(url, timeout=timeout))
            except Exception as exc:  # pragma: no cover - defensive
                LOGGER.warning("crawl4ai fetch_binary fallback for %s: %s", url, exc)
        return self._fetch_bytes_via_requests(url, timeout=timeout)

    # -- crawl4ai helpers ------------------------------------------------
    async def _fetch_text_via_crawl4ai(self, url: str, *, timeout: int) -> str:
        crawler = self._build_crawler()
        run_cfg = self._build_run_config(timeout=timeout)
        async with crawler:
            result = await self._run_crawl(crawler, url, run_cfg)
        text = self._result_to_text(result)
        if not text:
            raise RuntimeError("crawl4ai returned empty payload")
        return text

    async def _fetch_bytes_via_crawl4ai(self, url: str, *, timeout: int) -> bytes:
        crawler = self._build_crawler()
        run_cfg = self._build_run_config(timeout=timeout)
        async with crawler:
            result = await self._run_crawl(crawler, url, run_cfg)
        blob = self._result_to_bytes(result)
        if not blob:
            raise RuntimeError("crawl4ai returned empty bytes")
        return blob

    def _build_crawler(self):
        if self._async_crawler_cls is None:
            raise RuntimeError("crawl4ai AsyncWebCrawler missing")
        if self._browser_cfg_cls:
            browser_cfg = self._browser_cfg_cls(headless=True, extra_headers=self._headers)
            return self._async_crawler_cls(config=browser_cfg)
        return self._async_crawler_cls()

    def _build_run_config(self, *, timeout: int):
        if not self._run_cfg_cls:
            return None
        sig = inspect.signature(self._run_cfg_cls)
        kwargs: Dict[str, Any] = {}
        if "wait_for" in sig.parameters:
            kwargs["wait_for"] = "networkidle"
        if "cache_mode" in sig.parameters and self._cache_mode is not None:
            bypass = getattr(self._cache_mode, "BYPASS", None)
            if bypass:
                kwargs["cache_mode"] = bypass
        if "timeout" in sig.parameters:
            kwargs["timeout"] = timeout
        elif "timeout_ms" in sig.parameters:
            kwargs["timeout_ms"] = timeout * 1000
        return self._run_cfg_cls(**kwargs)

    async def _run_crawl(self, crawler, url: str, run_cfg):
        if run_cfg is not None:
            return await crawler.arun(url=url, config=run_cfg)
        return await crawler.arun(url=url)

    @staticmethod
    def _result_to_text(result) -> str:
        for attr in (
            "markdown",
            "raw_markdown",
            "markdown_v2",
            "text",
            "content",
            "raw_html",
            "html",
        ):
            value = getattr(result, attr, None)
            if isinstance(value, str) and value.strip():
                return value
        if isinstance(result, str):
            return result
        if isinstance(result, bytes):
            return result.decode("utf-8", errors="ignore")
        return ""

    @staticmethod
    def _result_to_bytes(result) -> bytes:
        for attr in ("binary", "raw_bytes", "content"):
            value = getattr(result, attr, None)
            if isinstance(value, (bytes, bytearray)):
                return bytes(value)
        text = Crawl4AIClient._result_to_text(result)
        return text.encode("utf-8")

    # -- requests fallback ----------------------------------------------
    def _fetch_text_via_requests(self, url: str, *, timeout: int) -> str:
        import requests

        resp = requests.get(url, headers=self._headers, timeout=timeout)
        resp.raise_for_status()
        return resp.text

    def _fetch_bytes_via_requests(self, url: str, *, timeout: int) -> bytes:
        import requests

        resp = requests.get(url, headers=self._headers, timeout=timeout)
        resp.raise_for_status()
        return resp.content


# ---------------------------------------------------------------------------
# Utilities


def safe_filename(name: str, max_len: int = 120) -> str:
    name = re.sub(r"[\\/:*?\"<>|]+", "_", name)
    name = re.sub(r"\s+", " ", name).strip()
    if len(name) > max_len:
        name = name[:max_len].rstrip()
    return name or "paper"


def norm_title(title: str) -> str:
    return re.sub(r"\s+", " ", title).strip().lower()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def ensure_dirs(out_dir: str, meta_path: str):
    os.makedirs(out_dir, exist_ok=True)
    os.makedirs(os.path.dirname(meta_path), exist_ok=True)
    os.makedirs(os.path.dirname(GRAPH_PATH), exist_ok=True)


def iter_existing_titles(meta_path: str) -> set[str]:
    titles: set[str] = set()
    if os.path.exists(meta_path):
        with open(meta_path, "r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if "title" in obj:
                    titles.add(norm_title(obj["title"]))
    return titles


def append_metadata(meta_path: str, papers: List[Paper], file_map: Dict[str, str]):
    with open(meta_path, "a", encoding="utf-8") as fh:
        for paper in papers:
            fh.write(json.dumps(paper.to_record(file_map.get(paper.title)), ensure_ascii=False) + "\n")


def download_pdf(client: Crawl4AIClient, url: str, path: str) -> Optional[str]:
    try:
        blob = client.fetch_binary(url)
    except Exception as exc:
        LOGGER.warning("Failed to download %s: %s", url, exc)
        return None
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as handle:
        handle.write(blob)
    return sha256_bytes(blob)


# ---------------------------------------------------------------------------
# Providers powered by crawl4ai HTTP fetches


def search_arxiv(
    client: Crawl4AIClient,
    query: str,
    max_n: int,
    year_min: Optional[int] = None,
    year_max: Optional[int] = None,
) -> List[Paper]:
    LOGGER.info("[crawl4ai][arxiv] %s", query)
    base = "http://export.arxiv.org/api/query"
    per_page = min(max_n, 100)
    collected: List[Paper] = []
    start = 0
    while len(collected) < max_n:
        url = (
            f"{base}?search_query=all:{quote_plus(query)}&start={start}&max_results={per_page}&"
            "sortBy=submittedDate"
        )
        text = client.fetch_text(url)
        feed = feedparser.parse(text)
        for entry in feed.entries:
            title = entry.get("title", "").strip()
            if not title:
                continue
            published = entry.get("published", "")[:4]
            year = int(published) if published.isdigit() else None
            if year_min and year and year < year_min:
                continue
            if year_max and year and year > year_max:
                continue
            authors = [a.get("name", "").strip() for a in entry.get("authors", []) if a.get("name")]
            summary = entry.get("summary", "").strip()
            pdf_url = None
            landing = entry.get("link")
            for link in entry.get("links", []):
                if link.get("type") == "application/pdf":
                    pdf_url = link.get("href")
                    break
            keywords = extract_keywords(f"{title} {summary}", boost=[query])
            collected.append(
                Paper(
                    source="arxiv",
                    title=title,
                    year=year,
                    url_pdf=pdf_url,
                    url_landing=landing,
                    authors=authors,
                    venue=entry.get("arxiv_journal_ref"),
                    doi=entry.get("arxiv_doi"),
                    abstract=summary,
                    query=query,
                    keywords=keywords,
                )
            )
            if len(collected) >= max_n:
                break
        if len(feed.entries) < per_page:
            break
        start += per_page
    return collected


def search_openalex(
    client: Crawl4AIClient,
    query: str,
    max_n: int,
    year_min: Optional[int] = None,
    year_max: Optional[int] = None,
) -> List[Paper]:
    LOGGER.info("[crawl4ai][openalex] %s", query)
    base = "https://api.openalex.org/works"
    filters = ["is_oa:true"]
    if year_min and year_max:
        filters.append(f"from_publication_date:{year_min}-01-01")
        filters.append(f"to_publication_date:{year_max}-12-31")
    elif year_min:
        filters.append(f"from_publication_date:{year_min}-01-01")
    elif year_max:
        filters.append(f"to_publication_date:{year_max}-12-31")
    url = f"{base}?search={quote_plus(query)}&per-page={max_n}&filter={','.join(filters)}"
    payload = json.loads(client.fetch_text(url))
    results = []
    for item in payload.get("results", []):
        year = item.get("publication_year")
        if year_min and year and year < year_min:
            continue
        if year_max and year and year > year_max:
            continue
        oa = item.get("open_access", {}) or {}
        pdf_url = oa.get("pdf_url") or (item.get("primary_location") or {}).get("pdf_url")
        summary = (item.get("abstract_inverted_index") or {})
        if isinstance(summary, dict):
            # flatten inverted index
            tokens = sorted(((min(pos), word) for word, pos in summary.items()))
            abstract = " ".join(word for _, word in tokens)
        else:
            abstract = ""
        authors = [auth.get("author", {}).get("display_name", "") for auth in item.get("authorships", [])]
        authors = [a for a in authors if a]
        keywords = extract_keywords(f"{item.get('display_name', '')} {abstract}", boost=[query])
        results.append(
            Paper(
                source="openalex",
                title=item.get("display_name", ""),
                year=year,
                url_pdf=pdf_url,
                url_landing=(item.get("primary_location") or {}).get("landing_page_url"),
                authors=authors,
                venue=item.get("host_venue", {}).get("display_name"),
                doi=item.get("doi"),
                abstract=abstract,
                query=query,
                keywords=keywords,
            )
        )
        if len(results) >= max_n:
            break
    return results


def search_semanticscholar(
    client: Crawl4AIClient,
    query: str,
    max_n: int,
    year_min: Optional[int] = None,
    year_max: Optional[int] = None,
) -> List[Paper]:
    LOGGER.info("[crawl4ai][semanticscholar] %s", query)
    base = "https://api.semanticscholar.org/graph/v1/paper/search"
    fields = "title,year,venue,authors,abstract,externalIds,url,openAccessPdf"
    url = f"{base}?query={quote_plus(query)}&limit={max_n}&fields={fields}"
    payload = json.loads(client.fetch_text(url))
    results = []
    for item in payload.get("data", []):
        year = item.get("year")
        if year_min and year and year < year_min:
            continue
        if year_max and year and year > year_max:
            continue
        pdf_url = (item.get("openAccessPdf") or {}).get("url")
        if not pdf_url:
            ext = item.get("externalIds") or {}
            pdf_url = ext.get("ArXiv")
        authors = [a.get("name", "") for a in item.get("authors", []) if a.get("name")]
        abstract = item.get("abstract")
        keywords = extract_keywords(f"{item.get('title', '')} {abstract}", boost=[query])
        results.append(
            Paper(
                source="semanticscholar",
                title=item.get("title", ""),
                year=year,
                url_pdf=pdf_url,
                url_landing=item.get("url"),
                authors=authors,
                venue=item.get("venue"),
                doi=(item.get("externalIds") or {}).get("DOI"),
                abstract=abstract,
                query=query,
                keywords=keywords,
            )
        )
        if len(results) >= max_n:
            break
    return results


PROVIDER_REGISTRY = {
    "arxiv": search_arxiv,
    "openalex": search_openalex,
    "semanticscholar": search_semanticscholar,
}


def collect_papers(
    client: Crawl4AIClient,
    queries: Sequence[str],
    providers: Sequence[str],
    max_per_source: int,
    year_min: Optional[int],
    year_max: Optional[int],
) -> List[Paper]:
    seen = set()
    papers: List[Paper] = []
    for query in queries:
        for provider in providers:
            func = PROVIDER_REGISTRY.get(provider)
            if not func:
                LOGGER.warning("Unknown provider: %s", provider)
                continue
            for paper in func(client, query, max_per_source, year_min, year_max):
                key = (provider, norm_title(paper.title))
                if key in seen:
                    continue
                seen.add(key)
                papers.append(paper)
    return papers


# ---------------------------------------------------------------------------
# Pipeline entry point


def run(config: Union[CrawlerConfig, argparse.Namespace, SimpleNamespace, Mapping[str, Any]]):
    cfg = CrawlerConfig.from_any(config)
    ensure_dirs(cfg.out, cfg.meta)

    providers = [p.strip().lower() for p in cfg.providers.split(",") if p.strip()]
    queries = [q.strip() for q in cfg.query.split(";") if q.strip()]
    if not queries:
        raise ValueError("query must contain at least one keyword")

    client = Crawl4AIClient()

    existing_titles = iter_existing_titles(cfg.meta)
    LOGGER.info("Existing metadata titles: %s", len(existing_titles))

    papers = collect_papers(client, queries, providers, cfg.max_per_source, cfg.year_min, cfg.year_max)
    LOGGER.info("Collected %s papers", len(papers))

    hash_set: set[str] = set()
    downloaded: List[Paper] = []
    file_map: Dict[str, str] = {}
    for paper in papers:
        if not paper.url_pdf:
            continue
        title_key = norm_title(paper.title)
        if title_key in existing_titles:
            LOGGER.info("Skip existing metadata entry: %s", paper.title)
            continue
        fname = safe_filename(paper.title) + ".pdf"
        fpath = os.path.join(cfg.out, fname)
        if os.path.exists(fpath):
            with open(fpath, "rb") as handle:
                digest = sha256_bytes(handle.read())
            if digest in hash_set:
                continue
            hash_set.add(digest)
            file_map[paper.title] = fpath
            downloaded.append(paper)
            continue
        digest = download_pdf(client, paper.url_pdf, fpath)
        if not digest:
            continue
        if digest in hash_set:
            try:
                os.remove(fpath)
            except OSError:
                pass
            continue
        hash_set.add(digest)
        file_map[paper.title] = fpath
        downloaded.append(paper)

    metadata_written = False
    if downloaded:
        append_metadata(cfg.meta, downloaded, file_map)
        metadata_written = True
        LOGGER.info("Metadata appended to %s", cfg.meta)

    graph_summary = build_graph_from_metadata(cfg.meta, graph_path=GRAPH_PATH, search_terms=queries)
    try:
        from app.services import reload_graph_index

        reload_graph_index()
    except Exception:  # pragma: no cover - optional
        pass

    ingest_summary = None
    ingest_ran = False
    if cfg.run_ingest and downloaded:
        LOGGER.info("Running ingest pipeline ...")
        from .ingest import run_ingest_pipeline

        ingest_summary = run_ingest_pipeline(pdf_dir=cfg.out, progress=False)
        ingest_ran = True

    return {
        "queries": queries,
        "providers": providers,
        "candidates": len(papers),
        "downloaded": len(downloaded),
        "metadata_written": metadata_written,
        "knowledge_graph": graph_summary,
        "ingest_ran": ingest_ran,
        "ingest_summary": ingest_summary,
    }


# ---------------------------------------------------------------------------
# CLI helpers


def build_argparser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description="Collect papers via crawl4ai and update the RAG index.")
    ap.add_argument("--query", required=True, help="Search keywords; separate multiple queries with ';'.")
    ap.add_argument("--providers", default=DEFAULT_PROVIDERS, help="Comma-separated providers")
    ap.add_argument("--max-per-source", type=int, default=DEFAULT_MAX_PER_SOURCE)
    ap.add_argument("--year-min", type=int, default=None)
    ap.add_argument("--year-max", type=int, default=None)
    ap.add_argument("--out", default=DEFAULT_OUT_DIR, help="Directory for PDFs")
    ap.add_argument("--meta", default=DEFAULT_META_PATH, help="Metadata JSONL path")
    ap.add_argument("--run-ingest", action="store_true", help="Run ingestion after download")
    return ap


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    return build_argparser().parse_args(argv)


def main(argv: Optional[Sequence[str]] = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
    args = parse_args(argv)
    summary = run(args)
    LOGGER.info("Crawler finished: %s", json.dumps(summary, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
