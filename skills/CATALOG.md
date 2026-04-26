# Logging rules

## Priority chain when the user describes a meal
1. **User gives explicit calories AND protein** → log those exact values, no second-guessing.
2. **User gives only calories OR only protein** → use the given value, calculate the other from the food description. Before doing a web search, confirm with the user (human in the loop)
3. **User gives neither** → calculate both from the food description. State your assumption in one short line ("logged ~520 kcal / ~38 g protein"). Confirm if you will do a web search.
4. **Food is unfamiliar or portion is ambiguous** → ask one specific clarifying question (e.g., "how many tortillas?"). Don't silently invent.
5. **You're confident enough to estimate within ±10%** → log without asking.

## When suggesting meals
- Pull from the `meals` catalog first via `list_meals`.
- Suggest options, not just one. The user can ask for alternatives.
- Respect the remaining kcal/protein budget for the day before suggesting (use `get_day_summary`).
- If uncertain what to eat and if the past instructions did not work, then suggest doing a web search for a meal and using the tools to register..

## When the user asks you to research a new food
- Only then go look it up. Otherwise, estimate from training data.
