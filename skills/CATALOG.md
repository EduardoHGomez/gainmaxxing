# Logging rules

## One meal = one entry
- A composite food (sandwich, bowl, burrito, smoothie, wrap, etc.) is **one** `log_entry` call, not one per ingredient.
- `calories` and `protein_g` hold the total for the whole composite.
- Only split into multiple entries when the user clearly ate them as separate items at separate times (e.g., "an apple at 10am, then a sandwich at 1pm").

## Editing past entries
- Logged values are not final. If the user says "actually that was 480 cal not 350" or "fix entry 42", call `edit_log_entry` with the corrected fields. To find an id, use `get_day_summary` first.

## Dates and times
- **Do not pass `date` or `created_at` to `log_entry` unless the user explicitly says when they ate it** (e.g., "yesterday", "at 2pm"). Let the database default fill them in — it uses America/Mexico_City local time, which is already correct.
- If the user says "yesterday at 8pm", convert to `America/Mexico_City` time when passing `created_at`. Never use UTC.
- When in doubt, omit the field. Today is whatever the database says today is.

## Priority chain when the user describes a meal
1. **User gives explicit calories AND protein** → log those exact values, no second-guessing.
2. **User gives only calories OR only protein** → use the given value, calculate the other from the food description. Before doing a web search, confirm with the user (human in the loop)
3. **User gives neither** → calculate both from the food description. State your assumption in one short line ("logged ~520 kcal / ~38 g protein"). Confirm if you will do a web search.
4. **Food is unfamiliar or portion is ambiguous** → ask one specific clarifying question (e.g., "how many tortillas?"). Don't silently invent.
5. **You're confident enough to estimate within ±10%** → log without asking.

## Adding to the catalog
- When calling `add_meal`, always fill `portion` with the size the `calories` and `protein_g` refer to (e.g., `"1 bowl"`, `"200g"`, `"2 tortillas"`). Without it the numbers are meaningless for future scaling.

## When suggesting meals
- Pull from the `meals` catalog first via `list_meals`.
- Suggest options, not just one. The user can ask for alternatives.
- Respect the remaining kcal/protein budget for the day before suggesting (use `get_day_summary`).
- If uncertain what to eat and if the past instructions did not work, then suggest doing a web search for a meal and using the tools to register..

## When the user asks you to research a new food
- Only then go look it up. Otherwise, estimate from training data.
