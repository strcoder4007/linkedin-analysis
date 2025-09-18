from __future__ import annotations

import json
import sys
from typing import List, Dict
import re

from playwright.sync_api import Playwright, TimeoutError, sync_playwright
from tqdm import tqdm
from pathlib import Path

from . import __version__
from .selectors import (
    POST_CONTAINER,
    MENU_TRIGGER,
    MENUITEM_COPY_LINK_ROLE_NAME,
    POST_CONTENT_PRIMARY,
    POST_CONTENT_FALLBACK,
    POST_TIME_EL_PRIMARY,
    POST_TIME_CONTAINER_FALLBACK,
)
from .utils import (
    ensure_dir,
    jitter_sleep,
    to_recent_activity,
    write_json,
)


def _click_copy_link(page, post) -> str | None:
    # Open menu
    trigger = post.locator(MENU_TRIGGER)
    if trigger.count() == 0:
        return None
    try:
        trigger.first.scroll_into_view_if_needed()
        trigger.first.click(timeout=4000)
    except TimeoutError:
        return None

    # Click the "Copy link to post" menu item (menu is page-level)
    try:
        page.get_by_role("menuitem", name=MENUITEM_COPY_LINK_ROLE_NAME).first.click(timeout=4000)
    except TimeoutError:
        # try text locator fallback
        try:
            page.locator("text='Copy link to post'").first.click(timeout=3000)
        except TimeoutError:
            return None

    # Read from clipboard
    try:
        link = page.evaluate("navigator.clipboard.readText()")
        return (link or "").strip() or None
    except Exception:
        return None


def _extract_content(post) -> str:
    for sel in (POST_CONTENT_PRIMARY, POST_CONTENT_FALLBACK):
        loc = post.locator(sel)
        if loc.count() > 0:
            try:
                # Expand "See more" if present within content
                see_more = post.get_by_role("button", name=re.compile(r"see more", re.I))
                if see_more.count():
                    see_more.first.click(timeout=1500)
            except Exception:
                pass
            try:
                return loc.first.inner_text(timeout=4000).strip()
            except Exception:
                continue
    return ""


def _extract_timestamp(post) -> str:
    # Prefer machine-readable datetime
    loc = post.locator(POST_TIME_EL_PRIMARY)
    if loc.count():
        try:
            dt = loc.first.get_attribute("datetime")
            if dt:
                return dt
        except Exception:
            pass
    # Fallback to visible text
    loc2 = post.locator(POST_TIME_CONTAINER_FALLBACK)
    if loc2.count():
        try:
            return loc2.first.inner_text(timeout=3000).strip()
        except Exception:
            pass
    return ""


def _collect_top_posts_from_page(page, limit: int) -> List[Dict[str, str]]:
    """Collect data from the top-N posts only, without continuous scrolling.

    Attempts to ensure at least N posts are present by performing minimal scrolls,
    then processes only the first N containers exactly once.
    """
    posts: List[Dict[str, str]] = []
    seen_links = set()

    # Ensure at least `limit` posts are present (minimal scrolling only)
    for _ in range(4):
        containers = page.locator(POST_CONTAINER)
        if containers.count() >= limit:
            break
        page.mouse.wheel(0, 2000)
        jitter_sleep(0.6, 1.0)

    containers = page.locator(POST_CONTAINER)
    top_n = min(containers.count(), limit)
    for i in range(top_n):
        post = containers.nth(i)
        try:
            post.scroll_into_view_if_needed()
        except Exception:
            pass

        link = _click_copy_link(page, post)
        content = _extract_content(post)
        timestamp = _extract_timestamp(post)

        if not link and timestamp == "" and content == "":
            continue

        if link and link in seen_links:
            continue
        if link:
            seen_links.add(link)

        posts.append({
            "link": link or "",
            "content": content,
            "timestamp": timestamp,
        })

        jitter_sleep(0.3, 0.8)

    return posts


def _ensure_logged_in(page, headless: bool) -> None:
    # Try to open feed and detect login
    page.goto("https://www.linkedin.com/feed/", wait_until="domcontentloaded")
    is_login = False
    try:
        is_login = page.locator("input#username").count() > 0
    except Exception:
        pass
    if is_login and not headless:
        print("Sign in to LinkedIn in the opened browser, then press Enter here…", file=sys.stderr)
        try:
            input()
        except EOFError:
            pass


def scrape_profile(page, base_profile_url: str, limit: int) -> List[Dict[str, str]]:
    ra_url = to_recent_activity(base_profile_url)
    page.goto(ra_url, wait_until="domcontentloaded")
    # Wait for at least one potential container or gracefully continue
    try:
        page.locator(POST_CONTAINER).first.wait_for(state="visible", timeout=8000)
    except TimeoutError:
        return []
    return _collect_top_posts_from_page(page, limit=limit)


def run(
    csv_rows: List[str],
    out_dir: str,
    limit: int = 3,
    headless: bool = False,
    user_data_dir: str = ".pw",
    out_file: str | None = None,
    aggregate_format: str = "json",
) -> None:
    ensure_dir(out_dir)

    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(
            user_data_dir=user_data_dir,
            headless=headless,
            viewport={"width": 1280, "height": 900},
            args=["--disable-blink-features=AutomationControlled"],
        )
        context.grant_permissions(["clipboard-read", "clipboard-write"], origin="https://www.linkedin.com")
        page = context.new_page()

        _ensure_logged_in(page, headless=headless)

        HARD_LIMIT = 3
        # Always write to a single aggregated file (default: outputs/all.json)
        agg_path = Path(out_file) if out_file else Path(out_dir) / "all.json"
        # Track previously scraped profiles and preload aggregate content
        processed_urls: set[str] = set()
        all_payloads: list[dict] = []
        if agg_path.exists():
            try:
                if aggregate_format == "ndjson":
                    with agg_path.open("r", encoding="utf-8") as f:
                        for line in f:
                            line = line.strip()
                            if not line:
                                continue
                            try:
                                obj = json.loads(line)
                            except Exception:
                                continue
                            url = (obj.get("profile_url") or "").strip()
                            if url:
                                processed_urls.add(url)
                else:
                    with agg_path.open("r", encoding="utf-8") as f:
                        obj = json.load(f)
                    profiles = obj.get("profiles") if isinstance(obj, dict) else None
                    if isinstance(profiles, list):
                        for item in profiles:
                            if isinstance(item, dict):
                                url = (item.get("profile_url") or "").strip()
                                if url:
                                    processed_urls.add(url)
                        # Preload existing aggregate for JSON mode so rewrites include it
                        all_payloads = list(profiles)
            except Exception:
                # If the aggregate file is malformed, ignore and start fresh
                processed_urls = set()
                all_payloads = []
        total = len(csv_rows)
        for idx, profile_url in enumerate(tqdm(csv_rows, desc="Profiles", unit="profile"), start=1):
            # Skip if already scraped and present in aggregate
            if profile_url in processed_urls:
                tqdm.write(f"[{idx}/{total}] Skipping already scraped: {profile_url}")
                continue
            # Use tqdm.write to avoid breaking the progress bar formatting
            tqdm.write(f"[{idx}/{total}] {profile_url} → {agg_path}")

            # Enforce hard limit of top 3 posts
            eff_limit = min(limit, HARD_LIMIT)
            posts = scrape_profile(page, profile_url, limit=eff_limit)
            payload = {"profile_url": profile_url, "posts": posts}
            all_payloads.append(payload)

            jitter_sleep(1.5, 3.5)

            # Incrementally update aggregated file after each profile
            agg_path.parent.mkdir(parents=True, exist_ok=True)
            if aggregate_format == "ndjson":
                # Append if file exists, otherwise create
                mode = "a" if agg_path.exists() else "w"
                with agg_path.open(mode, encoding="utf-8") as f:
                    f.write(json.dumps(payload, ensure_ascii=False) + "\n")
            else:
                # Write whole aggregate as a single JSON object
                write_json(agg_path, {"profiles": all_payloads})

        context.close()
