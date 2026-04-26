from datetime import datetime
from typing import Literal
from zoneinfo import ZoneInfo

MealType = Literal[
    "breakfast",
    "lunch",
    "dinner",
    "snack",
    "pre-workout",
    "post-workout",
    "other",
]

TZ = ZoneInfo("America/Mexico_City")


def ok(data):
    return {"ok": True, "data": data}


def err(msg: str):
    return {"ok": False, "error": msg}


def today_mx() -> str:
    return datetime.now(TZ).date().isoformat()
