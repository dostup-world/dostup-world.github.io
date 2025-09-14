#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Генератор sitemap.xml для GitHub Pages (совместим с Google и Яндекс).

- Собирает все *.html (кроме служебных/верификаций).
- Канонизирует URL: /dir/ для index.html, иначе /path.html.
- lastmod = дата последнего git-коммита файла (fallback: mtime).
- Даты в формате W3C/UTC с суффиксом 'Z' — дружит с GSC.
- Экранирует <loc> (если в ссылках будут ?& и т.п.).
- Если урлов очень много — режет на части и делает sitemap_index.xml.
- По желанию дописывает robots.txt со ссылкой на карту.

ENV:
  BASE_URL     базовый URL сайта (по умолчанию https://proxy-plus.github.io)
  MAX_URLS     макс. URL в одном файле (по умолчанию 49000)
  MAKE_ROBOTS  "1" — создать/обновить robots.txt (по умолчанию "0")
"""

import os
import re
import subprocess
import pathlib
from datetime import datetime, timezone
from typing import List
from xml.sax.saxutils import escape

# --- Конфиг -------------------------------------------------------

ROOT = pathlib.Path(__file__).resolve().parents[1]
BASE_URL = os.getenv("BASE_URL", "https://proxy-plus.github.io").rstrip("/")
MAX_URLS = int(os.getenv("MAX_URLS", "49000"))
MAKE_ROBOTS = os.getenv("MAKE_ROBOTS", "0") == "1"

EXCLUDE_DIRS = {
    ".git", ".github", "tools", "assets", "images", "img", "fonts",
    "css", "js", "vendor", "node_modules"
}
EXCLUDE_FILES_RE = re.compile(
    r"""(?xi)
    ^404\.html$|
    ^CNAME$|
    ^sitemap(\-index)?\.xml$|
    ^rss\.xml$|^feed\.xml$|^atom\.xml$|
    ^google[0-9a-zA-Z]+\.html$|
    ^yandex_[0-9a-zA-Z]+\.html$
    """
)

# --- Вспомогалки --------------------------------------------------

def git_last_commit_iso(path: pathlib.Path) -> datetime | None:
    """Последний git-коммит файла (datetime с таймзоной)."""
    try:
        out = subprocess.check_output(
            ["git", "log", "-1", "--format=%cI", "--", str(path)],
            cwd=str(ROOT),
            stderr=subprocess.DEVNULL
        ).decode("utf-8").strip()
        if out:
            return datetime.fromisoformat(out)
    except Exception:
        pass
    return None

def file_lastmod(path: pathlib.Path) -> datetime:
    """UTC, без микросекунд."""
    dt = git_last_commit_iso(path)
    if dt is None:
        dt = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
    return dt.astimezone(timezone.utc).replace(microsecond=0)

def fmt_w3c(dt: datetime) -> str:
    """W3C datetime строго в UTC с 'Z' (любим Гуглом/Яндексом)."""
    return dt.strftime('%Y-%m-%dT%H:%M:%SZ')

def to_url(rel: pathlib.Path) -> str:
    """Канонический абсолютный URL + экранирование (на случай ?&)."""
    rel_posix = rel.as_posix()
    if rel_posix.endswith("index.html"):
        url = "/" + rel.parent.as_posix().rstrip("/") + "/"
    else:
        url = "/" + rel_posix
    full = (BASE_URL + url).replace("//", "/").replace(":/", "://")
    return escape(full)

# --- Сбор URL -----------------------------------------------------

def collect() -> List[dict]:
    items = []
    for p in ROOT.rglob("*.html"):
        parts = set(p.relative_to(ROOT).parts)
        if parts & EXCLUDE_DIRS:
            continue
        if EXCLUDE_FILES_RE.match(p.name):
            continue

        rel = p.relative_to(ROOT)
        loc = to_url(rel)
        dt = file_lastmod(p)
        items.append({
            "loc": loc,
            "lastmod": fmt_w3c(dt),
            "dt": dt
        })

    items.sort(key=lambda x: x["dt"], reverse=True)
    return items

# --- Рендер -------------------------------------------------------

def write_sitemap(path: pathlib.Path, items: List[dict]) -> None:
    head = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
    )
    tail = '</urlset>\n'
    lines = [head]
    for it in items:
        lines.append("  <url>")
        lines.append(f"    <loc>{it['loc']}</loc>")
        lines.append(f"    <lastmod>{it['lastmod']}</lastmod>")
        lines.append("  </url>")
    lines.append(tail)
    path.write_text("\n".join(lines), "utf-8")

def write_sitemap_index(path: pathlib.Path, parts: List[str]) -> None:
    head = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
    )
    tail = '</sitemapindex>\n'
    now = fmt_w3c(datetime.now(timezone.utc).replace(microsecond=0))
    lines = [head]
    for p in parts:
        lines.append("  <sitemap>")
        loc = f"{BASE_URL}/{p}"
        lines.append(f"    <loc>{escape(loc)}</loc>")
        lines.append(f"    <lastmod>{now}</lastmod>")
        lines.append("  </sitemap>")
    lines.append(tail)
    path.write_text("\n".join(lines), "utf-8")

def ensure_robots():
    """Создаём/дополняем robots.txt ссылкой на sitemap."""
    robots = ROOT / "robots.txt"
    line = f"Sitemap: {BASE_URL}/sitemap.xml\n"
    if robots.exists():
        txt = robots.read_text("utf-8", errors="ignore")
        if "Sitemap:" not in txt:
            robots.write_text(txt.rstrip() + "\n" + line, "utf-8")
    else:
        robots.write_text("User-agent: *\nAllow: /\n" + line, "utf-8")

# --- main ---------------------------------------------------------

def main():
    items = collect()
    out_main = ROOT / "sitemap.xml"

    if len(items) <= MAX_URLS:
        write_sitemap(out_main, items)
        # если раньше был индекс — уберём, чтобы не мешал
        idx = ROOT / "sitemap_index.xml"
        if idx.exists():
            idx.unlink()
    else:
        # режем на пачки и собираем индекс
        parts = []
        for i in range(0, len(items), MAX_URLS):
            chunk = items[i:i + MAX_URLS]
            name = f"sitemap-{i // MAX_URLS + 1}.xml"
            write_sitemap(ROOT / name, chunk)
            parts.append(name)
        write_sitemap_index(ROOT / "sitemap_index.xml", parts)
        # главный файл сделаем индексом, указывающим на sitemap_index.xml
        out_main.write_text(
            '<?xml version="1.0" encoding="UTF-8"?>\n'
            '<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
            f'  <sitemap>\n    <loc>{escape(BASE_URL + "/sitemap_index.xml")}</loc>\n'
            f'    <lastmod>{fmt_w3c(datetime.now(timezone.utc).replace(microsecond=0))}</lastmod>\n'
            '  </sitemap>\n'
            '</sitemapindex>\n',
            "utf-8"
        )

    if MAKE_ROBOTS:
        ensure_robots()

    print(f"OK: sitemap written. Total URLs: {len(items)}")

if __name__ == "__main__":
    main()
