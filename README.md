# LinkedIn Recent Activity Scraper

Iterate over a CSV of LinkedIn profile URLs, open each profile’s `/recent-activity`, and collect the top posts’ link, content, and timestamp. By default it writes per‑profile JSON files; if you provide an aggregated output path, it writes only that single file and updates it incrementally after each profile. Shows a progress bar with `tqdm`.

> Note: This tool interacts with LinkedIn via a real browser (Playwright). Use responsibly and in accordance with LinkedIn’s Terms of Service and applicable laws. Avoid heavy or automated scraping at scale.

## Features
- Captures up to 3 recent posts per profile (hard cap)
- Saves per‑profile JSON files to an output folder
- Optional single aggregated output file (`json` array or `ndjson`); when used, per‑profile files are not created and the file is updated after each profile completes
- When `--out-file` already exists, profiles already present are skipped automatically
- Progress bar over profiles via `tqdm`
- Uses a persistent Chromium profile so you can log in once and reuse the session

## Prerequisites
- Python 3.10
- pip (to install Python dependencies)
- Playwright browsers (install after pip step below)

## Setup
```bash
# 1) Create and activate a virtual environment (recommended)
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# 2) Install dependencies
pip install -r requirements.txt

# 3) Install the Playwright browser binaries (Chromium)
python -m playwright install chromium
```

## Run
The simplest way to run the CLI from the repo:
```bash
python src/linkedin_analysis/cli.py --csv mini.csv
```

On first run, do not use `--headless` so you can sign in when prompted. A Chromium window opens; sign in to LinkedIn, then return to the terminal and press Enter when instructed.

If you prefer module execution, ensure `src` is on `PYTHONPATH` (or install the package) and then:
```bash
PYTHONPATH=src python -m linkedin_analysis --csv mini.csv
PYTHONPATH=src python3.10 -m linkedin_analysis.cli --csv mini.csv --out-file outputs/all.json   
```

## CLI Usage
```text
--csv                 Path to input CSV (must include a column of LinkedIn profile URLs)
--url-column          CSV column name containing the profile URLs (default: "Person Linkedin Url")
--out                 Directory to write per-profile JSON files (default: outputs)
--limit               Max posts per profile to collect (hard-capped at 3; default: 3)
--headless            Run browser headless (first run should be non-headless to login)
--user-data-dir       Persistent Chromium user data directory (default: .pw)
--out-file            Optional path to write a single aggregated output file (default: none)
--aggregate-format    Format for aggregated file: "json" | "ndjson" (default: json)
```

### Examples
- Minimal run (non-headless first time to sign in):
```bash
python src/linkedin_analysis/cli.py --csv mini.csv
```

- Save outputs under a custom directory:
```bash
python src/linkedin_analysis/cli.py --csv mini.csv --out outputs
```

- Collect fewer posts (still capped at 3):
```bash
python src/linkedin_analysis/cli.py --csv mini.csv --limit 2
```

- Headless after you’ve already logged in previously:
```bash
python src/linkedin_analysis/cli.py --csv mini.csv --headless
```

- Write a single aggregated JSON file (array of profile objects):
```bash
python src/linkedin_analysis/cli.py --csv mini.csv --out-file outputs/all.json
# Note: with --out-file, only outputs/all.json is written (no per-profile files)
```

- Write newline-delimited JSON (one profile object per line):
```bash
python src/linkedin_analysis/cli.py --csv mini.csv --out-file outputs/all.ndjson --aggregate-format ndjson
# With ndjson, one line is appended per profile as it finishes
```

## Input CSV
- The CSV must contain a column with LinkedIn profile URLs. By default, the code looks for a column named `Person Linkedin Url`.
- You can set a custom column name via `--url-column`.

## Output Format

Per‑profile files (e.g., `outputs/<slug>.json`) have the shape:
```json
{
  "profile_url": "https://www.linkedin.com/in/username",
  "posts": [
    {
      "link": "https://www.linkedin.com/posts/...",
      "content": "Post text...",
      "timestamp": "2024-08-30T10:12:00.000Z"
    }
  ]
}
```

Aggregated output (when `--out-file` is provided and per‑profile files are skipped):
- `json` (default): a single JSON object with a `profiles` array
```json
{
  "profiles": [
    { "profile_url": "https://.../in/user1", "posts": [ ... ] },
    { "profile_url": "https://.../in/user2", "posts": [ ... ] }
  ]
}
```

- `ndjson`: one JSON object per line (each object is the same shape as a per‑profile file)
```text
{"profile_url":"https://.../in/user1","posts":[...]}
{"profile_url":"https://.../in/user2","posts":[...]}
```

## Tips & Troubleshooting
- First run: keep the browser non‑headless to sign in.
- The scraper only processes the top 3 posts per profile (minimal scrolling to ensure visibility).
- If LinkedIn UI changes, selectors may need adjustment (see `src/linkedin_analysis/selectors.py`).
- Use `--user-data-dir` to preserve your session (`.pw` by default) across runs.

## Legal & Ethical
Scraping may be subject to the website’s Terms of Service and local regulations. Use responsibly. Do not share credentials or commit secrets/data to the repository.
