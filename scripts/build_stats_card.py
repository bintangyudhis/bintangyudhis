#!/usr/bin/env python3
"""Generate assets/gojo-stats.svg: a Gojo-themed GitHub stats banner.

Fetches live stats for GH_USER from the GitHub API (token in GH_TOKEN env),
computes an estimated rank with the github-readme-stats formula, and renders
an SVG with the Gojo cutout (scripts/gojo-cutout.png) embedded as base64.
Run daily by .github/workflows/stats-card.yml; can also run locally.
"""
import base64
import json
import math
import os
import random
import urllib.request

USER = os.environ.get("GH_USER", "bintangyudhis")
TOKEN = os.environ.get("GH_TOKEN", "")
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)


def api(path):
    req = urllib.request.Request("https://api.github.com" + path)
    req.add_header("Accept", "application/vnd.github+json")
    if TOKEN:
        req.add_header("Authorization", "Bearer " + TOKEN)
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def fetch_stats():
    user = api(f"/users/{USER}")
    stars = 0
    page = 1
    while True:
        repos = api(f"/users/{USER}/repos?per_page=100&page={page}&type=owner")
        if not repos:
            break
        stars += sum(r.get("stargazers_count", 0) for r in repos)
        page += 1
    prs = api(f"/search/issues?q=author:{USER}+type:pr+is:merged")["total_count"]
    issues = api(f"/search/issues?q=author:{USER}+type:issue")["total_count"]
    commits = api(f"/search/commits?q=author:{USER}")["total_count"]
    return {
        "commits": commits,
        "prs": prs,
        "issues": issues,
        "stars": stars,
        "followers": user.get("followers", 0),
    }


def rank_letter(s):
    # github-readme-stats: exponential cdf 1 - 2^(-x/median), weighted mean
    parts = [
        (s["commits"], 250, 2),
        (s["prs"], 50, 3),
        (s["issues"], 25, 1),
        (0, 2, 1),  # reviews: not fetched, counts as 0
        (s["stars"], 50, 4),
        (s["followers"], 10, 1),
    ]
    score = sum(w * (1 - 2 ** (-x / m)) for x, m, w in parts) / sum(w for _, _, w in parts)
    pct = (1 - score) * 100
    for limit, letter in [(1, "S+"), (12.5, "S"), (25, "A+"), (37.5, "A"),
                          (50, "A-"), (62.5, "B+"), (75, "B"), (87.5, "B-")]:
        if pct <= limit:
            return letter
    return "C+"


def fmt(n):
    return f"{n:,}".replace(",", ".")


def build_svg(s, rank, gojo_b64):
    W, H = 1000, 290
    random.seed(23)
    stars_svg = []
    for _ in range(64):
        x = round(random.uniform(12, 700), 1)
        y = round(random.uniform(10, H - 14), 1)
        r = round(random.uniform(0.8, 1.9), 2)
        dur = round(random.uniform(1.8, 4.4), 2)
        beg = round(random.uniform(0, 4), 2)
        op = round(random.uniform(0.45, 0.95), 2)
        fill = random.choice(["#dbeafe", "#e9d5ff", "#ffffff"])
        stars_svg.append(
            f'<circle cx="{x}" cy="{y}" r="{r}" fill="{fill}" opacity="{op}">'
            f'<animate attributeName="opacity" values="{op};0.15;{op}" dur="{dur}s" begin="{beg}s" repeatCount="indefinite"/></circle>')
    groups = [
        (fmt(s["commits"]), "Commits", "#f8fafc"),
        (fmt(s["prs"]), "Pull Requests", "#f8fafc"),
        (fmt(s["issues"]), "Issues", "#f8fafc"),
        (fmt(s["stars"]), "Stars", "#f8fafc"),
        (fmt(s["followers"]), "Followers", "#f8fafc"),
        (rank, "Rank", "#e879f9"),
    ]
    cells = []
    for i, (num, label, color) in enumerate(groups):
        x = 48 + i * 112
        cells.append(
            f'<text x="{x}" y="176" font-size="33" font-weight="700" fill="{color}">{num}</text>'
            f'<text x="{x}" y="204" font-size="14.5" fill="#94a3b8">{label}</text>')
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" font-family="'Segoe UI', Ubuntu, 'Helvetica Neue', sans-serif">
<defs>
  <linearGradient id="space" x1="0" y1="0" x2="0" y2="1">
    <stop offset="0" stop-color="#020010"/>
    <stop offset="0.6" stop-color="#0a0620"/>
    <stop offset="1" stop-color="#170b33"/>
  </linearGradient>
  <radialGradient id="neb1" cx="0.5" cy="0.5" r="0.5">
    <stop offset="0" stop-color="#7e22ce" stop-opacity="0.45"/><stop offset="1" stop-color="#7e22ce" stop-opacity="0"/>
  </radialGradient>
  <radialGradient id="neb2" cx="0.5" cy="0.5" r="0.5">
    <stop offset="0" stop-color="#1d4ed8" stop-opacity="0.45"/><stop offset="1" stop-color="#1d4ed8" stop-opacity="0"/>
  </radialGradient>
  <clipPath id="frame"><rect x="1" y="1" width="{W-2}" height="{H-2}" rx="18"/></clipPath>
</defs>
<g clip-path="url(#frame)">
  <rect x="1" y="1" width="{W-2}" height="{H-2}" rx="18" fill="url(#space)"/>
  <ellipse cx="200" cy="52" rx="300" ry="110" fill="url(#neb1)"/>
  <ellipse cx="640" cy="250" rx="320" ry="110" fill="url(#neb2)"/>
  {''.join(stars_svg)}
  <circle cx="876" cy="140" r="97" fill="none" stroke="#38bdf8" stroke-width="2.5" opacity="0.9">
    <animate attributeName="r" values="97;101;97" dur="6s" repeatCount="indefinite"/>
    <animate attributeName="opacity" values="0.9;0.55;0.9" dur="6s" repeatCount="indefinite"/>
  </circle>
  <circle cx="876" cy="140" r="108" fill="none" stroke="#a855f7" stroke-width="1.4" opacity="0.5">
    <animate attributeName="r" values="108;104;108" dur="6s" repeatCount="indefinite"/>
  </circle>
  <image href="data:image/png;base64,{gojo_b64}" x="772" y="8" width="212" height="299"/>
  <text x="48" y="66" font-size="21" font-weight="700" letter-spacing="3" fill="#e2e8f0">GITHUB STATS</text>
  <text x="48" y="94" font-size="16" fill="#7dd3fc">@{USER}</text>
  <rect x="48" y="112" width="150" height="3" rx="1.5" fill="#a855f7"/>
  {''.join(cells)}
  <text x="48" y="254" font-size="12.5" fill="#64748b">Diperbarui otomatis setiap hari</text>
</g>
<rect x="1" y="1" width="{W-2}" height="{H-2}" rx="18" fill="none" stroke="#a855f7" stroke-opacity="0.4" stroke-width="2"/>
</svg>'''


def main():
    stats = fetch_stats()
    rank = rank_letter(stats)
    with open(os.path.join(HERE, "gojo-cutout.png"), "rb") as f:
        gojo_b64 = base64.b64encode(f.read()).decode()
    svg = build_svg(stats, rank, gojo_b64)
    out = os.path.join(ROOT, "assets", "gojo-stats.svg")
    with open(out, "w") as f:
        f.write(svg)
    print("stats:", stats, "| rank:", rank, "| wrote", out, len(svg), "bytes")


if __name__ == "__main__":
    main()
