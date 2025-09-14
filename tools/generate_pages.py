#!/usr/bin/env python3
# coding: utf-8
"""
Генерим НЧ-страницы «Как зайти на … в России» из CSV.

Добавлено:
- Автоопределение домена для канонического адреса и ссылок (CNAME → SITE_DOMAIN → GITHUB_REPOSITORY)
- Canonical, OG/Twitter, hreflang, article:modified_time
- Перелинковка «Смотрите также» по категории (до 6 ссылок)
- Корректный Yandex.Metrika (ID 104025851)
- Партнёрские ссылки помечены rel="sponsored nofollow noopener"

Запуск локально/в CI:
    python tools/generate_pages.py
"""

import os, csv, sys, datetime
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
CSV  = REPO / "tools" / "pages.csv"

# ---------- Определение BASE_URL (для canonical/OG и навигации)
def detect_base_url() -> str:
    # 1) CNAME (GitHub Pages custom domain)
    cname = (REPO / "CNAME")
    if cname.exists():
        host = cname.read_text(encoding="utf-8").strip().splitlines()[0].strip()
        if host:
            return f"https://{host}".rstrip("/")
    # 2) Переменная окружения (удобно в CI через repo Variables)
    env_domain = os.getenv("SITE_DOMAIN", "").strip().rstrip("/")
    if env_domain.startswith("http"):
        return env_domain
    # 3) Имя репозитория
    repo = os.getenv("GITHUB_REPOSITORY", "")  # owner/repo
    if "/" in repo:
        owner, name = repo.split("/", 1)
        if name.endswith(".github.io"):
            # user/organization pages
            return f"https://{name}".rstrip("/")
        else:
            # project pages
            return f"https://{owner}.github.io/{name}".rstrip("/")
    # 4) Фолбэк — можно поменять при желании
    return "https://dostup-world.github.io"

BASE_URL = detect_base_url()

# ---------- Метрика (ID 104025851)
METRIKA = """<!-- Yandex.Metrika counter -->
<script type="text/javascript">
    (function(m,e,t,r,i,k,a){
        m[i]=m[i]||function(){(m[i].a=m[i].a||[]).push(arguments)};
        m[i].l=1*new Date();
        for (var j = 0; j < document.scripts.length; j++) { if (document.scripts[j].src === r) { return; } }
        k=e.createElement(t),a=e.getElementsByTagName(t)[0],k.async=1,k.src=r,a.parentNode.insertBefore(k,a)
    })(window, document,'script','https://mc.yandex.ru/metrika/tag.js?id=104025851', 'ym');

    ym(104025851, 'init', {ssr:true, webvisor:true, clickmap:true, ecommerce:"dataLayer", accurateTrackBounce:true, trackLinks:true});
</script>
<noscript><div><img src="https://mc.yandex.ru/watch/104025851" style="position:absolute; left:-9999px;" alt="" /></div></noscript>
<!-- /Yandex.Metrika counter -->"""

# ---------- Стиль
STYLE = """
<link href="https://cdn.jsdelivr.net/npm/tailwindcss@2.2.19/dist/tailwind.min.css" rel="stylesheet">
<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/@fortawesome/fontawesome-free@6.4.0/css/all.min.css">
<style>
html{scroll-behavior:smooth}
:root{--primary:#2563eb;--secondary:#1e40af;--accent:#10b981;--danger:#ef4444;--card:#1e293b}
body{font-family:Inter,-apple-system,BlinkMacSystemFont,sans-serif;background:linear-gradient(135deg,#0f172a 0%,#1e293b 100%);color:#e2e8f0;line-height:1.6}
.nav{background:rgba(15,23,42,.95);backdrop-filter:blur(10px);border-bottom:1px solid #334155}
.card{background:var(--card);border:1px solid #334155;border-radius:14px}
.btn{background:linear-gradient(135deg,#22c55e,#16a34a);color:#fff;padding:12px 18px;border-radius:12px;font-weight:800;display:inline-flex;gap:10px;align-items:center;text-decoration:none}
.btn-alt{background:linear-gradient(135deg,var(--primary),var(--secondary));color:#fff;padding:12px 18px;border-radius:12px;font-weight:800;display:inline-flex;gap:10px;align-items:center;text-decoration:none}
.badge{display:inline-block;background:#0ea5e9;color:#fff;padding:.15rem .5rem;border-radius:.5rem;font-size:.75rem;font-weight:700}
.hero{background:linear-gradient(135deg,#1e40af 0%, #3730a3 50%, #7c3aed 100%);position:relative;overflow:hidden}
.hero:before{content:'';position:absolute;inset:0;background:radial-gradient(900px 350px at 10% -10%, rgba(255,255,255,.08), transparent)}
ul li::marker{color:#60a5fa}
code{background:#0b1220;padding:.12rem .4rem;border-radius:.35rem}
</style>
"""

def _split(s: str):
    s = (s or "").strip()
    if not s: return []
    return [x.strip() for x in s.split("|") if x.strip()]

def render_list(items):
    if not items: return "<p class='text-gray-400'>—</p>"
    lis = "\n".join([f"<li>{i}</li>" for i in items])
    return f"<ul class='list-disc ml-5 space-y-1 text-gray-200'>\n{lis}\n</ul>"

def normalize_path(url: str) -> str:
    url = url.strip()
    if not url.startswith("/"): url = "/" + url
    if not url.endswith("/"):  url = url + "/"
    return url

def ensure_path(url: str) -> Path:
    return REPO / normalize_path(url).lstrip("/") / "index.html"

def absolutize(url_path: str) -> str:
    """BASE_URL + normalized path."""
    path = normalize_path(url_path)
    return f"{BASE_URL.rstrip('/')}{path}"

def make_related(all_rows, current_row, limit=6):
    """Берём до N страниц той же категории, исключая текущую. Анкор = h1."""
    cat = (current_row.get("category") or "").strip().lower()
    cur_url = normalize_path(current_row["url"])
    pool = [r for r in all_rows if (r.get("category","").strip().lower() == cat) and normalize_path(r["url"]) != cur_url]
    # стабильный порядок: по service, затем по url
    pool.sort(key=lambda r: (r.get("service",""), r.get("url","")))
    return pool[:limit]

def head_seo(row, canonical_url, iso_mod):
    title = row["title"].strip()
    desc  = row["description"].strip()
    return f"""
<link rel="canonical" href="{canonical_url}">
<link rel="alternate" hreflang="ru-RU" href="{canonical_url}">
<link rel="alternate" hreflang="x-default" href="{canonical_url}">
<meta name="robots" content="index,follow">
<!-- OG / Twitter -->
<meta property="og:title" content="{title}">
<meta property="og:description" content="{desc}">
<meta property="og:type" content="article">
<meta property="og:url" content="{canonical_url}">
<meta property="og:site_name" content="Internet Security Hub">
<meta property="article:modified_time" content="{iso_mod}">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="{title}">
<meta name="twitter:description" content="{desc}">
"""

def render_related(related_rows):
    if not related_rows:
        return ""
    items = []
    for r in related_rows:
        href = absolutize(r["url"])
        anchor = (r.get("h1") or r.get("title") or href).strip()
        items.append(f'<li><a class="underline hover:no-underline" href="{href}">{anchor}</a></li>')
    return f"""
  <div class="card p-6 mb-8">
    <h2 class="text-2xl font-bold mb-2">Смотрите также</h2>
    <ul class="list-disc ml-5 space-y-1 text-gray-200">
      {'\n      '.join(items)}
    </ul>
  </div>
"""

# --- Новое: безопасный текст «О сервисе» по категориям + фолбэк
NOTES_BY_CATEGORY = {
    "social":  "Соцсети часто режутся по IP и ASN провайдера. Нужен VPN с обфускацией.",
    "video":   "Видеосервисы помимо сайта блокируют CDN — DNS редко спасает, лучше VPN.",
    "games":   "Игровые сервисы чувствительны к задержке: берите ближайшие страны ЕС.",
    "work":    "Рабочие сервисы иногда блокируются по корпоративным политикам и IP-пулу.",
    "media":   "Музыка/стриминг фильтруется по гео. Без стабильного VPN часть треков недоступна.",
    "other":   "От провайдера к провайдеру фильтры разные — пробуйте несколько подходов.",
    # главное дополнение:
    "outage":  ("Интернет-доступ может временно пропадать из-за работ у оператора, перегрузки "
                "базовых станций или фильтрации трафика. Временно помогает: переключение 3G/4G/5G, "
                "перезапуск устройств, ручной DNS (1.1.1.1/8.8.8.8) и VPN с обфускацией.")
}

def page_html(row: dict, related_html: str) -> str:
    title       = row["title"].strip()
    desc        = row["description"].strip()
    h1          = row["h1"].strip()
    lead        = row["lead"].strip()
    service     = row["service"].strip()
    category    = row["category"].strip().lower()
    country     = row["country_hint"].strip()
    problems    = render_list(_split(row["problems"]))
    fixes       = render_list(_split(row["fixes"]))
    errors      = render_list(_split(row["errors"]))
    faq1_q      = row["faq1_q"].strip()
    faq1_a      = row["faq1_a"].strip()
    faq2_q      = row["faq2_q"].strip()
    faq2_a      = row["faq2_a"].strip()
    extra_html  = (row.get("extra_html","") or "").replace("{","&#123;").replace("}","&#125;")
    noindex     = (row.get("noindex","no").strip().lower() in ("yes","true","1"))

    # даты
    now = datetime.datetime.utcnow()
    today_human = now.strftime("%d.%m.%Y")
    iso_mod = now.replace(microsecond=0).isoformat() + "Z"

    # robots
    robots = '<meta name="robots" content="noindex,follow">' if noindex else ""

    # canonical для текущей страницы
    canonical_url = absolutize(row["url"])

    # Безопасно берём текст «О сервисе»: сначала по категории, иначе фолбэк к "other"
    category_note = NOTES_BY_CATEGORY.get(category) or NOTES_BY_CATEGORY["other"]

    # Карточку «О сервисе» показываем только если текст не пуст
    service_card_html = ""
    if category_note:
        service_card_html = f"""
  <div class="card p-6 mb-8">
    <div class="badge mb-2">О сервисе</div>
    <p class="text-gray-200">{category_note}</p>
  </div>
"""

    # Навигация
    nav_home   = BASE_URL + "/"
    nav_guide  = BASE_URL + "/guide/"
    nav_dev    = BASE_URL + "/devices/"
    nav_stream = BASE_URL + "/streaming/"

    return f"""<!DOCTYPE html><html lang="ru"><head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{title}</title>
<meta name="description" content="{desc}">
{robots}
{head_seo(row, canonical_url, iso_mod)}
{STYLE}
{METRIKA}
</head><body>

<!-- NAV -->
<nav class="nav sticky top-0 z-50">
  <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
    <a href="{nav_home}" class="text-xl font-bold text-white flex items-center gap-2">
      <i class="fas fa-shield-alt text-blue-400"></i> Internet Security Hub
    </a>
    <div class="hidden md:flex items-center space-x-6">
      <a href="{nav_guide}" class="text-gray-300 hover:text-white">Руководства</a>
      <a href="{nav_dev}" class="text-gray-300 hover:text-white">Устройства</a>
      <a href="{nav_stream}" class="text-gray-300 hover:text-white">Стриминг</a>
      <a href="https://t.me/SafeNetVpn_bot?start=afrrica" rel="sponsored nofollow noopener" class="btn-alt"><i class="fab fa-telegram"></i> Получить VPN</a>
    </div>
  </div>
</nav>

<!-- HERO -->
<section class="hero py-14">
  <div class="max-w-5xl mx-auto px-4 text-center relative z-10">
    <h1 class="text-4xl md:text-5xl font-extrabold text-white mb-3">{h1}</h1>
    <p class="text-blue-100 text-lg md:text-xl mb-6">{lead}</p>
    <div class="flex flex-col sm:flex-row gap-3 justify-center">
      <a href="https://t.me/SafeNetVpn_bot?start=afrrica" rel="sponsored nofollow noopener" class="btn"><i class="fab fa-telegram"></i> Быстрое решение</a>
      <a href="#methods" class="btn-alt"><i class="fas fa-list"></i> Все способы</a>
    </div>
    <p class="text-blue-200 text-xs mt-4 opacity-80">Обновлено: <time datetime="{iso_mod}">{today_human}</time></p>
  </div>
</section>

<main class="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8 py-10" id="methods">

  {service_card_html}

  <div class="grid md:grid-cols-2 gap-6 mb-8">
    <div class="card p-6">
      <h2 class="text-2xl font-bold mb-2">Почему {service} не открывается в РФ</h2>
      {problems}
    </div>
    <div class="card p-6">
      <h2 class="text-2xl font-bold mb-2">Быстрые решения</h2>
      {fixes}
      <p class="text-gray-400 text-sm mt-3">Страна сервера: <b>{country}</b></p>
    </div>
  </div>

  <div class="card p-6 mb-8">
    <h2 class="text-2xl font-bold mb-2">Типичные ошибки</h2>
    {errors}
  </div>

  <div class="card p-6 mb-8">
    <h2 class="text-2xl font-bold mb-2">Рекомендуем</h2>
    <p class="mb-4">Проще всего включить готовый профиль VPN: европейский сервер + обфушкация, чтобы {service} открылся без бубна.</p>
    <div class="flex flex-wrap gap-3">
      <a class="btn" href="https://t.me/SafeNetVpn_bot?start=afrrica" rel="sponsored nofollow noopener"><i class="fab fa-telegram"></i> Подключить SAFENET-VPN</a>
      <a class="btn-alt" href="https://t.me/normwpn_bot?start=partner_228691787" rel="sponsored nofollow noopener">Альтернативный VPN</a>
    </div>
  </div>

  {extra_html}

  <div class="grid md:grid-cols-2 gap-6 mb-8">
    <div class="card p-6">
      <h3 class="text-xl font-bold mb-2">{faq1_q}</h3>
      <p class="text-gray-200">{faq1_a}</p>
    </div>
    <div class="card p-6">
      <h3 class="text-xl font-bold mb-2">{faq2_q}</h3>
      <p class="text-gray-200">{faq2_a}</p>
    </div>
  </div>

  {related_html}

  <div class="mt-10 text-sm text-gray-400">
    *Материал образовательный. Соблюдайте законы вашей страны.
  </div>
</main>

<footer class="bg-slate-900 border-t border-slate-700 py-10 mt-10">
  <div class="max-w-7xl mx-auto px-4 text-center text-gray-400 text-sm">
    © 2025 Internet Security Hub • Гайды по обходу блокировок.
  </div>
</footer>

</body></html>"""

def main():
    if not CSV.exists():
        print(f"Нет файла: {CSV}", file=sys.stderr)
        sys.exit(1)

    with CSV.open(encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        need = {"url","title","description","h1","lead","service","category",
                "country_hint","problems","fixes","errors","faq1_q","faq1_a","faq2_q","faq2_a","extra_html","noindex"}
        if set(reader.fieldnames) != need:
            print("Нужно вот такое множество колонок:\n" + ", ".join(sorted(need)), file=sys.stderr)
            print("А сейчас: " + ", ".join(reader.fieldnames), file=sys.stderr)
            sys.exit(2)
        rows = list(reader)

    # Готовим перелинковку по категории
    created = 0
    for row in rows:
        related = make_related(rows, row, limit=6)
        related_html = render_related(related)

        out = ensure_path(row["url"])
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(page_html(row, related_html), encoding="utf-8")
        created += 1
        print("[ok] ", str(out.relative_to(REPO)))

    print(f"\nГотово. Сгенерировано страниц: {created}")
    print(f"BASE_URL: {BASE_URL}")

if __name__ == "__main__":
    main()

