from __future__ import annotations

import csv
import json
import os
import random
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Dict, Optional
from urllib.parse import urlparse


@dataclass
class Post:
    link: str
    content: str
    timestamp: str


def _normalize_header(s: str) -> str:
    return re.sub(r"\s+", " ", s.replace("\ufeff", "").strip().lower())


def _find_column(fieldnames: Optional[List[str]], target: str) -> Optional[str]:
    if not fieldnames:
        return None
    norm_target = _normalize_header(target)
    for name in fieldnames:
        if _normalize_header(name) == norm_target:
            return name
    # Loose contains match as fallback
    for name in fieldnames:
        if norm_target in _normalize_header(name):
            return name
    return None


def read_profile_urls(csv_path: str, url_column: str) -> List[str]:
    urls: List[str] = []
    tried: List[str] = []
    for enc in ("utf-8", "utf-8-sig", "utf-16", "utf-16le", "utf-16be", "latin-1"):
        try:
            with open(csv_path, newline="", encoding=enc, errors="strict") as f:
                reader = csv.DictReader(f)
                actual_col = _find_column(reader.fieldnames, url_column)  # type: ignore[arg-type]
                if not actual_col:
                    # Try next encoding; keep track
                    tried.append(f"{enc} (no matching column)")
                    continue
                for row in reader:  # type: ignore[assignment]
                    raw = (row.get(actual_col) or "").strip()
                    if not raw:
                        continue
                    urls.append(normalize_profile_url(raw))
                break
        except UnicodeDecodeError:
            tried.append(f"{enc} (decode error)")
            continue
    else:
        raise UnicodeDecodeError("csv", b"", 0, 1, f"Unable to decode CSV. Tried encodings: {', '.join(tried)}")

    # Deduplicate preserving order
    seen = set()
    deduped = []
    for u in urls:
        if u not in seen:
            seen.add(u)
            deduped.append(u)
    return deduped


def normalize_profile_url(url: str) -> str:
    # Ensure https scheme and strip query/fragment
    if not url.startswith("http"):
        url = "https://" + url.lstrip("/")
    parsed = urlparse(url)
    clean = f"https://{parsed.netloc}{parsed.path}"
    # Drop trailing slashes for base profile
    clean = re.sub(r"/+\Z", "", clean)
    return clean


def to_recent_activity(url: str) -> str:
    if url.endswith("/recent-activity"):
        return url
    return url + "/recent-activity"


def slugify_from_url(url: str) -> str:
    parsed = urlparse(url)
    parts = [p for p in parsed.path.split("/") if p]
    candidate = parts[-1] if parts else re.sub(r"\W+", "-", parsed.netloc)
    candidate = re.sub(r"[^a-zA-Z0-9_-]", "-", candidate)
    return candidate.lower() or "profile"


def ensure_dir(path: str | Path) -> Path:
    p = Path(path)
    p.mkdir(parents=True, exist_ok=True)
    return p


def write_json(path: str | Path, obj: Dict) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)


def jitter_sleep(min_s: float = 0.4, max_s: float = 1.2) -> None:
    time.sleep(random.uniform(min_s, max_s))
