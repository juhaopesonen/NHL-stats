"""Datan tallennus kausikohtaisiin CSV-tiedostoihin (data/2026-27/...)."""
from pathlib import Path

import pandas as pd

from .config import DATA_DIR

SORT_KEYS = ["date", "game_id"]


def season_dir(season_id: int) -> Path:
    start = season_id // 10000
    path = DATA_DIR / f"{start}-{str(start + 1)[-2:]}"
    path.mkdir(parents=True, exist_ok=True)
    return path


def load(season_id: int, name: str) -> pd.DataFrame:
    path = season_dir(season_id) / f"{name}.csv"
    if not path.exists():
        return pd.DataFrame()
    return pd.read_csv(path)


def save(season_id: int, name: str, df: pd.DataFrame) -> None:
    keys = [k for k in SORT_KEYS if k in df.columns]
    extra = ["player_id"] if "player_id" in df.columns else (["team"] if "team" in df.columns else [])
    df = df.sort_values(keys + extra or list(df.columns[:1]), kind="stable")
    # Peliajat ovat sekunteja: kokonaislukuina, jottei tiedosto muutu kokonaan puuttuvien arvojen takia
    for col in [c for c in df.columns if c == "toi" or c.endswith("_toi")]:
        df[col] = pd.to_numeric(df[col]).round().astype("Int64")
    df.to_csv(season_dir(season_id) / f"{name}.csv", index=False, float_format="%.4f", lineterminator="\n")


def upsert_games(season_id: int, name: str, rows: list[dict]) -> None:
    """Korvaa samojen otteluiden vanhat rivit uusilla."""
    if not rows:
        return
    new = pd.DataFrame(rows)
    old = load(season_id, name)
    if not old.empty:
        old = old[~old.game_id.isin(new.game_id.unique())]
        new = pd.concat([old, new], ignore_index=True)
    save(season_id, name, new)


def save_injuries(season_id: int, snapshot: pd.DataFrame) -> None:
    """Loukkaantumislistan päiväkohtainen tilannekuva; saman päivän vanha korvataan."""
    old = load(season_id, "injuries")
    if not old.empty:
        old = old[old.snapshot != snapshot.snapshot.iloc[0]]
        snapshot = pd.concat([old, snapshot], ignore_index=True)
    snapshot = snapshot.sort_values(["snapshot", "team", "name"], kind="stable")
    snapshot.to_csv(season_dir(season_id) / "injuries.csv", index=False, lineterminator="\n")


def injuries_for(season_id: int, day: str) -> pd.DataFrame:
    """Uusin tilannekuva, joka on otettu viimeistään pelipäivää seuraavana päivänä."""
    df = load(season_id, "injuries")
    if df.empty:
        return df
    limit = (pd.Timestamp(day) + pd.Timedelta(days=1)).strftime("%Y-%m-%d")
    df = df[df.snapshot <= limit]
    if df.empty:
        return df
    df = df[df.snapshot == df.snapshot.max()].copy()
    df["player_id"] = df.player_id.astype("Int64")
    return df.fillna({"injury": "", "return_date": "", "updated": "", "espn_url": "", "position": ""})


PLAYERS_FILE = DATA_DIR / "players.csv"


def load_players() -> pd.DataFrame:
    """Pelaajien syntymämaat (kaudesta riippumaton)."""
    if not PLAYERS_FILE.exists():
        return pd.DataFrame(columns=["player_id", "birth_country"])
    return pd.read_csv(PLAYERS_FILE, keep_default_na=False)


def save_players(df: pd.DataFrame) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    df.sort_values("player_id").to_csv(PLAYERS_FILE, index=False, lineterminator="\n")


def processed_dates(season_id: int) -> set[str]:
    path = season_dir(season_id) / "processed_dates.txt"
    if not path.exists():
        return set()
    return {line.strip() for line in path.read_text().splitlines() if line.strip()}


def mark_processed(season_id: int, day: str) -> None:
    dates = processed_dates(season_id) | {day}
    (season_dir(season_id) / "processed_dates.txt").write_text("\n".join(sorted(dates)) + "\n")
