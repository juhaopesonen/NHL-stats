"""RSS-syöte raporteista (docs/feed.xml).

Jokaisen raportin tiivistelmä tallennetaan data/feed_items.json-tiedostoon, josta
syöte kootaan. Saman päivän raportin päivitys korvaa tiivistelmän, mutta guid ja
julkaisuaika pysyvät samoina, jottei syötelukija ilmoita samasta raportista uudelleen.
"""
import json
from datetime import date, datetime, timezone
from email.utils import format_datetime
from html import escape

from .config import DATA_DIR, DOCS_DIR, SITE_URL
from .fmt import day_fi

ITEMS_FILE = DATA_DIR / "feed_items.json"
MAX_ITEMS = 30


def _load() -> dict:
    if ITEMS_FILE.exists():
        return json.loads(ITEMS_FILE.read_text(encoding="utf-8"))
    return {}


def update(day: date, n_games: int, highlights: list[str], finn_text: str) -> None:
    items = _load()
    key = day.isoformat()
    published = items.get(key, {}).get("published") or datetime.now(timezone.utc).isoformat(timespec="seconds")
    items[key] = {
        "published": published,
        "title": f"NHL-yöraportti {day.day}.{day.month}.{day.year} – {n_games} ottelua",
        "highlights": highlights,
        "finns": finn_text,
    }
    ITEMS_FILE.write_text(json.dumps(items, ensure_ascii=False, indent=1, sort_keys=True) + "\n",
                          encoding="utf-8")
    _write_feed(items)


def _write_feed(items: dict) -> None:
    entries = []
    for key in sorted(items, reverse=True)[:MAX_ITEMS]:
        it = items[key]
        d = date.fromisoformat(key)
        link = f"{SITE_URL}raportit/{key}.html"
        body = "".join(f"<li>{escape(h)}</li>" for h in it["highlights"])
        desc = (f"<p>Ottelut {day_fi(d)}.</p><ul>{body}</ul>"
                f"<p>Suomalaiset: {escape(it['finns'])}</p><p><a href=\"{link}\">Koko raportti</a></p>")
        pub = format_datetime(datetime.fromisoformat(it["published"]))
        entries.append(f"""  <item>
    <title>{escape(it['title'])}</title>
    <link>{link}</link>
    <guid isPermaLink="true">{link}</guid>
    <pubDate>{pub}</pubDate>
    <description>{escape(desc)}</description>
  </item>""")
    now = format_datetime(datetime.now(timezone.utc))
    xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom">
<channel>
  <title>NHL-yöraportti</title>
  <link>{SITE_URL}</link>
  <atom:link href="{SITE_URL}feed.xml" rel="self" type="application/rss+xml"/>
  <description>NHL:n yön otteluiden syvädata ja nostot suomeksi: xG, putket, suomalaiset ja loukkaantumiset.</description>
  <language>fi</language>
  <lastBuildDate>{now}</lastBuildDate>
{chr(10).join(entries)}
</channel>
</rss>
"""
    (DOCS_DIR / "feed.xml").write_text(xml, encoding="utf-8")
