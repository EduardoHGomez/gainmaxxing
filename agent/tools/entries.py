from __future__ import annotations

from datetime import date as date_cls, datetime
from typing import Optional

from langchain.tools import tool
from pydantic import BaseModel, Field

from agent.db import supabase
from agent.tools._shared import MealType, err, ok, today_mx


class LogEntryInput(BaseModel):
    food: str = Field(description="What was eaten, e.g. '2 tortillas with chicken'")
    calories: int = Field(ge=0, lt=10000)
    protein_g: float = Field(ge=0, lt=500)
    meal_type: Optional[MealType] = None
    notes: Optional[str] = None
    date: Optional[date_cls] = Field(
        default=None,
        description="ISO date YYYY-MM-DD. Defaults to today in America/Mexico_City.",
    )
    created_at: Optional[datetime] = Field(
        default=None,
        description="ISO timestamp for when the meal was eaten (e.g. 2026-04-25T08:30:00-06:00). Defaults to now. Use when backdating a meal logged late.",
    )


@tool("log_entry", args_schema=LogEntryInput)
def log_entry(food, calories, protein_g, meal_type=None, notes=None, date=None, created_at=None):
    """Record a meal or snack the user just ate. Pass `created_at` to backdate."""
    try:
        row = {
            "food": food,
            "calories": calories,
            "protein_g": protein_g,
            "meal_type": meal_type,
            "notes": notes,
        }
        if date is not None:
            row["date"] = date.isoformat()
        if created_at is not None:
            row["created_at"] = created_at.isoformat()
        res = supabase().table("entries").insert(row).execute()
        return ok(res.data[0] if res.data else None)
    except Exception as e:
        return err(str(e))


class EditLogEntryInput(BaseModel):
    id: int
    food: Optional[str] = None
    calories: Optional[int] = Field(default=None, ge=0, lt=10000)
    protein_g: Optional[float] = Field(default=None, ge=0, lt=500)
    meal_type: Optional[MealType] = None
    notes: Optional[str] = None
    date: Optional[date_cls] = None
    created_at: Optional[datetime] = Field(
        default=None,
        description="Correct the timestamp of when the meal was eaten (e.g. 2026-04-25T08:30:00-06:00).",
    )


@tool("edit_log_entry", args_schema=EditLogEntryInput)
def edit_log_entry(id, food=None, calories=None, protein_g=None, meal_type=None, notes=None, date=None, created_at=None):
    """Update fields of an existing log entry by id. Only fields provided are updated."""
    try:
        patch = {
            k: v
            for k, v in {
                "food": food,
                "calories": calories,
                "protein_g": protein_g,
                "meal_type": meal_type,
                "notes": notes,
                "date": date.isoformat() if date else None,
                "created_at": created_at.isoformat() if created_at else None,
            }.items()
            if v is not None
        }
        if not patch:
            return err("no fields to update")
        res = supabase().table("entries").update(patch).eq("id", id).execute()
        return ok(res.data[0] if res.data else None)
    except Exception as e:
        return err(str(e))


class DeleteLogEntryInput(BaseModel):
    id: int


@tool("delete_log_entry", args_schema=DeleteLogEntryInput)
def delete_log_entry(id):
    """Delete a log entry by id."""
    try:
        res = supabase().table("entries").delete().eq("id", id).execute()
        return ok({"deleted": len(res.data or [])})
    except Exception as e:
        return err(str(e))


class GetDaySummaryInput(BaseModel):
    date: Optional[date_cls] = Field(
        default=None,
        description="ISO date YYYY-MM-DD. Defaults to today in America/Mexico_City.",
    )


@tool("get_day_summary", args_schema=GetDaySummaryInput)
def get_day_summary(date=None):
    """Get all log entries for a date plus calorie/protein totals."""
    try:
        target = date.isoformat() if date is not None else today_mx()
        res = (
            supabase()
            .table("entries")
            .select("*")
            .eq("date", target)
            .order("created_at", desc=False)
            .execute()
        )
        rows = res.data or []
        totals = {
            "calories": sum(r.get("calories") or 0 for r in rows),
            "protein_g": round(sum(float(r.get("protein_g") or 0) for r in rows), 1),
            "count": len(rows),
        }
        return ok({"date": target, "entries": rows, "totals": totals})
    except Exception as e:
        return err(str(e))


class GetRangeSummaryInput(BaseModel):
    start_date: date_cls
    end_date: date_cls


@tool("get_range_summary", args_schema=GetRangeSummaryInput)
def get_range_summary(start_date, end_date):
    """Get all log entries between two dates inclusive, plus per-day totals."""
    try:
        res = (
            supabase()
            .table("entries")
            .select("*")
            .gte("date", start_date.isoformat())
            .lte("date", end_date.isoformat())
            .order("date", desc=False)
            .order("created_at", desc=False)
            .execute()
        )
        rows = res.data or []
        per_day: dict[str, dict] = {}
        for r in rows:
            d = r["date"]
            slot = per_day.setdefault(d, {"calories": 0, "protein_g": 0.0, "count": 0})
            slot["calories"] += r.get("calories") or 0
            slot["protein_g"] += float(r.get("protein_g") or 0)
            slot["count"] += 1
        for slot in per_day.values():
            slot["protein_g"] = round(slot["protein_g"], 1)
        return ok({"entries": rows, "per_day": per_day})
    except Exception as e:
        return err(str(e))


ENTRY_TOOLS = [
    log_entry,
    edit_log_entry,
    delete_log_entry,
    get_day_summary,
    get_range_summary,
]
