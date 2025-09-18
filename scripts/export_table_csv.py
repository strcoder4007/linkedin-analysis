from __future__ import annotations

import argparse
import csv
import json
import os
import re
from typing import Any, Dict, List, Optional
from urllib.parse import unquote, urlparse


DEF_INPUT = "outputs/filtered.json"
DEF_OUTPUT = "outputs/filtered.csv"


def normalize_whitespace(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip()


def guess_profile_name(url: str) -> str:
    try:
        p = urlparse(url)
        parts = [x for x in p.path.split("/") if x]
        name = ""
        if "in" in parts:
            idx = parts.index("in")
            if idx + 1 < len(parts):
                name = parts[idx + 1]
        elif parts:
            name = parts[-1]
        name = unquote(name)
        name = re.sub(r"[-_]+", " ", name)
        name = " ".join(w.capitalize() for w in name.split())
        return name or url
    except Exception:
        return url


def to_hyperlink(url: str, label: str) -> str:
    """Excel/Sheets-friendly hyperlink formula."""
    if not url:
        return ""
    # Escape double quotes in label
    safe_label = label.replace('"', "'")
    safe_url = url.replace('"', "")
    return f'=HYPERLINK("{safe_url}", "{safe_label}")'


def export_table(
    payload: Dict[str, Any],
    out_csv: str,
    max_chars: int = 160,
) -> None:
    profiles = payload.get("profiles")
    if not isinstance(profiles, list):
        profiles = []

    os.makedirs(os.path.dirname(out_csv) or ".", exist_ok=True)

    with open(out_csv, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["Profile", "Latest Post", "Timestamp", "Post Link"])
        for prof in profiles:
            if not isinstance(prof, dict):
                continue
            url = (prof.get("profile_url") or "").strip()
            posts = prof.get("posts")
            if not isinstance(posts, list) or not posts:
                # By design, filtered.json should exclude empty profiles, but handle gracefully
                name = guess_profile_name(url)
                w.writerow([to_hyperlink(url, name), "No posts", "—", "—"])
                continue

            # Use the first post as latest (filter preserves recency)
            post = posts[0]
            link = (post.get("link") or "").strip()
            content = normalize_whitespace((post.get("content") or "").strip())
            ts = (post.get("timestamp") or "").strip()

            if max_chars > 0 and len(content) > max_chars:
                content = content[: max_chars - 1].rstrip() + "…"

            name = guess_profile_name(url)
            w.writerow([
                to_hyperlink(url, name),
                content,
                ts,
                to_hyperlink(link, "Link"),
            ])


def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Export filtered.json to a tabular CSV.")
    p.add_argument("--input", "-i", default=DEF_INPUT, help="Path to filtered JSON (default: outputs/filtered.json)")
    p.add_argument("--output", "-o", default=DEF_OUTPUT, help="Path to write CSV (default: outputs/filtered.csv)")
    p.add_argument("--max-chars", type=int, default=160, help="Max characters for post content snippet (default: 160; 0 = unlimited)")
    return p.parse_args(argv)


def main(argv: Optional[List[str]] = None) -> int:
    args = parse_args(argv)
    with open(args.input, "r", encoding="utf-8") as f:
        payload = json.load(f)
    export_table(payload, out_csv=args.output, max_chars=args.max_chars)
    print(f"Wrote CSV: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

