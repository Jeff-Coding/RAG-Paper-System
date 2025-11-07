#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
paper_collector.py
------------------
Batch-collect open-access papers from arXiv, OpenAlex, and Semantic Scholar,
then store PDFs under data/pdf/, write/update metadata under data/metadata/,
and optionally trigger your RAG ingestion pipeline.

Dependencies:
  - requests
  - feedparser

Install:
  pip install requests feedparser

Examples:
  # basic
  python paper_collector.py --query "transformer" --max-per-source 100

  # multiple queries + year filter + provider filter
  python paper_collector.py --query "RAG;retrieval augmented generation" --year-min 2018 --providers arxiv,openalex

  # save to a custom folder and run your RAG ingest afterward
  python paper_collector.py --query "multimodal LLM" --out data/pdf --run-ingest

Notes:
  - Only open-access PDFs are downloaded.
  - De-duplication is by normalized title and SHA256 of file content.
  - Metadata is stored/updated at data/metadata/papers.jsonl
"""

import os
import re
import sys
import time
import json
import math
import glob
import random
import argparse
import hashlib
import logging
from types import SimpleNamespace
from dataclasses import dataclass, asdict
from typing import Any, Dict, List, Mapping, Optional, Union

# third-party
import requests
import feedparser

from urllib.parse import urlparse
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# ------------------------------
# Configuration (defaults)
# ------------------------------
DEFAULT_OUT_DIR = "data/pdf"
DEFAULT_META_DIR = "data/metadata"
DEFAULT_META_PATH = os.path.join(DEFAULT_META_DIR, "papers.jsonl")
DEFAULT_PROVIDERS = "arxiv,openalex,semanticscholar"
DEFAULT_MAX_PER_SOURCE = 100

# polite rate limiting
ARXIV_SLEEP = 0.5
OPENALEX_SLEEP = 0.5
S2_SLEEP = 0.5

# request timeouts
REQ_TIMEOUT = 15

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    datefmt="%H:%M:%S",
)

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


@dataclass
class CrawlerConfig:
    """Configuration for a crawling job."""

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
        """Create a configuration from a mapping-like object."""

        normalized = {k.replace("-", "_"): v for k, v in dict(data).items()}
        year_min = normalized.get("year_min")
        year_max = normalized.get("year_max")
        year_min = int(year_min) if year_min not in (None, "", "null") else None
        year_max = int(year_max) if year_max not in (None, "", "null") else None
        run_ingest_raw = normalized.get("run_ingest", False)
        if isinstance(run_ingest_raw, str):
            run_ingest = run_ingest_raw.lower() in {"1", "true", "yes", "y"}
        else:
            run_ingest = bool(run_ingest_raw)

        return cls(
            query=normalized["query"],
            providers=normalized.get("providers", DEFAULT_PROVIDERS),
            max_per_source=int(normalized.get("max_per_source", DEFAULT_MAX_PER_SOURCE)),
            year_min=year_min,
            year_max=year_max,
            out=normalized.get("out", DEFAULT_OUT_DIR),
            meta=normalized.get("meta", DEFAULT_META_PATH),
            run_ingest=run_ingest,
        )

    @classmethod
    def from_any(cls, config: Union["CrawlerConfig", argparse.Namespace, SimpleNamespace, Mapping[str, Any]]) -> "CrawlerConfig":
        """Normalize supported input formats into a :class:`CrawlerConfig`."""

        if isinstance(config, cls):
            return config
        if isinstance(config, (argparse.Namespace, SimpleNamespace)):
            return cls.from_mapping(vars(config))
        if isinstance(config, Mapping):
            return cls.from_mapping(config)
        raise TypeError(f"Unsupported crawler config type: {type(config)!r}")

# ------------------------------
# Utilities
# ------------------------------
def safe_filename(name: str, max_len: int = 120) -> str:
    name = re.sub(r"[\\/:*?\"<>|]+", "_", name)
    name = re.sub(r"\s+", " ", name).strip()
    if len(name) > max_len:
        name = name[:max_len].rstrip()
    return name

def norm_title(title: str) -> str:
    t = title.lower().strip()
    t = re.sub(r"\s+", " ", t)
    return t

def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()

def ensure_dirs(out_dir: str, meta_path: str):
    os.makedirs(out_dir, exist_ok=True)
    os.makedirs(os.path.dirname(meta_path), exist_ok=True)

def iter_existing_titles(meta_path: str) -> set:
    titles = set()
    if os.path.exists(meta_path):
        with open(meta_path, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    try:
                        obj = json.loads(line)
                        if "title" in obj:
                            titles.add(norm_title(obj["title"]))
                    except Exception:
                        continue
    return titles

def append_metadata(meta_path: str, papers: List[Paper], file_map: Dict[str, str]):
    with open(meta_path, "a", encoding="utf-8") as f:
        for p in papers:
            rec = asdict(p)
            rec["pdf_path"] = file_map.get(p.title)
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")

# ------------------------------
# Providers
# ------------------------------
def search_arxiv(query: str, max_n: int = 100, year_min: Optional[int] = None, year_max: Optional[int] = None) -> List[Paper]:
    logging.info(f"[arXiv] query={query!r}, max={max_n}")
    base = "http://export.arxiv.org/api/query"
    # arXiv API returns entries in pages (max 2000 total typically adequate). We'll fetch in chunks of 100.
    out = []
    start = 0
    per_page = 100
    while len(out) < max_n:
        n = min(per_page, max_n - len(out))
        url = f"{base}?search_query=all:{requests.utils.quote(query)}&start={start}&max_results={n}"
        feed = feedparser.parse(url)
        time.sleep(ARXIV_SLEEP)
        if not getattr(feed, "entries", None):
            break
        for e in feed.entries:
            title = e.title.strip()
            # arXiv year parsing
            year = None
            try:
                if hasattr(e, "published"):
                    year = int(e.published[:4])
            except Exception:
                pass
            if year_min and (year is not None) and year < year_min:
                continue
            if year_max and (year is not None) and year > year_max:
                continue
            # find pdf link
            pdf_url = None
            if hasattr(e, "links"):
                for link in e.links:
                    if link.get("type") == "application/pdf":
                        pdf_url = link.get("href")
                        break
            if not pdf_url and hasattr(e, "link"):
                # fallback: swap abs->pdf
                pdf_url = e.link.replace("/abs/", "/pdf/")
            authors = []
            if hasattr(e, "authors"):
                authors = [a.name for a in e.authors if hasattr(a, "name")]
            abstract = getattr(e, "summary", None)
            out.append(Paper(
                source="arxiv",
                title=title,
                year=year,
                url_pdf=pdf_url,
                url_landing=getattr(e, "link", None),
                authors=authors,
                venue="arXiv",
                doi=None,
                abstract=abstract,
                query=query
            ))
        if len(feed.entries) < n:
            break
        start += n
    return out

def search_openalex(query: str, max_n: int = 100, year_min: Optional[int] = None, year_max: Optional[int] = None) -> List[Paper]:
    logging.info(f"[OpenAlex] query={query!r}, max={max_n}")
    base = "https://api.openalex.org/works"
    out = []
    page = 1
    per_page = 50
    params = {
        "search": query,
        "page": page,
        "per_page": per_page,
        "sort": "relevance_score:desc"
    }
    if year_min or year_max:
        # Build a from_to filter
        if year_min and year_max:
            params["filter"] = f"from_publication_date:{year_min}-01-01,to_publication_date:{year_max}-12-31"
        elif year_min:
            params["filter"] = f"from_publication_date:{year_min}-01-01"
        elif year_max:
            params["filter"] = f"to_publication_date:{year_max}-12-31"
    session = requests.Session()
    while len(out) < max_n:
        params["page"] = page
        try:
            r = session.get(base, params=params, timeout=REQ_TIMEOUT)
            r.raise_for_status()
            data = r.json()
        except Exception as e:
            logging.warning(f"[OpenAlex] page={page} error: {e}")
            break
        results = data.get("results", [])
        if not results:
            break
        for w in results:
            oa = w.get("open_access", {}) or {}
            pdf_url = oa.get("oa_url")
            # ensure OA
            if not pdf_url:
                continue
            year = w.get("publication_year")
            if year_min and (year is not None) and year < year_min:
                continue
            if year_max and (year is not None) and year > year_max:
                continue
            title = w.get("title") or ""
            authors = []
            for auth in w.get("authorships", []):
                author = auth.get("author", {})
                if author.get("display_name"):
                    authors.append(author["display_name"])
            out.append(Paper(
                source="openalex",
                title=title,
                year=year,
                url_pdf=pdf_url,
                url_landing=(w.get("primary_location") or {}).get("landing_page_url"),
                authors=authors,
                venue=(w.get("host_venue") or {}).get("display_name"),
                doi=(w.get("doi") or None),
                abstract=(w.get("abstract") or None),
                query=query
            ))
        page += 1
        time.sleep(OPENALEX_SLEEP)
        if len(results) < per_page:
            break
    return out[:max_n]

def search_semanticscholar(query: str, max_n: int = 100, year_min: Optional[int] = None, year_max: Optional[int] = None) -> List[Paper]:
    logging.info(f"[SemanticScholar] query={query!r}, max={max_n}")
    base = "https://api.semanticscholar.org/graph/v1/paper/search"
    fields = "title,year,openAccessPdf,url,venue,authors,abstract,externalIds"
    out = []
    session = requests.Session()

    # Retry & respect Retry-After
    retry = Retry(
        total=5, connect=3, read=3, backoff_factor=0.8,
        status_forcelist=[408, 429, 500, 502, 503, 504],
        allowed_methods=["GET"],
        respect_retry_after_header=True,
    )
    session.mount("https://", HTTPAdapter(max_retries=retry))
    session.mount("http://", HTTPAdapter(max_retries=retry))

    headers = {
        "User-Agent": "paper-collector/1.0",
        "Accept": "application/json",
    }
    api_key = os.getenv("SEMANTIC_SCHOLAR_API_KEY")
    if api_key:
        headers["x-api-key"] = api_key

    per_page = 25  # 更稳
    page = 1
    while len(out) < max_n:
        params = {
            "query": query,
            "limit": per_page,
            "offset": (page-1)*per_page,
            "fields": fields
        }
        try:
            r = session.get(base, params=params, timeout=(5, 30), headers=headers)
            if r.status_code == 429:
                wait = int(r.headers.get("Retry-After", "60") or "60")
                logging.warning(f"[S2] 429 rate limited. Sleeping {wait}s...")
                time.sleep(wait)
                continue
            r.raise_for_status()
            data = r.json()
        except Exception as e:
            logging.warning(f"[S2] page={page} error: {e}")
            break

        papers = data.get("data", []) or []
        if not papers:
            break

        for p in papers:
            pdf_url = (p.get("openAccessPdf") or {}).get("url")
            if not pdf_url:
                continue
            year = p.get("year")
            if year_min and (year is not None) and year < year_min:
                continue
            if year_max and (year is not None) and year > year_max:
                continue
            title = p.get("title") or ""
            authors = [a.get("name") for a in (p.get("authors") or []) if a.get("name")]
            doi = (p.get("externalIds") or {}).get("DOI") if isinstance(p.get("externalIds"), dict) else None
            out.append(Paper(
                source="semanticscholar",
                title=title,
                year=year,
                url_pdf=pdf_url,
                url_landing=p.get("url"),
                authors=authors,
                venue=p.get("venue"),
                doi=doi,
                abstract=p.get("abstract"),
                query=query
            ))

        page += 1
        time.sleep(S2_SLEEP)
        if len(papers) < per_page:
            break

    return out[:max_n]

# ------------------------------
# Download + De-dup
# ------------------------------
# 增强配置
HEADERS_BASE = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                   "AppleWebKit/537.36 (KHTML, like Gecko) "
                   "Chrome/120.0.0.0 Safari/537.36"),
    "Accept": "application/pdf,application/octet-stream;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9,zh-CN;q=0.8",
}

def make_session() -> requests.Session:
    s = requests.Session()
    retries = Retry(
        total=5,
        connect=3,
        read=3,
        backoff_factor=0.8,
        status_forcelist=[403,408,429,500,502,503,504],
        allowed_methods=["HEAD","GET","OPTIONS"]
    )
    s.mount("http://", HTTPAdapter(max_retries=retries, pool_maxsize=10))
    s.mount("https://", HTTPAdapter(max_retries=retries, pool_maxsize=10))
    return s

def is_pdf_response(resp, first_chunk: bytes) -> bool:
    ctype = (resp.headers.get("Content-Type") or "").lower()
    return ("application/pdf" in ctype) or first_chunk.startswith(b"%PDF")

def download_pdf(url: str, path: str) -> Optional[str]:
    """Enhanced PDF downloader with headers, retry, and validation."""
    session = make_session()
    headers = HEADERS_BASE.copy()
    domain = urlparse(url).netloc
    headers["Referer"] = f"https://{domain}/"
    time.sleep(0.6 + random.random() * 0.6)  # polite sleep

    try:
        with session.get(url, headers=headers, stream=True,
                         timeout=(5, 60), allow_redirects=True) as r:
            first_chunk = next(r.iter_content(8192), b"")
            if not is_pdf_response(r, first_chunk):
                logging.warning(
                    f"Not a PDF: {url} type={r.headers.get('Content-Type')} "
                    f"status={r.status_code} size={len(first_chunk)}"
                )
                return None

            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "wb") as f:
                f.write(first_chunk)
                for chunk in r.iter_content(8192):
                    if chunk:
                        f.write(chunk)

        # Verify again
        with open(path, "rb") as f:
            head = f.read(4)
            if not head.startswith(b"%PDF"):
                logging.warning(f"Invalid PDF magic header: {url}")
                os.remove(path)
                return None
            data = f.read()
            return sha256_bytes(head + data)

    except requests.exceptions.SSLError as e:
        logging.warning(f"SSL error for {url}: {e}")
        return None
    except Exception as e:
        logging.warning(f"Download failed {url}: {e}")
        return None

def collect_papers(queries: List[str], providers: List[str], max_per_source: int,
                   year_min: Optional[int], year_max: Optional[int]) -> List[Paper]:
    all_papers: List[Paper] = []
    for q in queries:
        if "arxiv" in providers:
            all_papers.extend(search_arxiv(q, max_per_source, year_min, year_max))
        if "openalex" in providers:
            all_papers.extend(search_openalex(q, max_per_source, year_min, year_max))
        if "semanticscholar" in providers:
            all_papers.extend(search_semanticscholar(q, max_per_source, year_min, year_max))
    # basic title-level de-dup (keep first occurrence)
    seen_titles = set()
    unique = []
    for p in all_papers:
        t = norm_title(p.title)
        if not t or t in seen_titles:
            continue
        seen_titles.add(t)
        unique.append(p)
    return unique

def run(config: Union[CrawlerConfig, argparse.Namespace, SimpleNamespace, Mapping[str, Any]]) -> Dict[str, Any]:
    """Execute the crawling pipeline and return a summary dict."""

    cfg = CrawlerConfig.from_any(config)

    ensure_dirs(cfg.out, cfg.meta)
    providers = [p.strip().lower() for p in cfg.providers.split(",") if p.strip()]
    queries = [q.strip() for q in cfg.query.split(";") if q.strip()]

    # Load existing titles to skip
    existing_titles = iter_existing_titles(cfg.meta)
    logging.info(f"Existing metadata titles: {len(existing_titles)}")

    # 1) Search
    papers = collect_papers(queries, providers, cfg.max_per_source, cfg.year_min, cfg.year_max)
    logging.info(f"Found {len(papers)} candidate OA papers after title de-dup.")

    # 2) Download with de-dup by title + content hash
    file_map: Dict[str, str] = {}
    hash_set = set()
    downloaded = []
    for p in papers:
        nt = norm_title(p.title)
        if nt in existing_titles:
            logging.info(f"Skip (exists in metadata): {p.title}")
            continue
        if not p.url_pdf:
            continue
        fname = safe_filename(p.title) + ".pdf"
        fpath = os.path.join(cfg.out, fname)
        if os.path.exists(fpath):
            # calculate hash to avoid duplicating same content under different names
            try:
                with open(fpath, "rb") as fr:
                    h = sha256_bytes(fr.read())
                if h in hash_set:
                    logging.info(f"Skip (same content hash): {p.title}")
                    continue
                else:
                    hash_set.add(h)
                    file_map[p.title] = fpath
                    downloaded.append(p)
                    continue
            except Exception:
                pass
        h = download_pdf(p.url_pdf, fpath)
        if not h:
            continue
        if h in hash_set:
            # same content duplicate -> remove the file we just wrote
            try:
                os.remove(fpath)
            except Exception:
                pass
            logging.info(f"Skip (hash duplicate): {p.title}")
            continue
        hash_set.add(h)
        file_map[p.title] = fpath
        downloaded.append(p)

    logging.info(f"Downloaded new PDFs: {len(downloaded)}")
    # 3) Append metadata
    metadata_written = False
    if downloaded:
        append_metadata(cfg.meta, downloaded, file_map)
        metadata_written = True
        logging.info(f"Metadata appended -> {cfg.meta}")

    # 4) Optionally run ingest
    ingest_ran = False
    ingest_summary: Optional[Dict[str, Any]] = None
    if cfg.run_ingest:
        logging.info("Running ingest pipeline...")
        try:
            from .ingest import run_ingest_pipeline  # local import to avoid heavy deps

            ingest_summary = run_ingest_pipeline(pdf_dir=cfg.out, progress=False)
        except Exception as exc:  # pragma: no cover - defensive
            logging.exception("Ingest pipeline failed: %s", exc)
        else:
            ingest_ran = True
            logging.info("Ingest pipeline finished.")

    return {
        "queries": queries,
        "providers": providers,
        "candidates": len(papers),
        "downloaded": len(downloaded),
        "metadata_written": metadata_written,
        "ingest_ran": ingest_ran,
        "ingest_summary": ingest_summary,
    }

def build_argparser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description="Batch-collect OA papers and integrate with your RAG index.")
    ap.add_argument("--query", required=True, help="Search keywords; use ';' to separate multiple queries.")
    ap.add_argument("--providers", default=DEFAULT_PROVIDERS,
                    help="Comma-separated providers: arxiv,openalex,semanticscholar")
    ap.add_argument("--max-per-source", type=int, default=DEFAULT_MAX_PER_SOURCE,
                    help="Max results per provider per query.")
    ap.add_argument("--year-min", type=int, default=None, help="Minimum publication year.")
    ap.add_argument("--year-max", type=int, default=None, help="Maximum publication year.")
    ap.add_argument("--out", default=DEFAULT_OUT_DIR, help="Directory to store PDFs.")
    ap.add_argument("--meta", default=DEFAULT_META_PATH, help="Path to metadata JSONL.")
    ap.add_argument("--run-ingest", action="store_true", help="Run your ingest step after downloads.")
    return ap


def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    return build_argparser().parse_args(argv)


def main(argv: Optional[List[str]] = None) -> int:
    try:
        args = parse_args(argv)
        summary = run(args)
        logging.info("Crawler finished: %s", json.dumps(summary, ensure_ascii=False))
        return 0
    except KeyboardInterrupt:
        print("Interrupted by user.")
        return 130
    except Exception as exc:
        logging.exception(exc)
        return 1


if __name__ == "__main__":
    sys.exit(main())


__all__ = [
    "CrawlerConfig",
    "DEFAULT_OUT_DIR",
    "DEFAULT_META_DIR",
    "DEFAULT_META_PATH",
    "DEFAULT_PROVIDERS",
    "DEFAULT_MAX_PER_SOURCE",
    "build_argparser",
    "collect_papers",
    "main",
    "parse_args",
    "run",
]
