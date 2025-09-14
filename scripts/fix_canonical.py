#!/usr/bin/env python3
import os, re
from pathlib import Path

# === Настройки через ENV ===
BASE_URL   = os.environ.get("BASE_URL", "").strip()     # опционально: зафиксировать домен руками
SITE_ROOT  = os.environ.get("SITE_ROOT", ".").strip()   # если сайт лежит не в корне, укажи папку (например "docs")

REPO = os.environ.get("GITHUB_REPOSITORY", "")
OWNER, REPO_NAME = (REPO.split("/", 1) + [""])[:2]

ROOT = Path(SITE_ROOT).resolve()
changed_files = 0
skipped_files = 0

def detect_base_url() -> str:
    # 1) CNAME в корне (GitHub Pages кастомный домен)
    cname_path = Path("CNAME")
    if cname_path.exists():
        domain = cname_path.read_text(encoding="utf-8").strip().splitlines()[0].strip()
        if domain:
            if not domain.startswith("http"):
                return f"https://{domain}"
            return domain

    # 2) Репозиторий-пользовательский сайт: owner.github.io
    if REPO_NAME.endswith(".github.io"):
        return f"https://{REPO_NAME}"

    # 3) Проектный сайт: https://owner.github.io/repo
    if OWNER and REPO_NAME:
        return f"https://{OWNER}.github.io/{REPO_NAME}"

    # 4) Фоллбэк — обязателен (если ничего не нашли)
    return ""

def build_canonical_for(path: Path, base: str) -> str:
    """
    Генерируем self-canonical для HTML-файла.
    - index.html -> .../<dir>/
    - прочие .html -> .../<relpath>.html
    """
    base = base.rstrip("/")
    rel = path.relative_to(ROOT).as_posix()  # относительный путь от ROOT
    # Не канонимизируем спец-страницы (верификации и 404), при желании можно убрать исключения
    name = path.name.lower()
    if name == "404.html" or name.startswith("yandex_") or name.startswith("google"):
        return ""  # пропустим

    if rel.endswith("index.html"):
        url_path = "/" + rel[:-10]  # убираем "index.html"
    else:
        url_path = "/" + rel

    # Нормализация: заменить "//" внутри пути (на всякий)
    url_path = re.sub(r"/{2,}", "/", url_path)
    # Если получилось просто "/" (корень) — отлично
    return f"{base}{url_path}"

def ensure_canonical(html: str, canonical_url: str) -> str:
    """
    Удаляем все существующие canonical и вставляем новый перед </head>.
    Плюс лечим редкий баг с meta robots, в котором случайно стоит URL.
    """
    # 1) вычистим все <link rel="canonical" ...>
    html = re.sub(r'(?is)<link[^>]+rel=[\'"]canonical[\'"][^>]*>', '', html)

    # 2) вставим правильный
    tag = f'<link rel="canonical" href="{canonical_url}">'
    inserted = False

    m = re.search(r'(?is)</head\s*>', html)
    if m:
        pos = m.start()
        html = html[:pos] + tag + "\n" + html[pos:]
        inserted = True

    # 3) фикс мета-роботс, если контент случайно URL
    html = re.sub(
        r'(?is)<meta[^>]+name=[\'"]robots[\'"][^>]+content=[\'"]https?://[^\'"]+[\'"][^>]*>',
        '<meta name="robots" content="index, follow">', html
    )

    # Если <head> отсутствует — предупредим, но попробуем в начало файла
    if not inserted:
        html = tag + "\n" + html

    return html

def main():
    global changed_files, skipped_files
    base = BASE_URL or detect_base_url()
    if not base:
        raise SystemExit("Не удалось определить BASE_URL. Задайте переменную среды BASE_URL или добавьте CNAME/проверьте GITHUB_REPOSITORY.")

    print(f"[i] BASE_URL = {base}")
    if not ROOT.exists():
        raise SystemExit(f"Каталог SITE_ROOT не найден: {ROOT}")

    for p in ROOT.rglob("*.html"):
        try:
            html = p.read_text(encoding="utf-8")
        except Exception as e:
            print(f"[!] Пропуск (не читается): {p} ({e})")
            skipped_files += 1
            continue

        can_url = build_canonical_for(p, base)
        if not can_url:
            # исключённые файлы
            continue

        new_html = ensure_canonical(html, can_url)

        if new_html != html:
            p.write_text(new_html, encoding="utf-8")
            changed_files += 1
            print(f"[fix] {p} -> {can_url}")

    print(f"\nГотово. Изменено файлов: {changed_files}. Пропущено: {skipped_files}.")

if __name__ == "__main__":
    main()
