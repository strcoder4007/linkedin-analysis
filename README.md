# LinkedIn Recent Activity Scraper

Iterate over a CSV of LinkedIn profile URLs, open each profile’s `/recent-activity`, and collect the top posts’ link, content, and timestamp. Output is always written to a single aggregated file (`outputs/all.json` by default) and it is updated incrementally after each profile completes. No per‑profile files are created. Shows a progress bar with `tqdm`.

> Note: This tool interacts with LinkedIn via a real browser (Playwright). Use responsibly and in accordance with LinkedIn’s Terms of Service and applicable laws. Avoid heavy or automated scraping at scale.

## Features
- Captures up to 3 recent posts per profile (hard cap)
- Writes to a single aggregated output file (default: `outputs/all.json`), updated after each profile
- Supports `json` (single object with `profiles` array) or `ndjson` (one JSON object per line)
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
The simplest way to run the CLI from the repo (writes to `outputs/all.json`):
```bash
python src/linkedin_analysis/cli.py --csv mini.csv
```

On first run, do not use `--headless` so you can sign in when prompted. A Chromium window opens; sign in to LinkedIn, then return to the terminal and press Enter when instructed.

If you prefer module execution, ensure `src` is on `PYTHONPATH` (or install the package) and then:
```bash
PYTHONPATH=src python -m linkedin_analysis --csv mini.csv
PYTHONPATH=src python3.10 -m linkedin_analysis.cli --csv mini.csv
```

## CLI Usage
```text
--csv                 Path to input CSV (must include a column of LinkedIn profile URLs)
--url-column          CSV column name containing the profile URLs (default: "Person Linkedin Url")
--out                 Output directory (parent of aggregated file; default: outputs)
--limit               Max posts per profile to collect (hard-capped at 3; default: 3)
--headless            Run browser headless (first run should be non-headless to login)
--user-data-dir       Persistent Chromium user data directory (default: .pw)
--out-file            Path to aggregated output file (default: outputs/all.json)
--aggregate-format    Format for aggregated file: "json" | "ndjson" (default: json)
```

### Examples
- Minimal run (non-headless first time to sign in):
```bash
python src/linkedin_analysis/cli.py --csv mini.csv
# Writes/updates outputs/all.json by default
```

- Collect fewer posts (still capped at 3):
```bash
python src/linkedin_analysis/cli.py --csv mini.csv --limit 2
```

- Headless after you’ve already logged in previously:
```bash
python src/linkedin_analysis/cli.py --csv mini.csv --headless
```

- Write to a custom aggregated JSON path (array of profile objects):
```bash
python src/linkedin_analysis/cli.py --csv mini.csv --out-file outputs/custom_all.json
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

Aggregated output (default behavior):
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

## Filter Posts (after scraping)
Use the post-filtering script only after you have scraped and generated `outputs/all.json` via the scraper above.

### What it does
- Keeps only posts from the last 14 days (exactly 2 weeks is kept).
- Keeps only posts relevant to AI, Real Estate, or AI in Real Estate using the DeepSeek LLM (falls back to a keyword heuristic if no API key).
- Omits profiles that end up with zero kept posts from the output.

### Setup
1) Create a `.env` (not committed) from the provided template and add your DeepSeek key:
```bash
cp .env.example .env
echo "DEEPSEEK_API_KEY=YOUR_KEY" >> .env
```

### Run
```bash
# Requires outputs/all.json to exist first
python scripts/filter_posts.py --input outputs/all.json --output outputs/filtered.json
```

### Options
```text
--input, -i     Path to aggregated input JSON (default: outputs/all.json)
--output, -o    Path to write filtered JSON (default: outputs/filtered.json)
--model         DeepSeek model name (env: DEEPSEEK_MODEL; default: deepseek-chat)
--base-url      DeepSeek API base (env: DEEPSEEK_BASE_URL; default: https://api.deepseek.com)
--no-llm        Disable DeepSeek calls and use keyword heuristic only
--no-dotenv     Do not read .env on startup
```

### Notes
- Prints trace lines to stderr indicating which profile each post was analyzed under and why posts were kept or dropped.
- If a timestamp cannot be parsed, the post is kept (conservative) and then filtered by relevance.
