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


LANG_COLORS = {
    "TypeScript": "#3178c6", "JavaScript": "#f1e05a", "PHP": "#4F5D95",
    "Python": "#3572A5", "Dart": "#00B4AB", "HTML": "#e34c26",
    "CSS": "#563d7c", "Blade": "#f7523f", "Java": "#b07219", "Jupyter Notebook": "#DA5B0B", "SCSS": "#c6538c",
    "Go": "#00ADD8", "C++": "#f34b7d", "Vue": "#41b883",
}


def fetch_contributed():
    # Official metric via GraphQL (same as github-readme-stats "Contributed to")
    try:
        import urllib.request as ur
        body = json.dumps({"query": 'query { user(login: "%s") { repositoriesContributedTo(first: 1) { totalCount } } }' % USER}).encode()
        req = ur.Request("https://api.github.com/graphql", data=body, method="POST")
        req.add_header("Content-Type", "application/json")
        if TOKEN:
            req.add_header("Authorization", "Bearer " + TOKEN)
        with ur.urlopen(req, timeout=30) as r:
            data = json.load(r)
        return data["data"]["user"]["repositoriesContributedTo"]["totalCount"]
    except Exception:
        pass
    # Fallback: distinct foreign repos among authored issues/PRs
    repos = set()
    page = 1
    while page <= 5:
        res = api(f"/search/issues?q=author:{USER}&per_page=100&page={page}")
        items = res.get("items", [])
        if not items:
            break
        for it in items:
            owner_repo = it.get("repository_url", "").rsplit("/repos/", 1)[-1]
            if owner_repo and not owner_repo.lower().startswith(USER.lower() + "/"):
                repos.add(owner_repo)
        page += 1
    return len(repos)


def fetch_languages():
    totals = {}
    page = 1
    while True:
        repos = api(f"/users/{USER}/repos?per_page=100&page={page}&type=owner")
        if not repos:
            break
        for r in repos:
            if r.get("fork"):
                continue
            try:
                langs = api(f"/repos/{USER}/{r['name']}/languages")
            except Exception:
                continue
            for name, size in langs.items():
                totals[name] = totals.get(name, 0) + size
        page += 1
    return sorted(totals.items(), key=lambda kv: -kv[1])


def rank_letter(s):
    # github-readme-stats: exponential cdf 1 - 2^(-x/median), weighted mean
    parts = [
        (s["commits"], 1000, 2),  # median 1000: matches include_all_commits config of the official card
        (s["prs"], 50, 3),
        (s["issues"], 25, 1),
        (0, 2, 1),  # reviews: not fetched, counts as 0
        (s["stars"], 50, 4),
        (s["followers"], 10, 1),
    ]
    score = sum(w * (1 - 2 ** (-x / m)) for x, m, w in parts) / sum(w for _, _, w in parts)
    pct = (1 - score) * 100
    for limit, letter in [(1, "S+"), (12.5, "S"), (25, "A++"), (37.5, "A+"),
                          (50, "A"), (62.5, "A-"), (75, "B+"), (87.5, "B"), (100, "B-")]:
        if pct <= limit:
            return letter
    return "C+"


def fmt(n):
    return f"{n:,}".replace(",", ".")


def build_svg(s, rank, gojo_b64, gw, gh):
    W, H = 1000, 290
    disp_h = 300
    disp_w = round(disp_h * gw / gh)
    img_x = 976 - disp_w
    halo_cx = img_x + disp_w // 2
    halo_cy = 116
    halo_r = 104
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
  <circle cx="{halo_cx}" cy="{halo_cy}" r="{halo_r}" fill="none" stroke="#38bdf8" stroke-width="2.5" opacity="0.9">
    <animate attributeName="r" values="{halo_r};{halo_r + 4};{halo_r}" dur="6s" repeatCount="indefinite"/>
    <animate attributeName="opacity" values="0.9;0.55;0.9" dur="6s" repeatCount="indefinite"/>
  </circle>
  <circle cx="{halo_cx}" cy="{halo_cy}" r="{halo_r + 11}" fill="none" stroke="#a855f7" stroke-width="1.4" opacity="0.5">
    <animate attributeName="r" values="{halo_r + 11};{halo_r + 7};{halo_r + 11}" dur="6s" repeatCount="indefinite"/>
  </circle>
  <image href="data:image/png;base64,{gojo_b64}" x="{img_x}" y="4" width="{disp_w}" height="{disp_h}"/>
  <text x="48" y="66" font-size="21" font-weight="700" letter-spacing="3" fill="#e2e8f0">GITHUB STATS</text>
  <text x="48" y="94" font-size="16" fill="#7dd3fc">@{USER}</text>
  <rect x="48" y="112" width="150" height="3" rx="1.5" fill="#a855f7"/>
  {''.join(cells)}
</g>
<rect x="1" y="1" width="{W-2}" height="{H-2}" rx="18" fill="none" stroke="#a855f7" stroke-opacity="0.4" stroke-width="2"/>
</svg>'''


CARD_BG = """<defs>
  <linearGradient id="space" x1="0" y1="0" x2="0" y2="1">
    <stop offset="0" stop-color="#020010"/><stop offset="1" stop-color="#170b33"/>
  </linearGradient>
</defs>
<rect x="1" y="1" width="493" height="213" rx="10" fill="url(#space)" stroke="#a855f7" stroke-opacity="0.45" stroke-width="2"/>"""
FONT = "'Segoe UI', Ubuntu, 'Helvetica Neue', sans-serif"


def build_detail_svg(s, rank):
    rows = [
        ("Total Stars Earned", s["stars"]),
        ("Total Commits", s["commits"]),
        ("Total PRs", s["prs"]),
        ("Total Issues", s["issues"]),
        ("Contributed to", s["contributed"]),
    ]
    body = []
    for i, (label, val) in enumerate(rows):
        y = 78 + i * 27
        body.append(f'<circle cx="42" cy="{y - 5}" r="3.5" fill="#38bdf8"/>'
                    f'<text x="58" y="{y}" font-size="15.5" fill="#e2e8f0">{label}</text>'
                    f'<text x="330" y="{y}" font-size="15.5" font-weight="700" fill="#f8fafc" text-anchor="end">{fmt(val)}</text>')
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="495" height="215" viewBox="0 0 495 215" font-family="{FONT}">
{CARD_BG}
<text x="32" y="44" font-size="19" font-weight="700" fill="#a855f7">Statistik GitHub</text>
{''.join(body)}
<circle cx="415" cy="112" r="46" fill="none" stroke="#1e293b" stroke-width="9"/>
<circle cx="415" cy="112" r="46" fill="none" stroke="#a855f7" stroke-width="9" stroke-dasharray="289" stroke-dashoffset="70" transform="rotate(-90 415 112)" stroke-linecap="round"/>
<text x="415" y="122" font-size="27" font-weight="800" fill="#e879f9" text-anchor="middle">{rank}</text>
<text x="415" y="182" font-size="11.5" fill="#94a3b8" text-anchor="middle">Rank</text>
</svg>'''


def build_langs_svg(langs):
    top = langs[:6]
    total = sum(v for _, v in langs) or 1
    bar = []
    x = 32.0
    for name, size in top:
        w = 431 * size / total
        bar.append(f'<rect x="{x:.1f}" y="66" width="{max(w - 2, 2):.1f}" height="9" rx="4.5" fill="{LANG_COLORS.get(name, "#94a3b8")}"/>')
        x += w
    body = []
    for i, (name, size) in enumerate(top):
        col = i % 2
        row = i // 2
        lx = 32 + col * 222
        ly = 108 + row * 36
        pct = size / total * 100
        body.append(f'<circle cx="{lx + 5}" cy="{ly - 5}" r="5" fill="{LANG_COLORS.get(name, "#94a3b8")}"/>'
                    f'<text x="{lx + 18}" y="{ly}" font-size="15" fill="#e2e8f0">{name}</text>'
                    f'<text x="{lx + 205}" y="{ly}" font-size="15" fill="#94a3b8" text-anchor="end">{pct:.1f}%</text>')
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="495" height="215" viewBox="0 0 495 215" font-family="{FONT}">
{CARD_BG}
<text x="32" y="44" font-size="19" font-weight="700" fill="#a855f7">Bahasa Teratas</text>
{''.join(bar)}
{''.join(body)}
</svg>'''


def main():
    stats = fetch_stats()
    stats["contributed"] = fetch_contributed()
    rank = rank_letter(stats)
    langs = fetch_languages()
    with open(os.path.join(ROOT, "assets", "gojo-stats-detail.svg"), "w") as f:
        f.write(build_detail_svg(stats, rank))
    with open(os.path.join(ROOT, "assets", "gojo-langs.svg"), "w") as f:
        f.write(build_langs_svg(langs))
    print("langs:", [(n, v) for n, v in langs[:6]])
    with open(os.path.join(HERE, "gojo-cutout.png"), "rb") as f:
        raw = f.read()
    gojo_b64 = base64.b64encode(raw).decode()
    import struct
    gw, gh = struct.unpack(">II", raw[16:24])
    svg = build_svg(stats, rank, gojo_b64, gw, gh)
    out = os.path.join(ROOT, "assets", "gojo-stats.svg")
    with open(out, "w") as f:
        f.write(svg)
    print("stats:", stats, "| rank:", rank, "| wrote", out, len(svg), "bytes")


if __name__ == "__main__":
    main()
