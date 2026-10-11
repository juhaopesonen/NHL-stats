"""HTML-raportin generointi GitHub Pagesia varten (docs/)."""
from datetime import date, datetime, timezone
from html import escape

import pandas as pd

from .config import DOCS_DIR, INSIGHT_ORDER, INSIGHTS_PER_KIND, INSIGHTS_TOP, REPORTS_DIR
from .fmt import day_fi, num, toi
from .injuries import injury_fi, status_fi
from .insights import Insight, return_text

CSS = """
:root{--bg:#f6f7f9;--card:#fff;--text:#16181d;--muted:#5f6673;--line:#e3e6eb;
--accent:#0b5fff;--accent-soft:#e8efff;--good:#0f8a4b;--bad:#c4372c;--bar-a:#6b7385;--bar-h:#0b5fff;--bar-a-text:#fff;--bar-h-text:#fff}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){--bg:#0f1115;--card:#181b21;
--text:#e8eaee;--muted:#9aa2b1;--line:#2a2f38;--accent:#6c9cff;--accent-soft:#1d2840;--good:#3ccf84;
--bad:#ff7a6e;--bar-a:#5b6475;--bar-h:#6c9cff;--bar-a-text:#fff;--bar-h-text:#0f1115}}
:root[data-theme="dark"]{--bg:#0f1115;--card:#181b21;--text:#e8eaee;--muted:#9aa2b1;--line:#2a2f38;
--accent:#6c9cff;--accent-soft:#1d2840;--good:#3ccf84;--bad:#ff7a6e;--bar-a:#5b6475;--bar-h:#6c9cff;--bar-a-text:#fff;--bar-h-text:#0f1115}
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
.bar{display:flex;height:22px;border-radius:6px;overflow:hidden;margin:6px 0 10px;background:var(--line);
font-size:12px;font-weight:700;line-height:22px;font-variant-numeric:tabular-nums}
.bar div{flex-basis:0;min-width:3.4em;padding:0 8px;white-space:nowrap}
.bar .a{background:var(--bar-a);color:var(--bar-a-text)}
.bar .h{background:var(--bar-h);color:var(--bar-h-text);text-align:right}
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
.inj td:nth-child(4),.inj td:nth-child(5){white-space:nowrap}
.inj .tag{font-size:11px;padding:1px 7px}
.wide{grid-column:1/-1}
.tiles{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:10px;margin:20px 0 28px}
.tile{display:flex;flex-direction:column;gap:2px;background:var(--card);border:1px solid var(--line);border-radius:12px;
padding:12px 14px;text-decoration:none;color:var(--text);transition:border-color .15s,background .15s}
.tile:hover{border-color:var(--accent)}
.tile.active{border-color:var(--accent);box-shadow:inset 0 0 0 1px var(--accent);background:var(--accent-soft)}
.t-title{font-size:13px;font-weight:600;color:var(--muted)}
.tile.active .t-title{color:var(--accent)}
.t-big{font-size:26px;font-weight:700;line-height:1.15;font-variant-numeric:tabular-nums}
.t-sub{font-size:12px;color:var(--muted);line-height:1.35}
@media (max-width:520px){.tiles{grid-template-columns:repeat(2,1fr)}.t-big{font-size:22px}}
.panel{scroll-margin-top:12px}
.panel>h2{margin-top:0}
.js .panel+.panel{margin-top:0}
.panel+.panel{margin-top:36px}
.totop{position:fixed;right:16px;bottom:16px;background:var(--accent);color:var(--bg);text-decoration:none;
font-size:14px;font-weight:600;padding:8px 14px;border-radius:999px;box-shadow:0 2px 8px rgba(0,0,0,.2);display:none}
.totop.show{display:block}
details.more{margin-top:10px}
details.more>summary{cursor:pointer;color:var(--accent);font-size:14px;margin-bottom:8px}
.subhead{font-size:15px;margin:20px 0 10px}
#suomalaiset + .insights{margin-bottom:14px}
.game td a{color:inherit;text-decoration:none;border-bottom:1px dotted var(--muted)}
@media (max-width:520px){.insights li{flex-wrap:wrap}.insights a{margin-left:0}}
"""


def _signed(x: float) -> str:
    cls = "pos" if x > 0 else "neg" if x < 0 else ""
    sign = "+" if x > 0 else ""
    return f'<span class="{cls}">{sign}{num(x)}</span>'


def _insight_list(items: list[Insight]) -> str:
    rows = []
    for i in items:
        link = f'<a href="#g{i.game_id}">ottelu</a>' if i.game_id else ""
        rows.append(f'<li><span class="tag">{escape(i.kind)}</span><span>{escape(i.text)}</span>{link}</li>')
    return f'<ul class="insights">{"".join(rows)}</ul>'


def _by_kind(items: list[Insight]) -> list[Insight]:
    """Aiheittain kiinteään järjestykseen, aiheen sisällä tärkein ensin."""
    rank = {k: n for n, k in enumerate(INSIGHT_ORDER)}
    return sorted(items, key=lambda i: (rank.get(i.kind, len(rank)), -i.score))


def _insights_html(items: list[Insight], limit: int | None = None, per_kind: int = 2) -> str:
    if not items:
        return '<p class="empty">Ei erityisiä nostoja tältä yöltä.</p>'
    if limit is None:
        return _insight_list(_by_kind(items))
    # Tärkeimmät nostot (enintään per_kind samasta aiheesta), näytetään aihejärjestyksessä
    top, seen = [], {}
    for i in sorted(items, key=lambda i: -i.score):
        if len(top) < limit and seen.get(i.kind, 0) < per_kind:
            seen[i.kind] = seen.get(i.kind, 0) + 1
            top.append(i)
    items = _by_kind(items)
    html = _insight_list(_by_kind(top))
    if len(top) < len(items):
        html += (f'<details class="more"><summary>Kaikki nostot ({len(items)})</summary>'
                 f"{_insight_list(items)}</details>")
    return html


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
        title = f"xG {gm.away} {num(a.xg)} – {num(h.xg)} {gm.home}"
        bar = (f'<div class="bar" title="{escape(title)}">'
               f'<div class="a" style="flex-grow:{a.xg:.3f}">{num(a.xg)}</div>'
               f'<div class="h" style="flex-grow:{h.xg:.3f}">{num(h.xg)}</div></div>')
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


def _pp(seconds) -> str:
    """Ylivoima-aika; viiva, jos tietoa ei (vielä) ole."""
    return toi(seconds) if seconds is not None and pd.notna(seconds) else "–"


def _onice(r) -> list[str]:
    """5v5 xG puolesta–vastaan, xG-% (vihreä yli 50) ja ero joukkueeseen ilman pelaajaa."""
    if pd.isna(r.onice_xg_pct):
        return ["–", "–", "–"]
    pct = r.onice_xg_pct * 100
    cls = "pos" if pct > 50 else "neg" if pct < 50 else ""
    rel = (r.onice_xg_pct - r.office_xg_pct) * 100
    rel_cls = "pos" if rel > 0 else "neg" if rel < 0 else ""
    return [f"{num(r.onice_xgf, 1)}–{num(r.onice_xga, 1)}",
            f'<span class="{cls}">{pct:.0f} %</span>',
            f'<span class="{rel_cls}">{"+" if rel > 0 else ""}{rel:.0f}</span>'.replace("-", "−")]


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
                 num(p.ixg) if pd.notna(p.ixg) else "–", toi(p.toi), _pp(p.get("pp_toi"))] for _, p in sk.iterrows()]
        cards.append(_table("Yön suomalaiset", ["Pelaaja", "M", "S", "P", "L", "ixG", "Aika", "YV min"], rows))
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
    parts.append(f'<div class="season">{"".join(cards)}</div>')

    season_cards = []
    fs = tables["finns"]
    if not fs.empty:
        rows = [[f'{escape(r["name"])} ({escape(r.team)})', str(r.gp), str(r.goals), str(r.assists),
                 f"<b>{r.points}</b>", num(r.ixg), toi(r.toi), _pp(r.pp_toi), *_onice(r), str(r.streak) if r.streak >= 2 else ""]
                for _, r in fs.head(15).iterrows()]
        season_cards.append(_table("Suomalaisten pistepörssi",
                                   ["Pelaaja", "O", "M", "S", "P", "ixG", "Aika/O", "YV min/O", "5v5 xGF–xGA", "5v5 xG%", "vs. tiimi", "Putki"], rows, "wide"))
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


INJ_HEAD = ["Pelaaja", "Tila", "Vamma", "Arvioitu paluu", "Päivitetty"]


def _injuries_html(day: str, inj: pd.DataFrame, finns: set[int], stars: pd.DataFrame) -> str:
    """Sivussa olevat suomalaiset ja joukkueiden tähtipelaajat."""
    if inj is None or inj.empty:
        return '<p class="empty">Loukkaantumistietoja ei ole saatavilla tälle päivälle.</p>'
    basis = dict(zip(stars.player_id, stars.basis)) if not stars.empty else {}
    shown = inj[inj.player_id.isin(finns) | inj.player_id.isin(basis.keys())].copy()
    if shown.empty:
        return '<p class="empty">Yksikään suomalainen tai tähtipelaaja ei ole sivussa.</p>'
    shown["new"] = shown.updated >= day
    shown = shown.sort_values(["new", "team", "name"], ascending=[False, True, True])
    rows = []
    for _, r in shown.iterrows():
        who = escape(r["name"])
        if r.espn_url:
            who = f'<a href="{escape(r.espn_url)}">{who}</a>'
        who += f" ({escape(r.team)})"
        upd = pd.Timestamp(r.updated) if r.updated else None
        upd_txt = f"{upd.day}.{upd.month}." if upd is not None else "–"
        if r.new:
            upd_txt = f'<span class="tag">uusi</span> {upd_txt}'
        rows.append([who, escape(status_fi(r.status)), escape(injury_fi(r.injury)),
                     escape(return_text(r.return_date, r.snapshot)), upd_txt])
    return _table(f"Sivussa olevat suomalaiset ja tähtipelaajat ({len(shown)} / {len(inj)})",
                  INJ_HEAD, rows, "inj wide")


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


def _tile(panel: str, title: str, big: str, sub: str) -> str:
    return (f'<a class="tile" href="#{panel}" data-panel="{panel}"><span class="t-title">{escape(title)}</span>'
            f'<span class="t-big">{escape(big)}</span><span class="t-sub">{escape(sub)}</span></a>')


# Ruudukko: yksi osio kerrallaan näkyvissä. Ilman JavaScriptiä kaikki osiot näkyvät allekkain.
JS = """
(function(){
  var root=document.documentElement; root.classList.add('js');
  var panels=[].slice.call(document.querySelectorAll('.panel'));
  var tiles=[].slice.call(document.querySelectorAll('.tile'));
  var current=null;
  function show(id){
    current=id;
    panels.forEach(function(p){p.hidden=p.id!==id;});
    tiles.forEach(function(t){t.classList.toggle('active',t.dataset.panel===id);});
  }
  function route(){
    var h=decodeURIComponent(location.hash.slice(1));
    var el=h?document.getElementById(h):null;
    var panel=el?el.closest('.panel'):null;
    if(panel){show(panel.id); if(el!==panel) el.scrollIntoView({block:'start'});}
    else{ if(!current) show('nostot'); if(el) el.scrollIntoView({block:'start'}); }
  }
  tiles.forEach(function(t){t.addEventListener('click',function(e){
    e.preventDefault(); show(t.dataset.panel); history.replaceState(null,'','#'+t.dataset.panel);
  });});
  window.addEventListener('hashchange',route); route();
  var top=document.querySelector('.totop');
  function onScroll(){top.classList.toggle('show',window.scrollY>400);}
  window.addEventListener('scroll',onScroll,{passive:true}); onScroll();
})();
"""


def _archive_html(current: date) -> str:
    files = sorted(REPORTS_DIR.glob("*.html"), reverse=True)
    links = []
    for f in files[:60]:
        d = date.fromisoformat(f.stem)
        mark = " (tämä)" if d == current else ""
        links.append(f'<li><a href="raportit/{f.name}">{day_fi(d)}</a>{mark}</li>')
    return f'<ul class="archive">{"".join(links)}</ul>'


def render(day: date, games, skaters, goalies, xg, items, tables, finns: set[int] = frozenset(),
           inj: pd.DataFrame | None = None, stars: pd.DataFrame | None = None) -> str:
    stars = stars if stars is not None else pd.DataFrame()
    night = games[games.date == day.isoformat()].sort_values("game_id")

    fin_night = skaters[(skaters.date == day.isoformat()) & skaters.player_id.isin(finns)]
    fin_goalies = goalies[(goalies.date == day.isoformat()) & goalies.player_id.isin(finns)]
    n_fin = len(fin_night) + len(fin_goalies)
    if inj is not None and not inj.empty:
        star_ids = set(stars.player_id) if not stars.empty else set()
        shown = inj[inj.player_id.isin(finns) | inj.player_id.isin(star_ids)]
        new = int((shown.updated >= day.isoformat()).sum())
        inj_big, inj_sub = str(len(shown)), "suomalaista tai tähteä sivussa" + (f" · {new} uutta" if new else "")
    else:
        inj_big, inj_sub = "–", "ei tietoja"
    streaks = tables["streaks"]
    if not streaks.empty:
        lead = streaks.iloc[0]
        season_big, season_sub = str(lead.streak), f"pisin pisteputki: {lead['name']}"
    else:
        season_big, season_sub = "–", "kauden taulukot"
    finn_big = str(n_fin)
    finn_sub = (f"suomalaista pelasi · {fin_night.goals.sum()}+{fin_night.assists.sum()}"
                if n_fin else "suomalaista pelasi")
    top_kind = _by_kind(items)[0].kind.lower() if items else ""
    tiles = "".join(_tile(*t) for t in (
        ("nostot", "Yön nostot", str(len(items)), f"nostoa · kärjessä {top_kind}" if items else "nostoa"),
        ("ottelut", "Ottelut", str(len(night)), "ottelua · xG ja maalivahdit"),
        ("suomalaiset", "Suomalaisnurkkaus", finn_big, finn_sub),
        ("loukkaantumiset", "Loukkaantumiset", inj_big, inj_sub),
        ("kausi", "Kausi", season_big, season_sub),
        ("arkisto", "Arkisto", "{ARCHIVE_COUNT}", "aiempaa raporttia"),
    ))
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
<header id="top"><h1>NHL-yöraportti</h1>
<p class="sub">Ottelut {day_fi(day)} (Pohjois-Amerikan aikaa) · {len(night)} ottelua</p></header>
<nav class="tiles" id="valikko">{tiles}</nav>
<section class="panel" id="nostot"><h2>Yön nostot</h2>{_insights_html(items, INSIGHTS_TOP, INSIGHTS_PER_KIND)}</section>
<section class="panel" id="ottelut"><h2>Ottelut</h2>{f'<div class="games">{cards}</div>' if cards else '<p class="empty">Ei pelattuja otteluita.</p>'}</section>
<section class="panel" id="suomalaiset"><h2>Suomalaisnurkkaus</h2>{_finn_html(day.isoformat(), skaters, goalies, xg, items, tables, finns, inj)}</section>
<section class="panel" id="loukkaantumiset"><h2>Loukkaantumiset</h2>{_injuries_html(day.isoformat(), inj, finns, stars)}</section>
<section class="panel" id="kausi"><h2>Kausi tähän mennessä</h2>{_season_html(tables)}</section>
<section class="panel" id="arkisto"><h2>Arkisto</h2>{{ARCHIVE}}</section>
<a class="totop" href="#valikko">↑ Valikko</a>
<footer>
xG-, GSAx- ja laukausdata: <a href="https://moneypuck.com">MoneyPuck.com</a>.
Tulokset ja pelaajatilastot: NHL.com. Loukkaantumiset: ESPN / RotoWire (paluuarviot ovat suuntaa-antavia). Päivitetty {updated}.<br>
ixG = pelaajan laukausten odotetut maalit. GSAx = maalivahdin päästämät maalit verrattuna odotettuun
(positiivinen = odotettua parempi). Vaarallinen paikka = laukaus, jonka xG on vähintään 0,20.
5v5 xG% = joukkueen osuus odotetuista maaleista pelaajan ollessa jäällä 5 vs. 5 (kausi tähän asti);
vs. tiimi = ero prosenttiyksikköinä joukkueen xG%:iin pelaajan ollessa vaihdossa.
Lähdekoodi: <a href="https://github.com/juhaopesonen/NHL-stats">GitHub</a>.
</footer>
</main><script>{JS}</script></body></html>"""


def write(day: date, html: str) -> None:
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    (DOCS_DIR / ".nojekyll").touch()
    report = REPORTS_DIR / f"{day.isoformat()}.html"
    # Arkistoraportin linkit osoittavat sisarsivuihin, etusivun linkit raportit/-kansioon
    report.write_text("", encoding="utf-8")
    archive = _archive_html(day)
    earlier = sum(1 for f in REPORTS_DIR.glob("*.html") if f.stem < day.isoformat())
    html = html.replace("{ARCHIVE_COUNT}", str(earlier))
    report.write_text(html.replace("{ARCHIVE}", archive.replace('href="raportit/', 'href="')),
                      encoding="utf-8")
    # Etusivu näyttää aina uusimman raportin
    latest = max(REPORTS_DIR.glob("*.html")).stem
    if latest == day.isoformat():
        (DOCS_DIR / "index.html").write_text(html.replace("{ARCHIVE}", archive), encoding="utf-8")
