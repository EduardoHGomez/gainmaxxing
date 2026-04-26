# gainmaxxing

A personal AI nutrition coach. Logs meals conversationally to Supabase, tracks calories and protein against a daily target, queries history, and suggests meals from a curated catalog. Built on LangChain 1.0 + LangGraph + Supabase. Designed to be texted via WhatsApp/Telegram (Twilio integration deferred).

## Quick start

This project uses [`uv`](https://docs.astral.sh/uv/) for everything — venv, installs, and running commands.

```bash
# 1. Create the virtual env (uv venv writes to .venv/)
uv venv

# 2. Install the project + locked deps into it
uv sync

# 3. Fill in keys + your personal profile
cp .env.example .env
# edit .env: OPENAI_API_KEY, SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY
cp skills/PROFILE.example.md skills/PROFILE.md
# edit skills/PROFILE.md with your data — it's gitignored

# 4. Create the Supabase tables
# Open Supabase → SQL editor → paste sql/schema.sql → run

# 5a. Run via langgraph dev (recommended for iteration)
uv run langgraph dev

# 5b. Or run via FastAPI (when wiring Twilio / containers)
uv run uvicorn server.app:app --host 0.0.0.0 --port 8000
```

Studio UI: <https://smith.langchain.com/studio/?baseUrl=http://127.0.0.1:2024>

To activate the venv manually (so bare `python`, `langgraph`, `uvicorn` work without the `uv run` prefix): `source .venv/bin/activate` (Windows: `.venv\Scripts\activate`). Deactivate with `deactivate`.

## Layout

```
gainmaxxing/
├── skills/
│   ├── PROFILE.example.md  # template — copy to PROFILE.md and fill in (PROFILE.md is gitignored)
│   ├── BEHAVIOR.md         # tone + what the agent doesn't do
│   └── CATALOG.md          # logging priority chain (calories/protein resolution)
├── agent/
│   ├── graph.py       # create_agent → exports `graph` (loads skills/*.md)
│   ├── db.py          # Supabase client singleton
│   └── tools/
│       ├── entries.py # log_meal, edit, delete, day/range summaries
│       ├── meals.py   # catalog CRUD
│       └── _shared.py # MealType, ok/err helpers, MX-tz today()
├── server/
│   └── app.py         # FastAPI entry point — Twilio webhook lands here in Stage 3
├── docs/CONTEXT.md    # single-doc project context — read this first
├── sql/schema.sql     # paste into Supabase SQL editor (creates roles + RLS)
├── langgraph.json     # langgraph dev config (entry: agent/graph.py:graph)
└── pyproject.toml     # uv project + pinned deps
```

## Run modes

| Mode | Command | Purpose |
|---|---|---|
| `langgraph dev` | `uv run langgraph dev` | Local iteration, Studio UI, in-memory checkpoints |
| FastAPI | `uv run uvicorn server.app:app` | Twilio webhook, SQLite-persisted checkpoints (Stage 3) |

Both import `agent.graph:graph`. See `docs/CONTEXT.md` for the full deployment story.

## Editing the agent's behavior

Edit `skills/PROFILE.md` / `skills/BEHAVIOR.md` / `skills/CATALOG.md` in place, then restart the server. No code change, no redeploy.

## Further reading

`docs/CONTEXT.md` — single-document project context: architecture, data model, design decisions, gotchas, and full deployment plan.
