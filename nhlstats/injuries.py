"""Loukkaantumiset ESPN:n avoimesta rajapinnasta (tiedot RotoWirelta).

Raporttiin otetaan vain faktatiedot (tila, vamman tyyppi, arvioitu paluu),
ei uutistekstejä.
"""
import unicodedata

import pandas as pd

from . import http

URL = "https://site.api.espn.com/apis/site/v2/sports/hockey/nhl/injuries"

TEAM_FIX = {"LA": "LAK", "NJ": "NJD", "SJ": "SJS", "TB": "TBL", "CLB": "CBJ", "UTAH": "UTA"}

STATUS_FI = {
    "Day-To-Day": "päivittäinen arvio",
    "Out": "sivussa",
    "Injured Reserve": "IR-listalla",
    "Long Term Injured Reserve": "LTIR-listalla",
    "Suspension": "pelikielto",
}

TYPE_FI = {
    "Lower Body": "alavartalo", "Upper Body": "ylävartalo", "Undisclosed": "ei kerrottu",
    "Knee": "polvi", "Shoulder": "olkapää", "Hip": "lonkka", "Head": "pää",
    "Concussion": "aivotärähdys", "Ankle": "nilkka", "Foot": "jalkaterä", "Hand": "käsi",
    "Wrist": "ranne", "Back": "selkä", "Groin": "nivus", "Illness": "sairaus", "Neck": "niska",
    "Elbow": "kyynärpää", "Leg": "jalka", "Face": "kasvot", "Achilles": "akillesjänne",
    "Hamstring": "takareisi", "Abdomen": "vatsa", "Ribs": "kylkiluut", "Finger": "sormi",
    "Thumb": "peukalo", "Personal": "henkilökohtainen syy", "Eye": "silmä", "Jaw": "leuka",
    "Lower Leg": "sääri", "Thigh": "reisi", "Chest": "rintakehä", "Arm": "käsivarsi",
    "Calf": "pohje", "Quadricep": "etureisi", "Oblique": "kylki", "Pectoral": "rintalihas",
    "Collarbone": "solisluu", "Toe": "varvas", "Heel": "kantapää", "Lower-body": "alavartalo",
    "Upper-body": "ylävartalo", "Not Injury Related": "ei vamma",
    "Contract Dispute": "sopimuskiista", "Suspension": "pelikielto", "Covid-19": "koronavirus",
    "Rest": "lepo", "Skull": "kallo", "Torso": "vartalo", "Kidney": "munuainen", "Spleen": "perna",
    "Bicep": "hauislihas", "Tricep": "ojentajalihas", "Lower Back": "alaselkä",
}

COLUMNS = ["snapshot", "player_id", "name", "team", "position", "status", "injury",
           "return_date", "updated", "espn_url"]


def normalize(name: str) -> str:
    text = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    return "".join(ch for ch in text.lower() if ch.isalpha())


def fetch(snapshot: str, known: pd.DataFrame) -> pd.DataFrame:
    """Hakee nykyisen loukkaantumislistan ja yhdistää pelaajat NHL:n tunnisteisiin.

    known: DataFrame (player_id, name, team) kauden pelaajista.
    """
    data = http.get(URL).json()
    known = known.dropna(subset=["name"])
    by_team = {(normalize(n), t): int(pid) for pid, n, t in zip(known.player_id, known.name, known.team)
               if isinstance(t, str)}
    by_name: dict[str, set[int]] = {}
    for pid, n in zip(known.player_id, known.name):
        by_name.setdefault(normalize(n), set()).add(int(pid))

    rows = []
    for team in data.get("injuries", []):
        for item in team.get("injuries", []):
            ath = item.get("athlete", {})
            name = ath.get("displayName", "")
            abbr = ath.get("team", {}).get("abbreviation", "")
            abbr = TEAM_FIX.get(abbr, abbr)
            key = normalize(name)
            pid = by_team.get((key, abbr))
            if pid is None and len(by_name.get(key, ())) == 1:
                pid = next(iter(by_name[key]))
            details = item.get("details", {})
            link = next((l["href"] for l in ath.get("links", []) if "playercard" in l.get("rel", [])), "")
            rows.append({
                "snapshot": snapshot,
                "player_id": pid,
                "name": name,
                "team": abbr,
                "position": ath.get("position", {}).get("abbreviation", ""),
                "status": item.get("status", ""),
                "injury": details.get("type", ""),
                "return_date": details.get("returnDate", ""),
                "updated": (item.get("date") or "")[:10],
                "espn_url": link,
            })
    df = pd.DataFrame(rows, columns=COLUMNS)
    df["player_id"] = df.player_id.astype("Int64")
    return df


SEARCH = "https://search.d3.nhle.com/api/v1/search/player?culture=en-us&limit=10&q={q}"


def search_player(name: str, team: str) -> dict | None:
    """Etsii pelaajan NHL:n haulla (myös pitkään sivussa olleet, joita ei ole rostereissa)."""
    from urllib.parse import quote
    hits = [h for h in http.get(SEARCH.format(q=quote(name))).json()
            if normalize(h.get("name", "")) == normalize(name)]
    exact = [h for h in hits if team in (h.get("teamAbbrev"), h.get("lastTeamAbbrev"))]
    pick = exact[0] if exact else hits[0] if len(hits) == 1 else None
    if pick is None:
        return None
    return {"player_id": int(pick["playerId"]), "birth_country": pick.get("birthCountry") or "",
            "name": name}


def resolve_missing(df: pd.DataFrame) -> list[dict]:
    """Täydentää puuttuvat NHL-tunnisteet haulla; palauttaa löydetyt pelaajat."""
    found = []
    for idx in df.index[df.player_id.isna()]:
        try:
            hit = search_player(df.at[idx, "name"], df.at[idx, "team"])
        except Exception:
            hit = None
        if hit:
            df.at[idx, "player_id"] = hit["player_id"]
            found.append(hit)
    return found


def status_fi(status: str) -> str:
    return STATUS_FI.get(status, status)


def injury_fi(injury: str) -> str:
    return TYPE_FI.get(injury, injury) if injury else "ei kerrottu"
