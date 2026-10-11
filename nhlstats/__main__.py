"""Komentorivi: python -m nhlstats [--date VVVV-KK-PP] [--no-fetch]"""
import argparse
import sys
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import pandas as pd

from . import injuries, insights, moneypuck, nhl_api, report, storage


def default_day() -> date:
    """Yön pelit = Suomen aikaa eilinen päivämäärä (Pohjois-Amerikan pelipäivä)."""
    return datetime.now(ZoneInfo("Europe/Helsinki")).date() - timedelta(days=1)


def season_of(day: date) -> int:
    start = day.year if day.month >= 7 else day.year - 1
    return start * 10000 + start + 1


def fetch_boxscores(season_id: int, until: date) -> None:
    """Hakee kaikki käsittelemättömät päivät kauden alusta annettuun päivään asti."""
    done = storage.processed_dates(season_id)
    day = nhl_api.season_start(season_id)
    while day <= until:
        if day.isoformat() not in done:
            games = [g for g in nhl_api.games_on(day) if g["gameType"] in nhl_api.GAME_TYPES]
            final = [g for g in games if g["gameState"] in nhl_api.FINAL_STATES]
            rows = {"games": [], "skaters": [], "goalies": []}
            for g in final:
                game_row, sk, gl = nhl_api.game_details(g, day)
                rows["games"].append(game_row)
                rows["skaters"] += sk
                rows["goalies"] += gl
            for name, r in rows.items():
                storage.upsert_games(season_id, name, r)
            pending = [g for g in games if g["gameState"] not in nhl_api.FINAL_STATES
                       and g.get("gameScheduleState") == "OK"]
            print(f"{day}: {len(final)} ottelua haettu" + (f", {len(pending)} kesken" if pending else ""))
            if not pending:
                storage.mark_processed(season_id, day.isoformat())
        day += timedelta(days=1)


def update_countries(skaters: pd.DataFrame, goalies: pd.DataFrame) -> pd.DataFrame:
    """Hakee syntymämaan pelaajille, joita ei vielä ole data/players.csv:ssä."""
    known = storage.load_players()
    played = pd.concat([skaters[["player_id", "team"]], goalies[["player_id", "team"]]])
    missing = set(played.player_id) - set(known.player_id)
    if not missing:
        return known
    found: dict[int, str] = {}
    for team in sorted(set(played[played.player_id.isin(missing)].team)):
        try:
            found.update(nhl_api.roster_countries(team))
        except Exception as e:
            print(f"Rosterin {team} haku epäonnistui: {e}")
    # Rosterista puuttuvat (siirretyt, alas lähetetyt) haetaan yksitellen
    for pid in missing - found.keys():
        try:
            found[pid] = nhl_api.player_country(pid)
        except Exception as e:
            print(f"Pelaajan {pid} haku epäonnistui: {e}")
    new = pd.DataFrame([{"player_id": p, "birth_country": found[p]} for p in missing if p in found])
    players = pd.concat([known, new], ignore_index=True)
    storage.save_players(players)
    print(f"Syntymämaat: {len(new)} uutta pelaajaa")
    return players


def update_injuries(season_id: int, skaters: pd.DataFrame, goalies: pd.DataFrame) -> None:
    """Tallentaa päivän loukkaantumislistan ja tunnistaa listan pelaajat."""
    try:
        players = storage.load_players()
        cols = ["player_id", "name", "team"]
        known = pd.concat([skaters[cols], goalies[cols]]).drop_duplicates("player_id", keep="last")
        if "name" in players.columns:  # aiemmin haulla löydetyt
            extra = players[players.name.astype(bool) & ~players.player_id.isin(known.player_id)]
            known = pd.concat([known, extra[["player_id", "name"]].assign(team=None)])
        snapshot = datetime.now(ZoneInfo("Europe/Helsinki")).date().isoformat()
        inj = injuries.fetch(snapshot, known)
        found = injuries.resolve_missing(inj)
        if found:
            new = pd.DataFrame(found)
            if "name" not in players.columns:
                players["name"] = ""
            players = players[~players.player_id.isin(new.player_id)]
            storage.save_players(pd.concat([players, new], ignore_index=True))
        storage.save_injuries(season_id, inj)
        print(f"Loukkaantumiset: {len(inj)} listalla, {len(found)} tunnistettu haulla, "
              f"{inj.player_id.isna().sum()} tunnistamatta")
    except Exception as e:
        print(f"Loukkaantumisten haku epäonnistui: {e}")


def main() -> None:
    parser = argparse.ArgumentParser(description="NHL-yöraportti")
    parser.add_argument("--date", type=date.fromisoformat, default=None,
                        help="pelipäivä (oletus: Suomen aikaa eilinen)")
    parser.add_argument("--no-fetch", action="store_true",
                        help="älä hae uutta dataa, käytä tallennettua")
    args = parser.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")

    day = args.date or default_day()
    season_id = season_of(day)

    if not args.no_fetch:
        fetch_boxscores(season_id, day)

    games = storage.load(season_id, "games")
    skaters = storage.load(season_id, "skaters")
    goalies = storage.load(season_id, "goalies")
    if games.empty:
        print("Ei otteluita tallennettuna, raporttia ei tehdä.")
        return

    xg = {name: storage.load(season_id, name) for name in ("xg_players", "xg_teams", "xg_goalies")}
    if not args.no_fetch:
        try:
            shots = moneypuck.download_shots(season_id // 10000)
            xg = moneypuck.aggregate(shots, games)
            for name, df in xg.items():
                storage.save(season_id, name, df)
            have = set(xg["xg_teams"].game_id)
            missing = games[(games.date == day.isoformat()) & ~games.game_id.isin(have)]
            print(f"MoneyPuck: xG {len(have)} ottelulle"
                  + (f", yön otteluista puuttuu vielä {len(missing)}" if len(missing) else ""))
        except Exception as e:  # raportti tehdään ilman xG:tä, jos MoneyPuck ei vastaa
            print(f"MoneyPuck-haku epäonnistui: {e}")
    xg = {k: (v if not v.empty else pd.DataFrame(columns=["game_id", "player_id", "team"]))
          for k, v in xg.items()}

    if not args.no_fetch:
        update_countries(skaters, goalies)
        update_injuries(season_id, skaters, goalies)
    players = storage.load_players()
    finns = set(players[players.birth_country == "FIN"].player_id)
    inj = storage.injuries_for(season_id, day.isoformat())

    items = insights.build(day.isoformat(), games, skaters, goalies, xg, inj)
    tables = insights.season_tables(day.isoformat(), skaters, xg["xg_players"], finns)
    report.write(day, report.render(day, games, skaters, goalies, xg, items, tables, finns, inj))
    print(f"Raportti {day}: {len(items)} nostoa -> docs/raportit/{day}.html")


if __name__ == "__main__":
    main()
