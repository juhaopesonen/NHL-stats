"""Suomenkieliset muotoilut."""
from datetime import date

WEEKDAYS = ["maanantai", "tiistai", "keskiviikko", "torstai", "perjantai", "lauantai", "sunnuntai"]


def num(x: float, decimals: int = 2) -> str:
    return f"{x:.{decimals}f}".replace(".", ",").replace("-", "−")


def toi(seconds: float) -> str:
    seconds = int(round(seconds))
    return f"{seconds // 60}.{seconds % 60:02d}"


def day_fi(day: date) -> str:
    return f"{WEEKDAYS[day.weekday()]} {day.day}.{day.month}.{day.year}"
