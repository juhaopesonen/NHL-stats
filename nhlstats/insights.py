"""Analyysi: nostetaan yön peleistä kiinnostavat yksityiskohdat."""
from dataclasses import dataclass

import pandas as pd

from . import config as c
from . import injuries
from .fmt import num, toi


@dataclass
class Insight:
    kind: str       # lyhyt luokka, näkyy raportissa tunnisteena
    text: str
    score: float    # suurempi = tärkeämpi
    game_id: int | None = None
    player_id: int | None = None


def _trailing(values, predicate) -> int:
    n = 0
    for v in reversed(values):
        if not predicate(v):
            break
        n += 1
    return n


def player_insights(day: str, skaters: pd.DataFrame) -> list[Insight]:
    """Putket, isot illat, päättyneet paastot ja peliaikapoikkeamat."""
    out, grouped = [], []
    season = skaters[skaters.date <= day].sort_values(["date", "game_id"])
    for _, g in season.groupby("player_id", sort=False):
        last = g.iloc[-1]
        if last.date != day:
            continue
        who = f"{last['name']} ({last.team})"
        pts, goals = g.points.tolist(), g.goals.tolist()
        gid = int(last.game_id)
        start = len(out)

        streak = _trailing(pts, lambda v: v > 0)
        if streak >= c.POINT_STREAK_SOLO:
            run = g.iloc[-streak:]
            out.append(Insight("Pisteputki",
                f"{who} jatkoi pisteputkensa {streak} otteluun "
                f"(putken aikana {run.goals.sum()}+{run.assists.sum()}).",
                40 + 5 * streak, gid))
        elif streak >= c.POINT_STREAK_GROUP:
            grouped.append((streak, who))

        gstreak = _trailing(goals, lambda v: v > 0)
        if gstreak >= c.GOAL_STREAK_MIN:
            out.append(Insight("Maaliputki",
                f"{who} on tehnyt maalin {gstreak} ottelussa peräkkäin "
                f"(yhteensä {g.goals.iloc[-gstreak:].sum()} maalia).",
                50 + 8 * gstreak, gid))

        if last.points == 0:
            ended = _trailing(pts[:-1], lambda v: v > 0)
            if ended >= c.STREAK_ENDED_MIN:
                out.append(Insight("Putki katkesi",
                    f"{who}: {ended} ottelun pisteputki katkesi yön peliin.",
                    35 + 3 * ended, gid))

        if last.goals > 0:
            drought = _trailing(goals[:-1], lambda v: v == 0)
            if drought >= c.GOAL_DROUGHT_MIN:
                out.append(Insight("Paasto päättyi",
                    f"{who} katkaisi {drought} ottelun maalittoman jakson.",
                    40 + drought, gid))

        if last.goals >= 3:
            out.append(Insight("Hattutemppu",
                f"{who} teki hattutempun, tehot {last.goals}+{last.assists}.",
                90 + 5 * (last.points - 3), gid))
        elif last.points >= 3:
            out.append(Insight("Iso ilta",
                f"{who} keräsi {last.points} pistettä ({last.goals}+{last.assists}).",
                55 + 10 * (last.points - 3), gid))

        prev = g.iloc[:-1]
        if len(prev) >= c.TOI_MIN_GAMES and prev.toi.mean() >= 600:
            avg = prev.toi.mean()
            if last.toi >= avg * c.TOI_UP_RATIO:
                out.append(Insight("Peliaika",
                    f"{who} pelasi {toi(last.toi)}, kun aiempi keskiarvo on {toi(avg)}.",
                    30 + 20 * (last.toi / avg - c.TOI_UP_RATIO), gid))
            elif last.toi <= avg * c.TOI_DOWN_RATIO:
                out.append(Insight("Peliaika",
                    f"{who} pelasi vain {toi(last.toi)}, kun aiempi keskiarvo on {toi(avg)}.",
                    28, gid))

        for item in out[start:]:
            item.player_id = int(last.player_id)

    if grouped:
        grouped.sort(key=lambda x: (-x[0], x[1]))
        names = ", ".join(f"{who} {n}" for n, who in grouped)
        out.append(Insight("Pisteputket",
            f"Pisteputki jatkui {len(grouped)} pelaajalla (peliä putkessa): {names}.",
            45 + 5 * grouped[0][0]))
    return out


def xg_insights(day: str, games: pd.DataFrame, skaters: pd.DataFrame,
                goalies: pd.DataFrame, xgp: pd.DataFrame, xgt: pd.DataFrame,
                xgg: pd.DataFrame) -> list[Insight]:
    """Nostot, jotka perustuvat MoneyPuckin odotettuihin maaleihin (xG)."""
    out = []
    night = games[games.date == day]
    if night.empty or xgp.empty:
        return out
    gids = set(night.game_id)

    sk = skaters[skaters.game_id.isin(gids)].merge(xgp, on=["game_id", "player_id"], how="inner")
    for _, p in sk.iterrows():
        who = f"{p['name']} ({p.team})"
        if p.goals == 0 and p.ixg >= c.UNLUCKY_IXG:
            out.append(Insight("Huono tuuri",
                f"{who} jäi ilman maalia, vaikka laukauksista kertyi {num(p.ixg)} "
                f"odotettua maalia (ixG, {p.attempts} laukausyritystä, "
                f"{p.hd_attempts} vaarallista).",
                50 + 30 * (p.ixg - c.UNLUCKY_IXG), int(p.game_id), int(p.player_id)))
        elif p.goals >= 2 and p.goals - p.ixg >= c.FINISHER_MARGIN:
            out.append(Insight("Viimeistelijä",
                f"{who} teki {p.goals} maalia vain {num(p.ixg)} ixG:n laukauksista.",
                45 + 10 * (p.goals - p.ixg), int(p.game_id), int(p.player_id)))

    for _, gm in night.iterrows():
        t = xgt[xgt.game_id == gm.game_id].set_index("team")
        if len(t) != 2:
            continue
        home_won = gm.home_score > gm.away_score
        winner, loser = (gm.home, gm.away) if home_won else (gm.away, gm.home)
        share = t.at[loser, "xg"] / (t.at[loser, "xg"] + t.at[winner, "xg"])
        if share >= c.TEAM_XG_SHARE:
            score = f"{max(gm.home_score, gm.away_score)}–{min(gm.home_score, gm.away_score)}"
            out.append(Insight("xG vs. tulos",
                f"{loser} hävisi {winner}:lle {score}, vaikka voitti odotetut maalit "
                f"{num(t.at[loser, 'xg'])}–{num(t.at[winner, 'xg'])} "
                f"(xG-osuus {round(share * 100)} %).",
                55 + 50 * (share - c.TEAM_XG_SHARE), int(gm.game_id)))

    gl = goalies[goalies.game_id.isin(gids)].merge(xgg, on=["game_id", "player_id"], how="inner")
    for _, g in gl.iterrows():
        who = f"{g['name']} ({g.team})"
        line = f"{g.saves}/{g.shots_against}"
        if g.gsax >= c.GOALIE_GSAX:
            out.append(Insight("Maalivahti",
                f"{who} torjui {line} ja päästi {num(g.gsax)} maalia odotettua vähemmän (GSAx).",
                50 + 10 * g.gsax, int(g.game_id), int(g.player_id)))
        elif g.gsax <= -c.GOALIE_GSAX:
            out.append(Insight("Maalivahti",
                f"{who}: vaikea ilta, {line} ja {num(-g.gsax)} maalia odotettua enemmän (GSAx {num(g.gsax)}).",
                40 + 5 * -g.gsax, int(g.game_id), int(g.player_id)))
    return out


def return_text(return_date: str, snapshot: str) -> str:
    """Esim. '13.10. (n. 2 pv)'."""
    if not return_date:
        return "ei arviota"
    ret, ref = pd.Timestamp(return_date), pd.Timestamp(snapshot)
    days = (ret - ref).days
    span = "pian" if days <= 0 else f"n. {days} pv" if days < 21 else f"n. {round(days / 7)} vk"
    shown = f"{ret.day}.{ret.month}." + (str(ret.year) if days > 180 else "")
    return f"{shown} ({span})"


def injury_insights(day: str, skaters: pd.DataFrame, goalies: pd.DataFrame,
                    inj: pd.DataFrame) -> list[Insight]:
    """Yöllä pelanneet, joista on pelin jälkeen tullut loukkaantumisilmoitus."""
    if inj.empty:
        return []
    fresh = inj[(inj.updated >= day) & inj.player_id.notna()]
    played = pd.concat([skaters[skaters.date == day], goalies[goalies.date == day]])
    out = []
    for _, p in played[played.player_id.isin(set(fresh.player_id.astype(int)))].iterrows():
        r = fresh[fresh.player_id == p.player_id].iloc[0]
        out.append(Insight("Loukkaantuminen",
            f"{p['name']} ({p.team}) pelasi yöllä {toi(p.toi)} – nyt {injuries.status_fi(r.status)}, "
            f"vamma: {injuries.injury_fi(r.injury)}, arvioitu paluu {return_text(r.return_date, r.snapshot)}.",
            # Mitä lyhyemmäksi peliaika jäi, sitä todennäköisemmin loukkaantuminen sattui yöllä
            72 - p.toi / 60, int(p.game_id), int(p.player_id)))
    return out


def build(day, games, skaters, goalies, xg, inj: pd.DataFrame | None = None) -> list[Insight]:
    hurt = injury_insights(day, skaters, goalies, inj if inj is not None else pd.DataFrame())
    hurt_ids = {i.player_id for i in hurt}
    items = [i for i in player_insights(day, skaters)
             if not (i.kind == "Peliaika" and i.player_id in hurt_ids)]  # loukkaantuminen selittää
    items += hurt + xg_insights(
        day, games, skaters, goalies, xg["xg_players"], xg["xg_teams"], xg["xg_goalies"])
    return sorted(items, key=lambda i: i.score, reverse=True)


def finn_season(season: pd.DataFrame, xgp: pd.DataFrame, finns: set[int],
                onice: pd.DataFrame | None = None) -> pd.DataFrame:
    """Suomalaisten kenttäpelaajien kausitilastot pistejärjestyksessä.

    onice: MoneyPuckin 5v5-kausikooste (xG puolesta/vastaan pelaajan ollessa jäällä).
    """
    fin = season[season.player_id.isin(finns)]
    if "pp_toi" not in fin.columns:
        fin = fin.assign(pp_toi=float("nan"))
    if not xgp.empty:
        fin = fin.merge(xgp[["game_id", "player_id", "ixg"]], on=["game_id", "player_id"], how="left")
    else:
        fin = fin.assign(ixg=float("nan"))
    tot = fin.groupby("player_id").agg(
        name=("name", "last"), team=("team", "last"), gp=("game_id", "size"),
        goals=("goals", "sum"), assists=("assists", "sum"), points=("points", "sum"),
        ixg=("ixg", lambda s: s.fillna(0).sum()), toi=("toi", "mean"), pp_toi=("pp_toi", "mean"),
        streak=("points", lambda s: _trailing(s.tolist(), lambda v: v > 0))).reset_index()
    cols = ["onice_xgf", "onice_xga", "onice_xg_pct", "office_xg_pct"]
    if onice is not None and not onice.empty:
        tot = tot.merge(onice[["player_id"] + cols], on="player_id", how="left")
    else:
        tot = tot.assign(**{c: float("nan") for c in cols})
    return tot.sort_values(["points", "goals", "toi"], ascending=False)


def top_goalies(day: str, goalies: pd.DataFrame, xgg: pd.DataFrame, n: int = 10) -> pd.DataFrame:
    """Kauden parhaat maalivahdit GSAx:n mukaan (vähintään GOALIE_TOP_MIN_GP ottelua)."""
    gl = goalies[goalies.date <= day]
    if gl.empty:
        return pd.DataFrame()
    if not xgg.empty:
        gl = gl.merge(xgg[["game_id", "player_id", "gsax", "xga"]], on=["game_id", "player_id"], how="left")
    else:
        gl = gl.assign(gsax=float("nan"), xga=float("nan"))
    tot = gl.groupby("player_id").agg(
        name=("name", "last"), team=("team", "last"), gp=("game_id", "size"),
        wins=("decision", lambda d: (d == "W").sum()), saves=("saves", "sum"),
        shots=("shots_against", "sum"), ga=("goals_against", "sum"), toi=("toi", "sum"),
        gsax=("gsax", lambda v: v.fillna(0).sum()), xga=("xga", lambda v: v.fillna(0).sum())).reset_index()
    tot = tot[tot.gp >= c.GOALIE_TOP_MIN_GP]
    tot["sv_pct"] = tot.saves / tot.shots.where(tot.shots > 0)
    tot["gaa"] = tot.ga * 3600 / tot.toi.where(tot.toi > 0)
    return tot.sort_values(["gsax", "sv_pct"], ascending=False).head(n)


def season_tables(day: str, skaters: pd.DataFrame, xgp: pd.DataFrame,
                  finns: set[int] = frozenset(), onice: pd.DataFrame | None = None,
                  goalies: pd.DataFrame | None = None, xgg: pd.DataFrame | None = None) -> dict[str, pd.DataFrame]:
    """Kauden taulukot: pisteputket, xG-yli/alisuoriutujat ja suomalaiset."""
    season = skaters[skaters.date <= day].sort_values(["date", "game_id"])
    rows = []
    for pid, g in season.groupby("player_id", sort=False):
        streak = _trailing(g.points.tolist(), lambda v: v > 0)
        if streak >= c.POINT_STREAK_MIN:
            run = g.iloc[-streak:]
            rows.append({"name": g["name"].iloc[-1], "team": g.team.iloc[-1], "streak": streak,
                         "goals": run.goals.sum(), "assists": run.assists.sum()})
    streaks = pd.DataFrame(rows, columns=["name", "team", "streak", "goals", "assists"])
    streaks = streaks.sort_values(["streak", "goals"], ascending=False).head(10)

    tables = {"streaks": streaks, "finns": finn_season(season, xgp, finns, onice)}
    if goalies is not None:
        tables["goalies"] = top_goalies(day, goalies, xgg if xgg is not None else pd.DataFrame())
    if not xgp.empty:
        # Mukaan kaikki pelatut ottelut, joille xG-data on olemassa (ei laukauksia = ixG 0)
        merged = season[season.game_id.isin(xgp.game_id.unique())].merge(
            xgp[["game_id", "player_id", "ixg"]], on=["game_id", "player_id"], how="left")
        merged["ixg"] = merged.ixg.fillna(0)
        tot = merged.groupby("player_id").agg(
            name=("name", "last"), team=("team", "last"), gp=("game_id", "size"),
            goals=("goals", "sum"), ixg=("ixg", "sum")).reset_index()
        tot["diff"] = tot.goals - tot.ixg
        tables["unlucky"] = tot[tot.ixg >= 1.5].sort_values("diff").head(8)
        tables["finishers"] = tot[tot.goals >= 2].sort_values("diff", ascending=False).head(8)
    return tables
