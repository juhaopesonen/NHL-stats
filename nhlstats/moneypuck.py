"""MoneyPuck.com:n laukausdata ja siitä lasketut xG-luvut.

MoneyPuckin data on vapaasti käytettävissä ei-kaupalliseen käyttöön,
kunhan lähde (MoneyPuck.com) mainitaan selvästi.
"""
import io
import zipfile

import pandas as pd

from . import http
from .config import HIGH_DANGER_XG

SHOTS_URL = "https://peter-tanner.com/moneypuck/downloads/shots_{year}.zip"

COLUMNS = [
    "game_id", "season", "isPlayoffGame", "period", "isHomeTeam", "shooterPlayerId",
    "goalieIdForShot", "xGoal", "goal", "shotWasOnGoal", "shotOnEmptyNet",
    "homeSkatersOnIce", "awaySkatersOnIce", "time",
]


def download_shots(start_year: int) -> pd.DataFrame:
    """Lataa kauden laukausdatan (torjutut, ohi menneet ja maalit; ei blokattuja)."""
    resp = http.get(SHOTS_URL.format(year=start_year))
    with zipfile.ZipFile(io.BytesIO(resp.content)) as z:
        csv_name = next(n for n in z.namelist() if n.endswith(".csv"))
        shots = pd.read_csv(z.open(csv_name), usecols=COLUMNS)
    # Runkosarjan voittolaukauskilpailu ei kuulu xG-lukuihin
    shots = shots[~((shots.isPlayoffGame == 0) & (shots.period >= 5))].copy()
    # MoneyPuckin game_id (esim. 20081) -> NHL:n tunniste (2026020081)
    shots["game_id"] = shots.season * 1_000_000 + shots.game_id
    return shots


SUMMARY_URL = "https://moneypuck.com/moneypuck/playerData/seasonSummary/{year}/regular/skaters.csv"


def download_onice_5v5(start_year: int) -> pd.DataFrame:
    """Kauden kumulatiiviset 5v5-luvut pelaajan ollessa jäällä (xG puolesta/vastaan)."""
    resp = http.get(SUMMARY_URL.format(year=start_year))
    df = pd.read_csv(io.StringIO(resp.text))
    df = df[df.situation == "5on5"]
    return pd.DataFrame({
        "player_id": df.playerId,
        "gp_5v5": df.games_played,
        "toi_5v5": df.icetime,
        "onice_xgf": df.OnIce_F_xGoals,
        "onice_xga": df.OnIce_A_xGoals,
        "onice_xg_pct": df.onIce_xGoalsPercentage,
        "office_xg_pct": df.offIce_xGoalsPercentage,
    })


def aggregate(shots: pd.DataFrame, games: pd.DataFrame) -> dict[str, pd.DataFrame]:
    """Laskee ottelukohtaiset xG-luvut pelaajille, joukkueille ja maalivahdeille."""
    shots = shots.assign(hd=(shots.xGoal >= HIGH_DANGER_XG).astype(int))

    players = (
        shots[shots.shooterPlayerId > 0]
        .groupby(["game_id", "shooterPlayerId"])
        .agg(ixg=("xGoal", "sum"), xg_goals=("goal", "sum"),
             attempts=("xGoal", "size"), hd_attempts=("hd", "sum"))
        .reset_index()
        .rename(columns={"shooterPlayerId": "player_id"})
    )

    # Joukkueiden xG ilman tyhjiin maaleihin ammuttuja laukauksia
    team_shots = shots[shots.shotOnEmptyNet == 0].assign(
        ev5=((shots.homeSkatersOnIce == 5) & (shots.awaySkatersOnIce == 5)).astype(int))
    team_shots = team_shots.assign(xg5=team_shots.xGoal * team_shots.ev5)
    teams = (
        team_shots.groupby(["game_id", "isHomeTeam"])
        .agg(xg=("xGoal", "sum"), xg_5v5=("xg5", "sum"),
             attempts=("xGoal", "size"), hd_attempts=("hd", "sum"))
        .reset_index()
    )
    side = games.set_index("game_id")[["home", "away"]]
    teams = teams[teams.game_id.isin(side.index)]
    teams["team"] = [
        side.at[g, "home"] if h == 1 else side.at[g, "away"]
        for g, h in zip(teams.game_id, teams.isHomeTeam)
    ]
    teams = teams.drop(columns="isHomeTeam")

    goalies = (
        shots[(shots.goalieIdForShot > 0) & (shots.shotOnEmptyNet == 0)]
        .groupby(["game_id", "goalieIdForShot"])
        .agg(xga=("xGoal", "sum"), xg_ga=("goal", "sum"), unblocked=("xGoal", "size"))
        .reset_index()
        .rename(columns={"goalieIdForShot": "player_id"})
    )
    goalies["gsax"] = goalies.xga - goalies.xg_ga

    return {"xg_players": players, "xg_teams": teams, "xg_goalies": goalies}
