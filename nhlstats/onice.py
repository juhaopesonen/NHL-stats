"""Ottelukohtaiset 5v5-luvut pelaajan ollessa jäällä.

NHL:n vaihtodatasta (shift charts) selviää, ketkä olivat jäällä kunkin
MoneyPuckin laukauksen hetkellä. Laukausdatassa ei ole blokattuja laukauksia,
joten yritykset ovat Fenwick-lukuja. Tyhjään maaliin ammutut eivät ole mukana.
"""
import pandas as pd

from . import http

SHIFTS = "https://api.nhle.com/stats/rest/en/shiftcharts?cayenneExp=gameId={gid}"
SHIFT_TYPE = 517  # 505 = maalitapahtuma, ei vaihto

COLUMNS = ["game_id", "player_id", "team", "xgf_5v5", "xga_5v5", "gf_5v5", "ga_5v5", "ff_5v5", "fa_5v5"]


def _secs(mmss: str | None) -> int:
    if not mmss:
        return 0
    m, s = mmss.split(":")
    return int(m) * 60 + int(s)


def shifts(game_id: int) -> pd.DataFrame:
    """Pelaajien vaihdot ottelun sekunteina (alku, loppu]."""
    data = http.get(SHIFTS.format(gid=game_id)).json().get("data", [])
    rows = []
    for s in data:
        if s.get("typeCode") != SHIFT_TYPE or not s.get("startTime") or not s.get("endTime"):
            continue
        base = (s["period"] - 1) * 1200
        rows.append({"player_id": s["playerId"], "team": s["teamAbbrev"],
                     "start": base + _secs(s["startTime"]), "end": base + _secs(s["endTime"])})
    return pd.DataFrame(rows, columns=["player_id", "team", "start", "end"])


def game_onice(game_id: int, shots: pd.DataFrame, home: str, away: str) -> pd.DataFrame:
    """Laskee yhden ottelun 5v5-luvut jokaiselle pelaajalle."""
    sh = shifts(game_id)
    if sh.empty:
        return pd.DataFrame(columns=COLUMNS)
    s5 = shots[(shots.game_id == game_id) & (shots.homeSkatersOnIce == 5) & (shots.awaySkatersOnIce == 5)
               & (shots.shotOnEmptyNet == 0)]
    acc: dict[int, dict] = {}
    for pid, team in sh.drop_duplicates("player_id")[["player_id", "team"]].itertuples(index=False):
        acc[pid] = {"game_id": game_id, "player_id": pid, "team": team,
                    "xgf_5v5": 0.0, "xga_5v5": 0.0, "gf_5v5": 0, "ga_5v5": 0, "ff_5v5": 0, "fa_5v5": 0}
    for t, is_home, xg, goal in s5[["time", "isHomeTeam", "xGoal", "goal"]].itertuples(index=False):
        shooting = home if is_home == 1 else away
        on = sh[(sh.start < t) & (sh.end >= t)]
        for pid, team in on[["player_id", "team"]].drop_duplicates("player_id").itertuples(index=False):
            a = acc[pid]
            side = "f" if team == shooting else "a"
            a[f"xg{side}_5v5"] += xg
            a[f"g{side}_5v5"] += int(goal)
            a[f"f{side}_5v5"] += 1
    # Maalivahdit jätetään pois (heidän lukunsa ovat vain joukkueen lukuja)
    return pd.DataFrame(acc.values(), columns=COLUMNS)
