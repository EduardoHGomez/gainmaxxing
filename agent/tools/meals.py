from __future__ import annotations

from typing import Optional

from langchain.tools import tool
from pydantic import BaseModel, Field

from agent.db import supabase
from agent.tools._shared import MealType, err, ok


class AddMealInput(BaseModel):
    name: str = Field(description="A short, unique nickname for this catalog item.")
    food: str
    calories: int = Field(ge=0, lt=10000)
    protein_g: float = Field(ge=0, lt=500)
    portion: Optional[str] = Field(
        default=None,
        description="Portion size the calories/protein refer to (e.g., '1 bowl', '200g', '2 tortillas').",
    )
    meal_type: Optional[MealType] = None
    notes: Optional[str] = None


@tool("add_meal", args_schema=AddMealInput)
def add_meal(name, food, calories, protein_g, portion=None, meal_type=None, notes=None):
    """Add a meal to the user's curated catalog of foods that work."""
    try:
        row = {
            "name": name,
            "food": food,
            "calories": calories,
            "protein_g": protein_g,
            "portion": portion,
            "meal_type": meal_type,
            "notes": notes,
        }
        res = supabase().table("meals").insert(row).execute()
        return ok(res.data[0] if res.data else None)
    except Exception as e:
        return err(str(e))


class UpdateMealInput(BaseModel):
    id: int
    name: Optional[str] = None
    food: Optional[str] = None
    calories: Optional[int] = Field(default=None, ge=0, lt=10000)
    protein_g: Optional[float] = Field(default=None, ge=0, lt=500)
    portion: Optional[str] = None
    meal_type: Optional[MealType] = None
    notes: Optional[str] = None


@tool("update_meal", args_schema=UpdateMealInput)
def update_meal(id, name=None, food=None, calories=None, protein_g=None, portion=None, meal_type=None, notes=None):
    """Update a catalog meal by id. Only fields provided are updated."""
    try:
        patch = {
            k: v
            for k, v in {
                "name": name,
                "food": food,
                "calories": calories,
                "protein_g": protein_g,
                "portion": portion,
                "meal_type": meal_type,
                "notes": notes,
            }.items()
            if v is not None
        }
        if not patch:
            return err("no fields to update")
        res = supabase().table("meals").update(patch).eq("id", id).execute()
        return ok(res.data[0] if res.data else None)
    except Exception as e:
        return err(str(e))


class DeleteMealInput(BaseModel):
    id: int


@tool("delete_meal", args_schema=DeleteMealInput)
def delete_meal(id):
    """Delete a catalog meal by id."""
    try:
        res = supabase().table("meals").delete().eq("id", id).execute()
        return ok({"deleted": len(res.data or [])})
    except Exception as e:
        return err(str(e))


class ListMealsInput(BaseModel):
    meal_type: Optional[MealType] = None


@tool("list_meals", args_schema=ListMealsInput)
def list_meals(meal_type=None):
    """List catalog meals, optionally filtered by meal_type."""
    try:
        q = supabase().table("meals").select("*").order("name", desc=False)
        if meal_type is not None:
            q = q.eq("meal_type", meal_type)
        res = q.execute()
        return ok(res.data or [])
    except Exception as e:
        return err(str(e))


MEAL_TOOLS = [add_meal, update_meal, delete_meal, list_meals]
