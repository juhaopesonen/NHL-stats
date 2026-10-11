"""Komentorivi: python -m nhlstats [--date VVVV-KK-PP] [--no-fetch]"""
import argparse
import sys
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import pandas as pd

from . import injuries, insights, moneypuck, nhl_api, onice, report, storage


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


SPLIT_COLS = ["ev_toi", "pp_toi", "sh_toi"]


def fill_toi_splits(season_id: int) -> None:
    """Täydentää kenttäpelaajille yv-, av- ja tasakenttäajat päiville, joilta ne puuttuvat."""
    skaters = storage.load(season_id, "skaters")
    if skaters.empty:
        return
    for col in SPLIT_COLS:
        if col not in skaters.columns:
            skaters[col] = pd.NA
    missing = skaters.groupby("date").pp_toi.apply(lambda s: s.isna().all())
    days = sorted(missing[missing].index)
    if not days:
        return
    for day in days:
        try:
            rows = nhl_api.toi_splits(date.fromisoformat(day))
        except Exception as e:
            print(f"Peliaikajakauman haku {day} epäonnistui: {e}")
            continue
        if not rows:
            continue
        split = pd.DataFrame(rows).set_index(["game_id", "player_id"])
        idx = skaters.date == day
        keys = pd.MultiIndex.from_frame(skaters.loc[idx, ["game_id", "player_id"]])
        for col in SPLIT_COLS:
            skaters.loc[idx, col] = split[col].reindex(keys).to_numpy()
    storage.save(season_id, "skaters", skaters)
    print(f"Peliaikajakauma (yv/av/tasak.) täydennetty {len(days)} päivälle")


def update_onice_games(season_id: int, shots: pd.DataFrame, games: pd.DataFrame, day: date) -> None:
    """Laskee 5v5-jäällä-luvut otteluille, joilta ne puuttuvat (vaihtodata yritetään viikon ajan)."""
    done = storage.load(season_id, "onice_games")
    have = set(done.game_id) if not done.empty else set()
    with_shots = set(shots.game_id)
    recent = (day - timedelta(days=7)).isoformat()
    todo = games[~games.game_id.isin(have) & games.game_id.isin(with_shots) & (games.date >= recent)]
    if have == set() and not todo.empty:  # ensimmäinen ajo: koko kausi
        todo = games[games.game_id.isin(with_shots)]
    parts = []
    for g in todo.itertuples():
        try:
            df = onice.game_onice(g.game_id, shots, g.home, g.away)
        except Exception as e:
            print(f"Vaihtodatan haku {g.game_id} epäonnistui: {e}")
            continue
        if not df.empty:
            parts.append(df.assign(date=g.date))
    if parts:
        storage.upsert_games(season_id, "onice_games", pd.concat(parts).to_dict("records"))
    print(f"5v5 jäällä -luvut: {len(parts)}/{len(todo)} ottelua laskettu")


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
        fill_toi_splits(season_id)

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
            update_onice_games(season_id, shots, games, day)
        except Exception as e:  # raportti tehdään ilman xG:tä, jos MoneyPuck ei vastaa
            print(f"MoneyPuck-haku epäonnistui: {e}")
        try:
            storage.save(season_id, "onice_5v5", moneypuck.download_onice_5v5(season_id // 10000))
        except Exception as e:
            print(f"MoneyPuckin 5v5-kausikoosteen haku epäonnistui: {e}")
    xg = {k: (v if not v.empty else pd.DataFrame(columns=["game_id", "player_id", "team"]))
          for k, v in xg.items()}
    xg["onice_games"] = storage.load(season_id, "onice_games")

    if not args.no_fetch:
        update_countries(skaters, goalies)
        update_injuries(season_id, skaters, goalies)
    players = storage.load_players()
    finns = set(players[players.birth_country == "FIN"].player_id)
    inj = storage.injuries_for(season_id, day.isoformat())
    stars = storage.load(season_id, "stars")
    if stars.empty and not args.no_fetch:
        try:
            stars = pd.DataFrame(nhl_api.stars(season_id))
            storage.save(season_id, "stars", stars)
            print(f"Tähtipelaajat: {len(stars)} (edellisen kauden tilastoista)")
        except Exception as e:
            print(f"Tähtipelaajien haku epäonnistui: {e}")

    items = insights.build(day.isoformat(), games, skaters, goalies, xg, inj)
    tables = insights.season_tables(day.isoformat(), skaters, xg["xg_players"], finns,
                                    storage.load(season_id, "onice_5v5"), goalies, xg["xg_goalies"])
    report.write(day, report.render(day, games, skaters, goalies, xg, items, tables, finns, inj, stars))
    print(f"Raportti {day}: {len(items)} nostoa -> docs/raportit/{day}.html")


if __name__ == "__main__":
    main()
