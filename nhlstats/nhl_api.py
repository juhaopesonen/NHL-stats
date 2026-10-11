"""NHL:n avoin rajapinta (api-web.nhle.com): ottelut, tulokset ja boxscoret."""
from datetime import date

from . import http

WEB = "https://api-web.nhle.com/v1"
STATS = "https://api.nhle.com/stats/rest/en"

FINAL_STATES = {"OFF", "FINAL"}
GAME_TYPES = {2: "runkosarja", 3: "pudotuspelit"}  # 1 = harjoitusottelut, ohitetaan


def season_start(season_id: int) -> date:
    """Kauden aloituspäivä NHL:n tilastorajapinnasta, varalla 25.9."""
    try:
        data = http.get(f"{STATS}/season?cayenneExp=id={season_id}").json()["data"]
        return date.fromisoformat(data[0]["startDate"][:10])
    except Exception:
        return date(season_id // 10000, 9, 25)


def games_on(day: date) -> list[dict]:
    """Päivän ottelut (yhdysvaltalainen päivämäärä)."""
    return http.get(f"{WEB}/score/{day.isoformat()}").json().get("games", [])


def _toi_seconds(toi: str | None) -> int:
    if not toi:
        return 0
    minutes, seconds = toi.split(":")
    return int(minutes) * 60 + int(seconds)


def game_details(game: dict, day: date) -> tuple[dict, list[dict], list[dict]]:
    """Palauttaa (ottelurivi, kenttäpelaajarivit, maalivahtirivit) yhdelle ottelulle."""
    gid = game["id"]
    box = http.get(f"{WEB}/gamecenter/{gid}/boxscore").json()
    pbp = http.get(f"{WEB}/gamecenter/{gid}/play-by-play").json()

    names = {
        r["playerId"]: f'{r["firstName"]["default"]} {r["lastName"]["default"]}'
        for r in pbp.get("rosterSpots", [])
    }
    away, home = box["awayTeam"], box["homeTeam"]
    game_row = {
        "game_id": gid,
        "date": day.isoformat(),
        "game_type": box["gameType"],
        "away": away["abbrev"],
        "home": home["abbrev"],
        "away_name": f'{away["placeName"]["default"]} {away["commonName"]["default"]}',
        "home_name": f'{home["placeName"]["default"]} {home["commonName"]["default"]}',
        "away_score": away.get("score", 0),
        "home_score": home.get("score", 0),
        "away_sog": away.get("sog", 0),
        "home_sog": home.get("sog", 0),
        "last_period": (box.get("gameOutcome") or {}).get("lastPeriodType", "REG"),
    }

    skaters, goalies = [], []
    for side, team, opp in (("awayTeam", away["abbrev"], home["abbrev"]),
                            ("homeTeam", home["abbrev"], away["abbrev"])):
        stats = box["playerByGameStats"][side]
        for p in stats.get("forwards", []) + stats.get("defense", []):
            skaters.append({
                "game_id": gid, "date": day.isoformat(),
                "player_id": p["playerId"],
                "name": names.get(p["playerId"], p["name"]["default"]),
                "team": team, "opp": opp, "position": p.get("position", ""),
                "goals": p.get("goals", 0), "assists": p.get("assists", 0),
                "points": p.get("points", 0), "sog": p.get("sog", 0),
                "pp_goals": p.get("powerPlayGoals", 0),
                "plus_minus": p.get("plusMinus", 0), "hits": p.get("hits", 0),
                "blocks": p.get("blockedShots", 0),
                "toi": _toi_seconds(p.get("toi")),
            })
        for p in stats.get("goalies", []):
            toi = _toi_seconds(p.get("toi"))
            if toi == 0:
                continue
            goalies.append({
                "game_id": gid, "date": day.isoformat(),
                "player_id": p["playerId"],
                "name": names.get(p["playerId"], p["name"]["default"]),
                "team": team, "opp": opp,
                "shots_against": p.get("shotsAgainst", 0),
                "saves": p.get("saves", 0),
                "goals_against": p.get("goalsAgainst", 0),
                "decision": p.get("decision", ""),
                "starter": bool(p.get("starter", False)),
                "toi": toi,
            })
    return game_row, skaters, goalies
