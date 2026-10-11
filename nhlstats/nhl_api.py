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


def stars(season_id: int) -> list[dict]:
    """Joukkueiden tähtipelaajat edellisen kauden runkosarjan perusteella.

    Kenttäpelaaja: aina vähintään 50 pistettä, ja lisäksi joukkueensa kolmen
    parhaan pistemiehen joukossa, puolustaja tai vähintään 65 pistettä.
    Maalivahti: joukkueensa ykkönen, vähintään 30 aloitusta.
    """
    prev = season_id - 10001  # 20262027 -> 20252026
    exp = f"seasonId={prev}%20and%20gameTypeId=2"
    sk = http.get(f"{STATS}/skater/summary?limit=-1&cayenneExp={exp}").json()["data"]
    gl = http.get(f"{STATS}/goalie/summary?limit=-1&cayenneExp={exp}").json()["data"]
    team = lambda r: (r.get("teamAbbrevs") or "").split(",")[-1].strip()

    out = {}
    by_team: dict[str, list[dict]] = {}
    for r in sk:
        by_team.setdefault(team(r), []).append(r)
    for t, rows in by_team.items():
        for r in sorted(rows, key=lambda r: r["points"], reverse=True)[:3]:
            if r["points"] >= 50:
                out[r["playerId"]] = (r, f'{t}:n {r["points"]} p')
    for r in sk:
        if r["points"] >= 65 or (r["positionCode"] == "D" and r["points"] >= 50):
            out.setdefault(r["playerId"], (r, f'{r["points"]} p'))
    result = [{"player_id": pid, "name": r["skaterFullName"], "team": team(r), "basis": basis}
              for pid, (r, basis) in out.items()]

    goalies_by_team: dict[str, dict] = {}
    for r in gl:
        t = team(r)
        if r["gamesStarted"] >= 30 and r["gamesStarted"] > goalies_by_team.get(t, {}).get("gamesStarted", 0):
            goalies_by_team[t] = r
    result += [{"player_id": r["playerId"], "name": r["goalieFullName"], "team": t,
                "basis": f'ykkösvahti, {r["gamesStarted"]} aloitusta'} for t, r in goalies_by_team.items()]
    return result


def roster_countries(team: str) -> dict[int, str]:
    """Joukkueen nykyisen rosterin pelaajien syntymämaat (esim. FIN)."""
    roster = http.get(f"{WEB}/roster/{team}/current").json()
    return {p["id"]: p.get("birthCountry", "")
            for group in ("forwards", "defensemen", "goalies") for p in roster.get(group, [])}


def player_country(player_id: int) -> str:
    return http.get(f"{WEB}/player/{player_id}/landing").json().get("birthCountry", "")


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
