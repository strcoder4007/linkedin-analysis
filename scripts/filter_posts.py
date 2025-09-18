from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


DEF_INPUT = "outputs/all.json"
DEF_OUTPUT = "outputs/filtered.json"
DEF_DEEPSEEK_BASE = "https://api.deepseek.com"
DEF_DEEPSEEK_MODEL = "deepseek-chat"


def load_env_file(path: str = ".env") -> None:
    """Minimal .env loader without external deps.

    Parses lines of the form KEY=VALUE, ignoring blanks and comments.
    Does not overwrite variables that are already set in the environment.
    """
    try:
        with open(path, "r", encoding="utf-8") as f:
            for raw in f:
                line = raw.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" not in line:
                    continue
                k, v = line.split("=", 1)
                key = k.strip()
                val = v.strip().strip('"').strip("'")
                if key and key not in os.environ:
                    os.environ[key] = val
    except FileNotFoundError:
        pass


def _iso_to_dt(ts: str) -> Optional[datetime]:
    s = ts.strip()
    if not s:
        return None
    try:
        # Handle Zulu suffix
        if s.endswith("Z"):
            s = s[:-1] + "+00:00"
        dt = datetime.fromisoformat(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except Exception:
        return None


_REL_RE = re.compile(
    r"(?P<num>\d+)\s*(?P<unit>years?|yrs?|y|months?|mos?|mo|weeks?|wks?|wk|w|days?|d|hours?|hrs?|hr|h|minutes?|mins?|min|m)\b",
    re.IGNORECASE,
)


def _relative_to_dt(s: str, now: Optional[datetime] = None) -> Optional[datetime]:
    """Parse common LinkedIn relative timestamps to an approximate datetime (UTC).

    Examples supported: "2wk", "2 weeks ago", "5d", "3 days ago", "1yr", "6mo", "12h", "30m".
    Returns None if no recognizable token is found.
    """
    if not s:
        return None
    now = now or datetime.now(timezone.utc)
    m = _REL_RE.search(s)
    if not m:
        return None
    num = int(m.group("num"))
    unit = m.group("unit").lower()

    days = 0.0
    if unit.startswith("y") or unit.startswith("yr"):
        days = num * 365
    elif unit.startswith("mo"):
        days = num * 30
    elif unit.startswith("w"):
        days = num * 7
    elif unit == "d" or unit.startswith("day"):
        days = num
    elif unit.startswith("h"):
        days = num / 24.0
    elif unit.startswith("min") or unit == "m":
        days = num / (24.0 * 60.0)
    else:
        return None

    return now - timedelta(days=days)


def parse_timestamp_to_dt(ts: str, now: Optional[datetime] = None) -> Optional[datetime]:
    """Try ISO first, then relative. Returns UTC datetime or None."""
    if not ts:
        return None
    dt = _iso_to_dt(ts)
    if dt:
        return dt
    return _relative_to_dt(ts, now=now)


def within_two_weeks(ts: str, now: Optional[datetime] = None) -> bool:
    """Return True if timestamp is <= 14 days ago. If unparseable, default to True."""
    now = now or datetime.now(timezone.utc)
    dt = parse_timestamp_to_dt(ts, now=now)
    if not dt:
        # If we cannot parse, keep the post rather than drop it.
        return True
    delta = now - dt
    # Keep if age is <= 14 days. More than 14 days is irrelevant.
    return delta <= timedelta(days=14)


KEYWORDS_AI = [
    "ai",
    "artificial intelligence",
    "machine learning",
    "ml",
    "genai",
    "gpt",
    "llm",
    "deep learning",
    "neural",
    "openai",
    "deepseek",
]

KEYWORDS_RE = [
    "real estate",
    "property",
    "properties",
    "realtor",
    "reit",
    "cre",
    "proptech",
    "prop tech",
]


def _heuristic_relevant(text: str) -> bool:
    t = text.lower()
    return any(k in t for k in KEYWORDS_AI) or any(k in t for k in KEYWORDS_RE)


class DeepseekClient:
    def __init__(self, api_key: str, model: str = DEF_DEEPSEEK_MODEL, base_url: str = DEF_DEEPSEEK_BASE) -> None:
        self.api_key = api_key
        self.model = model
        self.base_url = base_url.rstrip("/")

    def classify(self, content: str, timeout: int = 30) -> Tuple[bool, str]:
        """Return (relevant, raw_response_text). Falls back to heuristic on error."""
        url = f"{self.base_url}/v1/chat/completions"
        prompt = (
            "Decide if the following LinkedIn post content is relevant to any of: "
            "(A) AI (artificial intelligence), (B) Real Estate, or (C) AI applied to Real Estate.\n"
            "Respond strictly as a compact JSON object with keys: relevant (boolean), category (one of: AI, RealEstate, AI_in_RealEstate, Other). No extra text.\n"
            "Content:"\
        )
        messages = [
            {"role": "system", "content": "You are a precise JSON-only classifier."},
            {"role": "user", "content": f"{prompt}\n\n{content.strip()}"},
        ]
        body = {
            "model": self.model,
            "messages": messages,
            "temperature": 0.0,
            "max_tokens": 64,
        }

        data = json.dumps(body).encode("utf-8")
        req = Request(url, data=data, method="POST")
        req.add_header("Authorization", f"Bearer {self.api_key}")
        req.add_header("Content-Type", "application/json")

        try:
            with urlopen(req, timeout=timeout) as resp:
                raw = resp.read().decode("utf-8")
        except (HTTPError, URLError) as e:
            print(f"[deepseek] API error: {e}", file=sys.stderr)
            return _heuristic_relevant(content), ""
        except Exception as e:
            print(f"[deepseek] Unexpected error: {e}", file=sys.stderr)
            return _heuristic_relevant(content), ""

        try:
            obj = json.loads(raw)
            # OpenAI-compatible shape
            text = obj["choices"][0]["message"]["content"].strip()
        except Exception:
            text = raw.strip()

        # Extract JSON object from text
        relevant = _parse_relevance_from_text(text, fallback=_heuristic_relevant(content))
        return relevant, text


_JSON_OBJ_RE = re.compile(r"\{.*\}", re.DOTALL)


def _parse_relevance_from_text(text: str, fallback: bool) -> bool:
    # Try pure JSON first
    try:
        obj = json.loads(text)
        if isinstance(obj, dict) and "relevant" in obj:
            return bool(obj["relevant"])  # type: ignore[truthy-bool]
    except Exception:
        pass
    # Try to find a JSON object substring
    m = _JSON_OBJ_RE.search(text)
    if m:
        try:
            obj = json.loads(m.group(0))
            if isinstance(obj, dict) and "relevant" in obj:
                return bool(obj["relevant"])  # type: ignore[truthy-bool]
        except Exception:
            pass
    return fallback


def filter_payload(
    payload: Dict[str, Any],
    client: Optional[DeepseekClient],
    now: Optional[datetime] = None,
) -> Dict[str, Any]:
    """Filter posts per profile based on recency and LLM relevance.

    The input payload should be a dict with key "profiles" -> list of {profile_url, posts[]}.
    Returns a similarly-shaped dict with posts filtered.
    """
    now = now or datetime.now(timezone.utc)
    profiles = payload.get("profiles")
    if not isinstance(profiles, list):
        return {"profiles": []}

    out_profiles: List[Dict[str, Any]] = []
    relevance_cache: dict[str, bool] = {}

    for prof in profiles:
        if not isinstance(prof, dict):
            continue
        profile_url = prof.get("profile_url", "")
        posts = prof.get("posts")
        if not isinstance(posts, list):
            # No valid posts list; treat as empty and skip including this profile
            print(
                f"[trace] Profile={profile_url} DROP (no posts list)",
                file=sys.stderr,
            )
            continue

        kept: List[Dict[str, Any]] = []
        for post in posts:
            if not isinstance(post, dict):
                continue
            link = (post.get("link") or "").strip()
            content = (post.get("content") or "").strip()
            timestamp = (post.get("timestamp") or "").strip()

            # Rule 0: Must have link, content, and timestamp
            missing = []
            if not link:
                missing.append("link")
            if not content:
                missing.append("content")
            if not timestamp:
                missing.append("timestamp")
            if missing:
                print(
                    f"[trace] Profile={profile_url} SKIP (missing {','.join(missing)}) link={link}",
                    file=sys.stderr,
                )
                continue

            # Rule 1: Recency (<= 14 days old)
            if "https://www.linkedin.com/posts" not in link:
                print(
                    f"[trace] Profile={profile_url} SKIP (link not linkedin posts) link={link}",
                    file=sys.stderr,
                )
                continue

            # Rule 1: Recency (<= 14 days old)
            if not within_two_weeks(timestamp, now=now):
                print(
                    f"[trace] Profile={profile_url} SKIP (older than 2 weeks) ts={timestamp}",
                    file=sys.stderr,
                )
                continue

            # Rule 2: Topic relevance (AI OR Real Estate)

            key = content[:5000]
            if key in relevance_cache:
                ok = relevance_cache[key]
                print(
                    f"[trace] Profile={profile_url} cache-hit classify relevant={ok} link={post.get('link','')}",
                    file=sys.stderr,
                )
            else:
                if client is None:
                    ok = _heuristic_relevant(content)
                    raw = ""
                    print(
                        f"[trace] Profile={profile_url} classify source=heuristic relevant={ok} link={post.get('link','')}",
                        file=sys.stderr,
                    )
                else:
                    print(
                        f"[trace] Profile={profile_url} classify source=LLM link={post.get('link','')}",
                        file=sys.stderr,
                    )
                    ok, raw = client.classify(content)
                relevance_cache[key] = ok
                if raw:
                    # Optional: emit trace for transparency
                    print(
                        f"[trace] Profile={profile_url} LLM: relevant={ok} :: {raw}",
                        file=sys.stderr,
                    )

            if ok:
                kept.append(post)

        if kept:
            out_profiles.append({
                "profile_url": profile_url,
                "posts": kept,
            })
        else:
            print(
                f"[trace] Profile={profile_url} DROP (no kept posts)",
                file=sys.stderr,
            )

    return {"profiles": out_profiles}


def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Filter LinkedIn posts by recency and topic using DeepSeek.")
    p.add_argument("--input", "-i", default=DEF_INPUT, help="Path to aggregated input JSON (default: outputs/all.json)")
    p.add_argument("--output", "-o", default=DEF_OUTPUT, help="Path to write filtered JSON (default: outputs/filtered.json)")
    p.add_argument("--base-url", default=os.environ.get("DEEPSEEK_BASE_URL", DEF_DEEPSEEK_BASE), help="DeepSeek API base URL (default: https://api.deepseek.com)")
    p.add_argument("--model", default=os.environ.get("DEEPSEEK_MODEL", DEF_DEEPSEEK_MODEL), help="DeepSeek model name (default: deepseek-chat)")
    p.add_argument("--no-llm", action="store_true", help="Disable DeepSeek calls and use simple keyword heuristic only")
    p.add_argument("--no-dotenv", action="store_true", help="Do not read .env at startup")
    return p.parse_args(argv)


def main(argv: Optional[List[str]] = None) -> int:
    args = parse_args(argv)

    if not args.no_dotenv:
        load_env_file()

    api_key = os.environ.get("DEEPSEEK_API_KEY")
    client: Optional[DeepseekClient]
    if args.no_llm:
        client = None
    else:
        if not api_key:
            print("DEEPSEEK_API_KEY not set; falling back to keyword heuristic.", file=sys.stderr)
            client = None
        else:
            client = DeepseekClient(api_key=api_key, model=args.model, base_url=args.base_url)

    # Load input
    with open(args.input, "r", encoding="utf-8") as f:
        payload = json.load(f)

    # Filter
    filtered = filter_payload(payload, client=client)

    # Write output
    os.makedirs(os.path.dirname(args.output) or ".", exist_ok=True)
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(filtered, f, ensure_ascii=False, indent=2)

    # Brief summary
    total_before = sum(len(p.get("posts", [])) for p in payload.get("profiles", [])) if isinstance(payload.get("profiles"), list) else 0
    total_after = sum(len(p.get("posts", [])) for p in filtered.get("profiles", [])) if isinstance(filtered.get("profiles"), list) else 0
    print(f"Filtered posts: {total_before} → {total_after}", file=sys.stderr)
    print(f"Wrote: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
