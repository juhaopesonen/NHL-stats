"""HTML-raportin generointi GitHub Pagesia varten (docs/)."""
from datetime import date, datetime, timezone
from html import escape

import pandas as pd

from .config import DOCS_DIR, REPORTS_DIR
from .fmt import day_fi, num, toi
from .injuries import injury_fi, status_fi
from .insights import Insight, return_text

CSS = """
:root{--bg:#f6f7f9;--card:#fff;--text:#16181d;--muted:#5f6673;--line:#e3e6eb;
--accent:#0b5fff;--accent-soft:#e8efff;--good:#0f8a4b;--bad:#c4372c;--bar-a:#8a94a6;--bar-h:#0b5fff}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){--bg:#0f1115;--card:#181b21;
--text:#e8eaee;--muted:#9aa2b1;--line:#2a2f38;--accent:#6c9cff;--accent-soft:#1d2840;--good:#3ccf84;
--bad:#ff7a6e;--bar-a:#5b6475;--bar-h:#6c9cff}}
:root[data-theme="dark"]{--bg:#0f1115;--card:#181b21;--text:#e8eaee;--muted:#9aa2b1;--line:#2a2f38;
--accent:#6c9cff;--accent-soft:#1d2840;--good:#3ccf84;--bad:#ff7a6e;--bar-a:#5b6475;--bar-h:#6c9cff}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--text);font:15px/1.5 system-ui,-apple-system,"Segoe UI",Roboto,sans-serif}
main{max-width:1100px;margin:0 auto;padding:24px 16px 48px}
h1{font-size:28px;margin:0}h2{font-size:20px;margin:36px 0 12px}
.sub{color:var(--muted);margin:4px 0 0}
a{color:var(--accent)}
.insights{list-style:none;padding:0;margin:0;display:grid;gap:8px}
.insights li{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:10px 14px;display:flex;gap:12px;align-items:baseline}
.tag{flex:none;font-size:12px;font-weight:600;background:var(--accent-soft);color:var(--accent);border-radius:999px;padding:2px 10px;white-space:nowrap}
.insights a{margin-left:auto;font-size:13px;white-space:nowrap}
.games{display:grid;grid-template-columns:repeat(auto-fill,minmax(320px,1fr));gap:14px}
.game{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:14px 16px}
.score{display:flex;justify-content:space-between;align-items:center;font-size:20px;font-weight:700}
.score .ot{font-size:12px;color:var(--muted);font-weight:500}
.names{display:flex;justify-content:space-between;color:var(--muted);font-size:12px;margin-bottom:10px}
.bar{display:flex;height:8px;border-radius:4px;overflow:hidden;margin:4px 0 10px;background:var(--line)}
.bar .a{background:var(--bar-a)}.bar .h{background:var(--bar-h)}
table{width:100%;border-collapse:collapse;font-size:13px}
td,th{padding:3px 4px;text-align:right;font-variant-numeric:tabular-nums}
td:first-child,th:first-child{text-align:left}
th{color:var(--muted);font-weight:500;border-bottom:1px solid var(--line)}
.block{margin-top:10px}.block h3{font-size:13px;margin:0 0 4px;color:var(--muted);font-weight:600}
.players{margin:0;padding-left:18px;font-size:13px}
.pos{color:var(--good)}.neg{color:var(--bad)}
.season{display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:14px}
.season .game table{font-size:14px}
.archive{columns:3 160px;padding-left:18px}
footer{margin-top:40px;color:var(--muted);font-size:13px;border-top:1px solid var(--line);padding-top:12px}
.empty{color:var(--muted)}
.game{overflow-x:auto}
.inj td,.inj th{text-align:left}
.inj td:nth-child(4){white-space:nowrap}
.wide{grid-column:1/-1}
details.game{margin-top:14px}
details.game summary{cursor:pointer;font-weight:600}
details.game .game{border:0;padding:0}
.subhead{font-size:15px;margin:20px 0 10px}
#suomalaiset + .insights{margin-bottom:14px}
.game td a{color:inherit;text-decoration:none;border-bottom:1px dotted var(--muted)}
@media (max-width:520px){.insights li{flex-wrap:wrap}.insights a{margin-left:0}}
"""


def _signed(x: float) -> str:
    cls = "pos" if x > 0 else "neg" if x < 0 else ""
    sign = "+" if x > 0 else ""
    return f'<span class="{cls}">{sign}{num(x)}</span>'


def _insights_html(items: list[Insight]) -> str:
    if not items:
        return '<p class="empty">Ei erityisiä nostoja tältä yöltä.</p>'
    rows = []
    for i in items:
        link = f'<a href="#g{i.game_id}">ottelu</a>' if i.game_id else ""
        rows.append(f'<li><span class="tag">{escape(i.kind)}</span><span>{escape(i.text)}</span>{link}</li>')
    return f'<ul class="insights">{"".join(rows)}</ul>'


def _game_html(gm, skaters, goalies, xgt, xgg) -> str:
    gid = gm.game_id
    ot = {"OT": "JA", "SO": "VL"}.get(gm.last_period, "")
    t = xgt[xgt.game_id == gid].set_index("team") if not xgt.empty else pd.DataFrame()
    has_xg = len(t) == 2

    rows = [("Laukaukset maalia kohti", str(gm.away_sog), str(gm.home_sog))]
    bar = ""
    if has_xg:
        a, h = t.loc[gm.away], t.loc[gm.home]
        rows += [
            ("xG (ilman tyhjää maalia)", num(a.xg), num(h.xg)),
            ("xG 5v5", num(a.xg_5v5), num(h.xg_5v5)),
            ("Laukausyritykset (ei blokit)", str(int(a.attempts)), str(int(h.attempts))),
            ("Vaaralliset paikat", str(int(a.hd_attempts)), str(int(h.hd_attempts))),
        ]
        total = a.xg + h.xg or 1
        bar = (f'<div class="bar" title="xG-osuus"><div class="a" style="width:{a.xg / total * 100:.1f}%"></div>'
               f'<div class="h" style="width:{h.xg / total * 100:.1f}%"></div></div>')
    stat_rows = "".join(f"<tr><td>{escape(l)}</td><td>{x}</td><td>{y}</td></tr>" for l, x, y in rows)
    stats = (f'<table><tr><th></th><th>{escape(gm.away)}</th><th>{escape(gm.home)}</th></tr>{stat_rows}</table>')
    if not has_xg:
        stats += '<p class="empty">MoneyPuckin xG-data ei ole vielä saatavilla.</p>'

    scorers = skaters[(skaters.game_id == gid) & (skaters.points > 0)].sort_values(
        ["points", "goals"], ascending=False)
    pl = "".join(
        f"<li>{escape(p['name'])} ({escape(p.team)}) {p.goals}+{p.assists}</li>"
        for _, p in scorers.head(6).iterrows()) or "<li>–</li>"

    gl = goalies[goalies.game_id == gid]
    if not xgg.empty:
        gl = gl.merge(xgg[["game_id", "player_id", "gsax"]], on=["game_id", "player_id"], how="left")
    grows = ""
    for _, g in gl.iterrows():
        sv = g.saves / g.shots_against if g.shots_against else 0
        gsax = _signed(g.gsax) if "gsax" in g and pd.notna(g.gsax) else "–"
        grows += (f"<tr><td>{escape(g['name'])} ({escape(g.team)})</td><td>{g.saves}/{g.shots_against}</td>"
                  f"<td>{num(sv, 3)}</td><td>{gsax}</td><td>{toi(g.toi)}</td></tr>")
    gtable = (f'<table><tr><th>Maalivahti</th><th>Torjunnat</th><th>Torj-%</th><th>GSAx</th><th>Aika</th></tr>'
              f"{grows}</table>")

    return f"""
<article class="game" id="g{gid}">
  <div class="score"><span>{escape(gm.away)} {gm.away_score} – {gm.home_score} {escape(gm.home)}</span><span class="ot">{ot}</span></div>
  <div class="names"><span>{escape(gm.away_name)}</span><span>{escape(gm.home_name)}</span></div>
  {bar}{stats}
  <div class="block"><h3>Pisteet</h3><ul class="players">{pl}</ul></div>
  <div class="block">{gtable}</div>
</article>"""


DECISIONS = {"W": "voitto", "L": "tappio", "O": "JA-tappio"}


def _table(title: str, head: list[str], rows: list[list[str]], cls: str = "") -> str:
    th = "".join(f"<th>{h}</th>" for h in head)
    body = "".join("<tr>" + "".join(f"<td>{c}</td>" for c in r) + "</tr>" for r in rows)
    h3 = f"<h3>{escape(title)}</h3>" if title else ""
    return (f'<div class="game {cls}"><div class="block">{h3}'
            f"<table><tr>{th}</tr>{body}</table></div></div>")


def _finn_html(day: str, skaters, goalies, xg, items: list[Insight], tables, finns: set[int],
               inj: pd.DataFrame | None = None) -> str:
    xgp, xgg = xg["xg_players"], xg["xg_goalies"]
    sk = skaters[(skaters.date == day) & skaters.player_id.isin(finns)]
    gl = goalies[(goalies.date == day) & goalies.player_id.isin(finns)]
    parts = []

    own = [i for i in items if i.player_id in finns]
    if own:
        parts.append(_insights_html(own))

    cards = []
    if not sk.empty:
        if not xgp.empty:
            sk = sk.merge(xgp[["game_id", "player_id", "ixg"]], on=["game_id", "player_id"], how="left")
        else:
            sk = sk.assign(ixg=float("nan"))
        sk = sk.sort_values(["points", "goals", "toi"], ascending=False)
        rows = [[f'<a href="#g{p.game_id}">{escape(p["name"])}</a> ({escape(p.team)}–{escape(p.opp)})',
                 str(p.goals), str(p.assists), f"<b>{p.points}</b>", str(p.sog),
                 num(p.ixg) if pd.notna(p.ixg) else "–", toi(p.toi)] for _, p in sk.iterrows()]
        cards.append(_table("Yön suomalaiset", ["Pelaaja", "M", "S", "P", "L", "ixG", "Aika"], rows))
    if not gl.empty:
        if not xgg.empty:
            gl = gl.merge(xgg[["game_id", "player_id", "gsax"]], on=["game_id", "player_id"], how="left")
        rows = []
        for _, g in gl.iterrows():
            sv = g.saves / g.shots_against if g.shots_against else 0
            gsax = _signed(g.gsax) if "gsax" in g and pd.notna(g.gsax) else "–"
            rows.append([f'<a href="#g{g.game_id}">{escape(g["name"])}</a> ({escape(g.team)}–{escape(g.opp)})',
                         f"{g.saves}/{g.shots_against}", num(sv, 3), gsax,
                         DECISIONS.get(g.decision, "–") if isinstance(g.decision, str) else "–"])
        cards.append(_table("Yön suomalaismaalivahdit", ["Maalivahti", "Torjunnat", "Torj-%", "GSAx", "Tulos"], rows))
    if not cards:
        cards.append('<p class="empty">Yöllä ei pelannut suomalaisia.</p>')
    if inj is not None and not inj.empty:
        hurt = inj[inj.player_id.isin(finns)].sort_values("name")
        if not hurt.empty:
            cards.append(_table("Sivussa olevat suomalaiset", INJ_HEAD, _injury_rows(hurt), "inj wide"))
    parts.append(f'<div class="season">{"".join(cards)}</div>')

    season_cards = []
    fs = tables["finns"]
    if not fs.empty:
        rows = [[f'{escape(r["name"])} ({escape(r.team)})', str(r.gp), str(r.goals), str(r.assists),
                 f"<b>{r.points}</b>", num(r.ixg), toi(r.toi), str(r.streak) if r.streak >= 2 else ""]
                for _, r in fs.head(15).iterrows()]
        season_cards.append(_table("Suomalaisten pistepörssi",
                                   ["Pelaaja", "O", "M", "S", "P", "ixG", "Aika/O", "Putki"], rows))
    sg = goalies[(goalies.date <= day) & goalies.player_id.isin(finns)]
    if not sg.empty:
        if not xgg.empty:
            sg = sg.merge(xgg[["game_id", "player_id", "gsax"]], on=["game_id", "player_id"], how="left")
        else:
            sg = sg.assign(gsax=float("nan"))
        tot = sg.groupby("player_id").agg(
            name=("name", "last"), team=("team", "last"), gp=("game_id", "size"),
            wins=("decision", lambda s: (s == "W").sum()), saves=("saves", "sum"),
            shots=("shots_against", "sum"), gsax=("gsax", lambda s: s.fillna(0).sum())
        ).sort_values("gp", ascending=False)
        rows = [[f'{escape(r["name"])} ({escape(r.team)})', str(r.gp), str(r.wins),
                 num(r.saves / r.shots if r.shots else 0, 3), _signed(r.gsax)] for _, r in tot.iterrows()]
        season_cards.append(_table("Suomalaismaalivahdit kaudella", ["Maalivahti", "O", "V", "Torj-%", "GSAx"], rows))
    if season_cards:
        parts.append(f'<h3 class="subhead">Kausi tähän mennessä</h3><div class="season">{"".join(season_cards)}</div>')
    return "".join(parts)


def _injury_rows(df: pd.DataFrame, with_team: bool = True) -> list[list[str]]:
    rows = []
    for _, r in df.iterrows():
        who = escape(r["name"])
        if r.espn_url:
            who = f'<a href="{escape(r.espn_url)}">{who}</a>'
        if with_team:
            who += f" ({escape(r.team)})"
        upd = pd.Timestamp(r.updated) if r.updated else None
        rows.append([who, escape(status_fi(r.status)), escape(injury_fi(r.injury)),
                     escape(return_text(r.return_date, r.snapshot)),
                     f"{upd.day}.{upd.month}." if upd is not None else "–"])
    return rows


INJ_HEAD = ["Pelaaja", "Tila", "Vamma", "Arvioitu paluu", "Päivitetty"]


def _injuries_html(day: str, inj: pd.DataFrame) -> str:
    if inj is None or inj.empty:
        return '<p class="empty">Loukkaantumistietoja ei ole saatavilla tälle päivälle.</p>'
    fresh = inj[inj.updated >= day].sort_values(["updated", "team"], ascending=[False, True])
    parts = []
    if fresh.empty:
        parts.append('<p class="empty">Ei uusia loukkaantumisilmoituksia.</p>')
    else:
        parts.append(_table(f"Uudet ja päivittyneet ilmoitukset ({len(fresh)})", INJ_HEAD, _injury_rows(fresh), "inj"))
    full = inj.sort_values(["team", "name"])
    parts.append(f'<details class="game"><summary>Kaikki sivussa olevat ({len(full)})</summary>'
                 + _table("", INJ_HEAD, _injury_rows(full), "inj") + "</details>")
    return "".join(parts)


def _season_html(tables: dict[str, pd.DataFrame]) -> str:
    parts = []
    s = tables["streaks"]
    rows = "".join(f"<tr><td>{escape(r['name'])} ({escape(r.team)})</td><td>{r.streak}</td>"
                   f"<td>{r.goals}+{r.assists}</td></tr>" for _, r in s.iterrows())
    parts.append(f'<div class="game"><div class="block"><h3>Käynnissä olevat pisteputket</h3>'
                 f'<table><tr><th>Pelaaja</th><th>Peliä</th><th>Tehot</th></tr>'
                 f'{rows or "<tr><td>–</td></tr>"}</table></div></div>')
    for key, title in (("unlucky", "Maaleja tulossa? (maalit selvästi alle ixG:n)"),
                       ("finishers", "Kuumat viimeistelijät (maalit yli ixG:n)")):
        if key not in tables:
            continue
        rows = "".join(f"<tr><td>{escape(r['name'])} ({escape(r.team)})</td><td>{r.gp}</td><td>{r.goals}</td>"
                       f"<td>{num(r.ixg)}</td><td>{_signed(r['diff'])}</td></tr>"
                       for _, r in tables[key].iterrows())
        parts.append(f'<div class="game"><div class="block"><h3>{escape(title)}</h3>'
                     f'<table><tr><th>Pelaaja</th><th>O</th><th>M</th><th>ixG</th><th>Erotus</th></tr>'
                     f'{rows}</table></div></div>')
    return f'<div class="season">{"".join(parts)}</div>'


def _archive_html(current: date) -> str:
    files = sorted(REPORTS_DIR.glob("*.html"), reverse=True)
    links = []
    for f in files[:60]:
        d = date.fromisoformat(f.stem)
        mark = " (tämä)" if d == current else ""
        links.append(f'<li><a href="raportit/{f.name}">{day_fi(d)}</a>{mark}</li>')
    return f'<ul class="archive">{"".join(links)}</ul>'


def render(day: date, games, skaters, goalies, xg, items, tables, finns: set[int] = frozenset(),
           inj: pd.DataFrame | None = None) -> str:
    night = games[games.date == day.isoformat()].sort_values("game_id")
    cards = "".join(_game_html(gm, skaters, goalies, xg["xg_teams"], xg["xg_goalies"])
                    for _, gm in night.iterrows())
    updated = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    return f"""<!doctype html>
<html lang="fi"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>NHL-yöraportti {day.day}.{day.month}.{day.year}</title>
<meta name="description" content="NHL:n yön otteluiden syvädata ja nostot: xG, putket ja poikkeamat.">
<style>{CSS}</style></head>
<body><main>
<header><h1>NHL-yöraportti</h1>
<p class="sub">Ottelut {day_fi(day)} (Pohjois-Amerikan aikaa) · {len(night)} ottelua</p></header>
<h2>Yön nostot</h2>{_insights_html(items)}
<h2 id="suomalaiset">Suomalaisnurkkaus</h2>{_finn_html(day.isoformat(), skaters, goalies, xg, items, tables, finns, inj)}
<h2 id="loukkaantumiset">Loukkaantumiset</h2>{_injuries_html(day.isoformat(), inj)}
<h2>Ottelut</h2>{f'<div class="games">{cards}</div>' if cards else '<p class="empty">Ei pelattuja otteluita.</p>'}
<h2>Kausi tähän mennessä</h2>{_season_html(tables)}
<h2>Arkisto</h2>{{ARCHIVE}}
<footer>
xG-, GSAx- ja laukausdata: <a href="https://moneypuck.com">MoneyPuck.com</a>.
Tulokset ja pelaajatilastot: NHL.com. Loukkaantumiset: ESPN / RotoWire (paluuarviot ovat suuntaa-antavia). Päivitetty {updated}.<br>
ixG = pelaajan laukausten odotetut maalit. GSAx = maalivahdin päästämät maalit verrattuna odotettuun
(positiivinen = odotettua parempi). Vaarallinen paikka = laukaus, jonka xG on vähintään 0,20.
Lähdekoodi: <a href="https://github.com/juhaopesonen/NHL-stats">GitHub</a>.
</footer>
</main></body></html>"""


def write(day: date, html: str) -> None:
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    (DOCS_DIR / ".nojekyll").touch()
    report = REPORTS_DIR / f"{day.isoformat()}.html"
    # Arkistoraportin linkit osoittavat sisarsivuihin, etusivun linkit raportit/-kansioon
    report.write_text("", encoding="utf-8")
    archive = _archive_html(day)
    report.write_text(html.replace("{ARCHIVE}", archive.replace('href="raportit/', 'href="')),
                      encoding="utf-8")
    # Etusivu näyttää aina uusimman raportin
    latest = max(REPORTS_DIR.glob("*.html")).stem
    if latest == day.isoformat():
        (DOCS_DIR / "index.html").write_text(html.replace("{ARCHIVE}", archive), encoding="utf-8")
