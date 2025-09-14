#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Добавляет/обновляет код Яндекс.Метрики (id=103602117) во все HTML-страницы.
- Вставляет перед </head> (или перед </body>, если </head> нет).
- Если найдёт другую Метрику — заменит её id на 103602117.
- Не дублирует, если нужный код уже есть.

Запуск:
    python tools/inject_metrika.py
    python tools/inject_metrika.py --dry-run
"""

from pathlib import Path
import re
import argparse

TARGET_ID = "103602117"

SNIPPET = """<!-- Yandex.Metrika counter -->
<script type="text/javascript">
    (function(m,e,t,r,i,k,a){
        m[i]=m[i]||function(){(m[i].a=m[i].a||[]).push(arguments)};
        m[i].l=1*new Date();
        for (var j = 0; j < document.scripts.length; j++) {if (document.scripts[j].src === r) { return; }}
        k=e.createElement(t),a=e.getElementsByTagName(t)[0],k.async=1,k.src=r,a.parentNode.insertBefore(k,a)
    })(window, document,'script','https://mc.yandex.ru/metrika/tag.js?id=103602117', 'ym');

    ym(103602117, 'init', {ssr:true, webvisor:true, clickmap:true, ecommerce:"dataLayer", accurateTrackBounce:true, trackLinks:true});
</script>
<noscript><div><img src="https://mc.yandex.ru/watch/103602117" style="position:absolute; left:-9999px;" alt="" /></div></noscript>
<!-- /Yandex.Metrika counter -->
"""

# Регексы для поиска существующей Метрики
RE_TAG_JS = re.compile(r"https://mc\.yandex\.ru/metrika/tag\.js\?id=(\d+)")
RE_WATCH  = re.compile(r"https://mc\.yandex\.ru/watch/(\d+)")
RE_YM_INIT = re.compile(r"ym\(\s*(\d+)\s*,\s*'init'")

def has_target_id(text: str) -> bool:
    # Любой из признаков с нужным id
    return (f"metrika/tag.js?id={TARGET_ID}" in text
            or f"watch/{TARGET_ID}" in text
            or re.search(rf"ym\(\s*{TARGET_ID}\s*,\s*'init'", text) is not None)

def replace_other_id(text: str) -> tuple[str, bool]:
    """Если найдена Метрика с другим id — заменить на целевой. Вернёт (text, changed?)."""
    changed = False

    def repl_tag(m):
        nonlocal changed
        old = m.group(1)
        if old != TARGET_ID:
            changed = True
            return m.group(0).replace(old, TARGET_ID)
        return m.group(0)

    def repl_watch(m):
        nonlocal changed
        old = m.group(1)
        if old != TARGET_ID:
            changed = True
            return m.group(0).replace(old, TARGET_ID)
        return m.group(0)

    def repl_init(m):
        nonlocal changed
        old = m.group(1)
        if old != TARGET_ID:
            changed = True
            start, end = m.span(1)
            return text[:start] + TARGET_ID + text[end:]
        return m.group(0)

    text_new = RE_TAG_JS.sub(repl_tag, text)
    text_new = RE_WATCH.sub(repl_watch, text_new)
    text_new = RE_YM_INIT.sub(lambda m: f"ym({TARGET_ID}, 'init'", text_new)

    return text_new, changed

def inject(text: str) -> tuple[str, bool]:
    """Вставить сниппет перед </head> (или </body>). Вернёт (text, injected?)."""
    lower = text.lower()
    insert_at = None

    head_idx = lower.rfind("</head>")
    body_idx = lower.rfind("</body>")

    if head_idx != -1:
        insert_at = head_idx
    elif body_idx != -1:
        insert_at = body_idx

    if insert_at is not None:
        return text[:insert_at] + "\n" + SNIPPET + "\n" + text[insert_at:], True
    else:
        # если нет head/body — просто в конец файла
        return text + "\n" + SNIPPET + "\n", True

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=".", help="корень проекта (по умолчанию текущая папка)")
    ap.add_argument("--dry-run", action="store_true", help="только показать, что будет изменено")
    args = ap.parse_args()

    root = Path(args.root)
    files = list(root.rglob("*.html")) + list(root.rglob("*.htm"))
    # Исключим node_modules и скрытые папки на всякий.
    files = [p for p in files if "node_modules" not in p.parts and ".git" not in p.parts]

    added = updated = skipped = 0
    touched = []

    for p in files:
        try:
            text = p.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            text = p.read_text(encoding="utf-8", errors="ignore")

        if has_target_id(text):
            skipped += 1
            continue

        # Если есть Метрика с другим id — заменим
        text2, changed = replace_other_id(text)
        if changed:
            updated += 1
            touched.append(("update", p))
            if not args.dry_run:
                p.write_text(text2, encoding="utf-8")
            continue

        # Иначе — вставим сниппет
        text3, injected = inject(text)
        if injected:
            added += 1
            touched.append(("add", p))
            if not args.dry_run:
                p.write_text(text3, encoding="utf-8")

    print(f"\nГотово. Добавлено: {added}, обновлено: {updated}, без изменений: {skipped}. Всего файлов: {len(files)}")
    if touched:
        print("\nИзменённые файлы:")
        for kind, p in touched:
            print(f"  [{kind}] {p.relative_to(root)}")

if __name__ == "__main__":
    main()
