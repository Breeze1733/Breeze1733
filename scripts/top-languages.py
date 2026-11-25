#!/usr/bin/env python3
"""Generate a "Most Used Languages" SVG card for the GitHub profile README.

Self-contained: Python standard library only, no third-party packages and no
external card service. Data comes from the GitHub REST API: public repos
owned by the user, forks and archived repos excluded. The generated SVG is
committed into this same repo, so the profile README no longer depends on
anybody else's deployment (the old github-readme-stats mirror broke twice).

Usage (locally or in GitHub Actions):
    GITHUB_TOKEN=<token> GITHUB_USERNAME=Breeze1733 python scripts/top-languages.py
The token is optional for public repos but raises the API rate limit.
Output: assets/top-languages.svg (relative to the repo root).
"""

import json
import os
import urllib.error
import urllib.request
from xml.sax.saxutils import escape

USERNAME = os.environ.get("GITHUB_USERNAME", "Breeze1733")
TOKEN = os.environ.get("GITHUB_TOKEN", "")
API = "https://api.github.com"
LANGS_COUNT = 6

# Languages excluded from the stats even if they appear in the repos.
# Add more here if another non-primary language starts polluting the card
# (e.g. "HTML", "CSS", "Dockerfile", "Makefile", "Batchfile", "Shell").
EXCLUDED_LANGUAGES = {
    "PowerShell",
    "TeX",  # LaTeX shows up as "TeX" in GitHub language stats.
    "HTML",
}

# GitHub Linguist colors (subset covering this user's repos; anything
# missing falls back to grey).
LANGUAGE_COLORS = {
    "Python": "#3572A5",
    "Dart": "#00B4AB",
    "JavaScript": "#f1e05a",
    "TypeScript": "#3178c6",
    "Vue": "#41b883",
    "C++": "#f34b7d",
    "C": "#555555",
    "C#": "#178600",
    "Java": "#b07219",
    "Go": "#00ADD8",
    "Rust": "#dea584",
    "Kotlin": "#A97BFF",
    "Swift": "#F05138",
    "HTML": "#e34c26",
    "CSS": "#563d7c",
    "Shell": "#89e051",
    "Lua": "#000080",
    "Ruby": "#701516",
    "PHP": "#4F5D95",
    "Jupyter Notebook": "#DA5B0B",
    "Dockerfile": "#384d54",
    "Makefile": "#427819",
    "CMake": "#DA3434",
    "Slim": "#ff8f77",
    "NSIS": "#d3d3d3",
    "Batchfile": "#C1F12E",
}
FALLBACK_COLOR = "#858585"

# Card style copied from the github-readme-stats default theme, so the
# profile keeps the look it had before.
CARD_WIDTH = 400
CARD_BG = "#fffefe"
CARD_BORDER = "#e4e2e2"
TITLE_COLOR = "#2f80ed"
TEXT_COLOR = "#434d58"


def api_get(url):
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "top-languages-card",
            "Accept": "application/vnd.github+json",
            **({"Authorization": f"Bearer {TOKEN}"} if TOKEN else {}),
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.load(resp)
    except urllib.error.HTTPError as e:
        raise SystemExit(f"GitHub API request failed: {url} -> HTTP {e.code}")


def fetch_repos():
    """Repos owned by the user that the token can see.

    /users/{USERNAME}/repos lists public repos, but with a fine-grained
    PAT it does NOT return the private repos granted to the token, so
    also query /user/repos (repos the token itself can access) and merge
    the two lists, de-duplicated by repo id. With the default
    GITHUB_TOKEN, /user/repos only returns this repo, which is already
    in the public list, so the merge is a no-op there.
    """
    seen = {}
    urls = [f"{API}/users/{USERNAME}/repos?type=owner"]
    if TOKEN:
        urls.append(f"{API}/user/repos?type=owner")
    for url in urls:
        page = 1
        while True:
            batch = api_get(f"{url}&per_page=100&page={page}")
            if not batch:
                break
            for repo in batch:
                seen[repo["id"]] = repo
            if len(batch) < 100:
                break
            page += 1
    repos = [
        r for r in seen.values()
        if not r.get("fork") and not r.get("archived")
    ]
    print(f"repos counted: {len(repos)}")
    return repos


def fetch_language_totals():
    totals = {}
    for repo in fetch_repos():
        langs = api_get(
            f"{API}/repos/{USERNAME}/{repo['name']}/languages"
        )
        for lang, size in langs.items():
            if lang in EXCLUDED_LANGUAGES:
                continue
            totals[lang] = totals.get(lang, 0) + size
    return totals


def render_svg(top, total):
    """Compact card: title, stacked progress bar, 2 columns x 3 rows."""
    rows = (len(top) + 1) // 2
    height = 78 + rows * 25 + 12
    shown_total = sum(size for _, size in top)

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{CARD_WIDTH}" '
        f'height="{height}" viewBox="0 0 {CARD_WIDTH} {height}" role="img" '
        f'aria-label="Most Used Languages">',
        f'<rect x="0.5" y="0.5" width="{CARD_WIDTH - 1}" height="{height - 1}" '
        f'rx="4.5" fill="{CARD_BG}" stroke="{CARD_BORDER}"/>',
        f'<text x="25" y="35" font-family="Segoe UI, Ubuntu, Sans-Serif" '
        f'font-size="16" font-weight="600" fill="{TITLE_COLOR}">'
        f"Most Used Languages</text>",
    ]

    # Stacked progress bar, segments normalised to the displayed languages.
    x = 25.0
    bar_y, bar_w, bar_h = 48, 350, 8
    parts.append(
        f'<g><rect x="{x}" y="{bar_y}" width="{bar_w}" height="{bar_h}" '
        f'rx="4" fill="#f0f0f0"/></g>'
    )
    for lang, size in top:
        w = bar_w * size / shown_total
        color = LANGUAGE_COLORS.get(lang, FALLBACK_COLOR)
        parts.append(
            f'<rect x="{x:.2f}" y="{bar_y}" width="{w:.2f}" '
            f'height="{bar_h}" fill="{color}"/>'
        )
        x += w
    parts.append(
        f'<rect x="25" y="{bar_y}" width="{bar_w}" height="{bar_h}" '
        f'rx="4" fill="none" stroke="{CARD_BORDER}" stroke-opacity="0.4"/>'
    )

    # Language rows: two columns.
    for i, (lang, size) in enumerate(top):
        col = i % 2
        row = i // 2
        cx = 25 + col * 190
        cy = 88 + row * 25
        color = LANGUAGE_COLORS.get(lang, FALLBACK_COLOR)
        pct = size / total * 100
        parts.append(
            f'<circle cx="{cx + 5}" cy="{cy - 4}" r="5" fill="{color}"/>'
        )
        parts.append(
            f'<text x="{cx + 18}" y="{cy}" font-family="Segoe UI, Ubuntu, '
            f'Sans-Serif" font-size="12" fill="{TEXT_COLOR}">'
            f"{escape(lang)}</text>"
        )
        parts.append(
            f'<text x="{cx + 175}" y="{cy}" text-anchor="end" '
            f'font-family="Segoe UI, Ubuntu, Sans-Serif" font-size="12" '
            f'fill="{TEXT_COLOR}">{pct:.2f}%</text>'
        )
    parts.append("</svg>")
    return "\n".join(parts) + "\n"


def main():
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    totals = fetch_language_totals()
    total = sum(totals.values())
    if not total:
        raise SystemExit(f"No language data found for user {USERNAME}")
    top = sorted(totals.items(), key=lambda kv: -kv[1])[:LANGS_COUNT]
    for lang, size in sorted(totals.items(), key=lambda kv: -kv[1]):
        print(f"{lang:20s} {size:10d}  {size / total * 100:5.2f}%")
    out_path = os.path.join(root, "assets", "top-languages.svg")
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(render_svg(top, total))
    print(f"Wrote {out_path}")


if __name__ == "__main__":
    main()
