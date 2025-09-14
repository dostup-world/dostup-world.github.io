#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Генерит rss.xml для всего проекта.
Берёт все HTML-страницы (кроме мусора/верификаций), тянет <title>, <meta name="description">,
дату последнего коммита файла (git), делает абсолютные ссылки и собирает RSS 2.0.

ENV:
  BASE_URL              базовый URL сайта (по умолчанию https://proxy-plus.github.io)
  SITE_TITLE            заголовок RSS (по умолчанию "SAFENET-VPN — Руководства и инструкции по VPN")
  SITE_DESCRIPTION      описание RSS
  MAX_ITEMS             макс. кол-во элементов (0 = без лимита), по умолчанию 0
"""

import os, re, sys, subprocess, html, pathlib, time
from datetime import datetime, timezone
from email.utils import format_datetime

ROOT = pathlib.Path(__file__).resolve().parents[1]
BASE_URL = os.getenv("BASE_URL", "https://proxy-plus.github.io").rstrip("/")
SITE_TITLE = os.getenv("SITE_TITLE", "SAFENET-VPN — Руководства и инструкции по VPN")
SITE_DESCRIPTION = os.getenv("SITE_DESCRIPTION", "Гайды по VPN, обходу блокировок и скачиванию видео (YouTube/VK/TG/TikTok, MP3).")
MAX_ITEMS = int(os.getenv("MAX_ITEMS", "0"))

EXCLUDE_DIRS = {
    ".git", ".github", "tools", "assets", "images", "img", "fonts", "css", "js", "vendor", "node_modules"
}
EXCLUDE_FILES_REGEX = re.compile(
    r"""(?xi)
    ^404\.html$|
    ^CNAME$|
    ^sitemap\.xml$|
    ^rss\.xml$|
    ^feed\.xml$|
    ^atom\.xml$|
    ^google[0-9a-zA-Z]+\.html$|
    ^yandex_[0-9a-zA-Z]+\.html$
    """
)

TITLE_RE = re.compile(r"<title[^>]*>(.*?)</title>", re.IGNORECASE | re.DOTALL)
META_DESC_RE = re.compile(
    r"""<meta\s+[^>]*name=["']description["'][^>]*content=["'](.*?)["'][^>]*>""",
    re.IGNORECASE | re.DOTALL
)
H1_RE = re.compile(r"<h1[^>]*>(.*?)</h1>", re.IGNORECASE | re.DOTALL)
P_RE = re.compile(r"<p[^>]*>(.*?)</p>", re.IGNORECASE | re.DOTALL)

def read_text_safe(path: pathlib.Path) -> str:
    try:
        return path.read_text("utf-8", errors="ignore")
    except Exception:
        return ""

def strip_tags(s: str) -> str:
    return re.sub(r"<[^>]+>", "", s)

def get_title(html_text: str) -> str:
    m = TITLE_RE.search(html_text)
    if not m:
        return ""
    t = strip_tags(m.group(1)).strip()
    return html.unescape(re.sub(r"\s+", " ", t))[:300]

def get_description(html_text: str) -> str:
    m = META_DESC_RE.search(html_text)
    if m:
        desc = strip_tags(m.group(1)).strip()
        return html.unescape(re.sub(r"\s+", " ", desc))[:500]
    # fallback: h1 или первый параграф
    for rx in (H1_RE, P_RE):
        m = rx.search(html_text)
        if m:
            d = strip_tags(m.group(1)).strip()
            if d:
                return html.unescape(re.sub(r"\s+", " ", d))[:500]
    return ""

def to_rfc2822(dt: datetime) -> str:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return format_datetime(dt)

def git_last_commit_iso(path: pathlib.Path) -> datetime | None:
    try:
        out = subprocess.check_output(
            ["git", "log", "-1", "--format=%cI", "--", str(path)],
            cwd=str(ROOT),
            stderr=subprocess.DEVNULL
        ).decode("utf-8").strip()
        if out:
            # 2025-09-03T14:22:00+03:00
            return datetime.fromisoformat(out)
    except Exception:
        pass
    return None

def file_mtime_dt(path: pathlib.Path) -> datetime:
    return datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)

def to_url(rel: pathlib.Path) -> str:
    rel_posix = rel.as_posix()
    if rel_posix.endswith("index.html"):
        url = "/" + rel.parent.as_posix().rstrip("/") + "/"
        return (BASE_URL + url).replace("//", "/").replace(":/", "://")
    else:
        url = "/" + rel_posix
        return (BASE_URL + url).replace("//", "/").replace(":/", "://")

def collect_items():
    items = []
    for path in ROOT.rglob("*.html"):
        # пропуски папок
        parts = set(path.relative_to(ROOT).parts)
        if parts & EXCLUDE_DIRS:
            continue
        name = path.name
        if EXCLUDE_FILES_REGEX.match(name):
            continue

        rel = path.relative_to(ROOT)
        html_text = read_text_safe(path)
        title = get_title(html_text)
        if not title:
            continue
        desc = get_description(html_text)
        link = to_url(rel)

        dt = git_last_commit_iso(path) or file_mtime_dt(path)
        pub = to_rfc2822(dt)

        items.append({
            "title": title,
            "link": link,
            "guid": link,
            "pubDate": pub,
            "dt_sort": dt,
            "description": desc or title
        })
    # сортировка по дате
    items.sort(key=lambda x: x["dt_sort"], reverse=True)
    if MAX_ITEMS and MAX_ITEMS > 0:
        items = items[:MAX_ITEMS]
    return items

def render_rss(items):
    now = to_rfc2822(datetime.now(timezone.utc))
    lines = []
    lines.append('<?xml version="1.0" encoding="UTF-8"?>')
    lines.append('<rss version="2.0" xmlns:media="http://search.yahoo.com/mrss/">')
    lines.append("  <channel>")
    lines.append(f"    <title>{html.escape(SITE_TITLE)}</title>")
    lines.append(f"    <link>{html.escape(BASE_URL + '/')}</link>")
    lines.append(f"    <description>{html.escape(SITE_DESCRIPTION)}</description>")
    lines.append("    <language>ru-RU</language>")
    lines.append(f"    <lastBuildDate>{now}</lastBuildDate>")
    lines.append("    <generator>generate_rss.py</generator>")
    for it in items:
        lines.append("    <item>")
        lines.append(f"      <title>{html.escape(it['title'])}</title>")
        lines.append(f"      <link>{html.escape(it['link'])}</link>")
        lines.append(f"      <guid>{html.escape(it['guid'])}</guid>")
        lines.append(f"      <pubDate>{it['pubDate']}</pubDate>")
        lines.append(f"      <description>{html.escape(it['description'])}</description>")
        lines.append("    </item>")
    lines.append("  </channel>")
    lines.append("</rss>")
    return "\n".join(lines)

def main():
    items = collect_items()
    rss = render_rss(items)
    out_path = ROOT / "rss.xml"
    out_path.write_text(rss, "utf-8")
    print(f"OK: rss.xml written with {len(items)} items at {out_path}")

if __name__ == "__main__":
    sys.exit(main())
