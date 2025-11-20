import os, json, hashlib, re
from typing import List, Sequence
from .config import TEXT_DIR
import json
import os
import re
import hashlib
from typing import List, Sequence

import jieba

def write_jsonl(path, rows):
    with open(path, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

def read_jsonl(path):
    out = []
    if not os.path.exists(path):
        return out
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            out.append(json.loads(line))
    return out

def md5(s: str) -> str:
    return hashlib.md5(s.encode("utf-8")).hexdigest()

def clean_text(t: str) -> str:
    # remove excessive spaces and artifacts
    t = re.sub(r"[ \t]+", " ", t)
    t = re.sub(r"\n{3,}", "\n\n", t)
    return t.strip()

def tokenize_for_bm25(text: str) -> List[str]:
    # Chinese-aware simple tokenization
    # Split by jieba for CJK; also split on spaces for English.
    # Lowercase latin words.
    seg = list(jieba.cut(text))
    tokens = []
    for tok in seg:
        if tok.strip():
            tokens.append(tok.lower())
    return tokens


def extract_keywords(text: str, max_keywords: int = 8, *, boost: Sequence[str] | None = None) -> List[str]:
    """Derive lightweight keywords from free-form text.

    The implementation intentionally avoids heavy NLP dependencies so it can
    run inside the crawler without GPU/torch.
    """

    tokens = tokenize_for_bm25(text)
    seen = []
    boost = boost or []
    for item in boost:
        norm = item.strip().lower()
        if norm and norm not in seen:
            seen.append(norm)
            if len(seen) >= max_keywords:
                return seen

    for tok in tokens:
        tok = tok.strip().lower()
        if len(tok) < 3:
            continue
        if tok in seen:
            continue
        seen.append(tok)
        if len(seen) >= max_keywords:
            break
    return seen
