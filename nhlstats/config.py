"""Projektin asetukset ja analyysien raja-arvot."""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
DOCS_DIR = ROOT / "docs"
REPORTS_DIR = DOCS_DIR / "raportit"

USER_AGENT = "NHL-stats (+https://github.com/juhaopesonen/NHL-stats)"
REQUEST_DELAY = 0.25  # sekuntia pyyntöjen välissä, ettei rajapintoja kuormiteta

# Nostojen raja-arvot
POINT_STREAK_MIN = 3          # kausitaulukon pisteputket vähintään N peliä
POINT_STREAK_GROUP = 5        # yön nostoihin koottuna vähintään N pelin putket
POINT_STREAK_SOLO = 8         # oma nostonsa vähintään N pelin putkelle
GOAL_STREAK_MIN = 3           # maaliputki vähintään N peliä
STREAK_ENDED_MIN = 5          # katkennut pisteputki vähintään N peliä
GOAL_DROUGHT_MIN = 10         # päättynyt maaliton jakso vähintään N peliä
UNLUCKY_IXG = 1.0             # ixG vähintään tämä mutta 0 maalia
FINISHER_MARGIN = 1.5         # maalit - ixG vähintään tämä (ja >= 2 maalia)
TEAM_XG_SHARE = 0.60          # hävinnyt joukkue, jonka xG-osuus vähintään tämä
GOALIE_GSAX = 2.0             # maalivahdin |GSAx| vähintään tämä
TOI_MIN_GAMES = 5             # peliaikapoikkeama vaatii vähintään N aiempaa peliä
TOI_UP_RATIO = 1.35
TOI_DOWN_RATIO = 0.60
HIGH_DANGER_XG = 0.20         # MoneyPuckin "high danger" -raja laukauksen xG:lle
