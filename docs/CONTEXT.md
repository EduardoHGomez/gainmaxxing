# Project context

Single-document context file. Read this first if you're a new collaborator (human or AI) reviving the project — it covers what the system is, how it's wired, why each non-obvious choice was made, and how to deploy it.

---

## What this is

A personal AI nutrition coach the user texts (WhatsApp/Telegram once Twilio is wired). It logs meals conversationally to Supabase, tracks calories and protein against a daily target, queries history, and suggests meals from a curated catalog. Single user, single domain, minimal token footprint.

The codebase is generic — no personal details are baked into code or skills. All user-specific data lives in `skills/PROFILE.md` (which the deployer fills in) and the Supabase database.

## Components

```
user message
    │
    ▼
┌──────────────────────────────┐
│  agent/graph.py:graph        │  create_agent(model, tools, system_prompt)
│   - model: ChatOpenAI         │
│   - tools: TOOLS (9)          │
│   - system_prompt:            │
│       PROFILE + BEHAVIOR +    │
│       CATALOG (concatenated)  │
└──────────────────────────────┘
    │           │
    │           └────► Supabase (Postgres)
    │                     - entries (meal log)
    │                     - meals   (catalog)
    ▼
checkpointer
  - in-memory   (langgraph dev mode)
  - SqliteSaver (FastAPI / container mode, future)
```

## Data model

### `entries` — what was eaten
| column | type | notes |
|---|---|---|
| `id` | `bigint` PK | auto |
| `created_at` | `timestamptz` | `now()` |
| `date` | `date` | defaults to today in America/Mexico_City |
| `meal_type` | `text` | breakfast / lunch / dinner / snack / pre-workout / post-workout / other |
| `food` | `text` | freeform description |
| `calories` | `integer` | 0–9999 |
| `protein_g` | `numeric(5,1)` | 0–500 |
| `notes` | `text` | optional |

### `meals` — curated catalog of foods that work
Same shape, plus `name` (unique, case-insensitive) and `updated_at` (auto-bumped). No FK to `entries` — they're independent.

## Tools (`agent/tools.py`)

| Tool | Table | What it does |
|---|---|---|
| `log_entry` | entries | insert what the user just ate |
| `edit_log_entry` | entries | partial update by id |
| `delete_log_entry` | entries | delete by id |
| `get_day_summary` | entries | rows + totals for a single day (defaults today MX) |
| `get_range_summary` | entries | rows + per-day totals across a range |
| `add_meal` | meals | add to the catalog |
| `update_meal` | meals | partial update by id |
| `delete_meal` | meals | delete by id |
| `list_meals` | meals | read all (optionally filter by `meal_type`) |

Every tool returns `{"ok": True, "data": ...}` or `{"ok": False, "error": "..."}`. Exceptions are caught inside the function and never re-raised — see "tools never raise" below.

## Request flow

1. User message arrives (via `langgraph dev` API, or the future Twilio webhook).
2. Graph state appends the human message.
3. LLM is called with `system_prompt` + history + tool schemas.
4. LLM either replies in text or calls one of the 9 tools.
5. Tool runs, hits Supabase via the service_role client, returns a structured dict.
6. LLM observes the tool result and either calls another tool or finalizes a reply.
7. Reply is returned to the caller.

---

## Decisions (why each non-obvious choice was made)

### Skills live in `skills/` — split into PROFILE + BEHAVIOR + CATALOG
Three short markdown files in `skills/`, concatenated at agent build by `agent/prompt.py`. Single file would have been simpler, but separating **what the user is** (PROFILE), **how the agent should talk** (BEHAVIOR), and **how meals get logged** (CATALOG) lets each be edited without re-reading the others. Total tokens are unchanged. The `skills/` name follows Anthropic's convention for on-demand domain skills; future skills (workouts, progress, meal-planning) would land here too.

### No FK between `entries` and `meals`
`entries` records what was eaten; `meals` is a curated catalog of foods that work. Different domains. A meal entry shouldn't break if its catalog row is deleted, and a catalog row shouldn't be locked from deletion just because it's been logged before. The agent uses `list_meals` for suggestion context, not for FK lookups.

### Service role only, RLS enabled, no anon policies
The bot is server-side and uses the Supabase service_role key, which bypasses RLS. RLS is still enabled on both tables so that if anon/authenticated keys ever leak or get used by accident, no rows are exposed. Never put the service_role key in client code.

**Where the keys come from.** Supabase auto-creates three Postgres roles per project — `anon`, `authenticated`, `service_role` — so `schema.sql` can grant/revoke against them out of the box. The corresponding API keys live in the Supabase Dashboard under **Project Settings → API Keys**:
- `SUPABASE_URL` — top of the page ("Project URL").
- `SUPABASE_SERVICE_ROLE_KEY` — "Legacy API Keys" tab (`service_role` JWT) **or** the new "API Keys" tab (`sb_secret_...`). Both map to the `service_role` Postgres role and both bypass RLS.
- The publishable / `anon` key is not used by this bot — it's safe to ignore unless you ever add a client-side surface.

`schema.sql` enables RLS, adds zero policies for `anon` / `authenticated` (so RLS denies everything for those roles), explicitly `revoke`s table privileges from them, and `grant`s full access to `service_role`. The bot, using the service_role key, has full access; anything else is locked out.

### No checkpointer bound in `agent/graph.py`
`langgraph dev` provides its own in-memory checkpointer at runtime. Binding one in code (e.g., a `SqliteSaver`) conflicts with that. The Stage-3 FastAPI entry point will import the same `graph` and re-compile it with a `SqliteSaver` for persistence — that's the right place to wire one.

### Mexico_City timezone defaults at the DB level
The VPS will be UTC. If `date` defaults were computed in Python or as Postgres `now()::date` (UTC), meals logged after 6pm CST would be attributed to the next day. The DB column uses `default ((now() at time zone 'America/Mexico_City')::date)` so it's correct regardless of host timezone. Tools that need "today" client-side use `zoneinfo.ZoneInfo("America/Mexico_City")`.

### langgraph dev for iteration, FastAPI for prod containers
Two run modes share the same graph:
- **`langgraph dev`** — fast iteration, Studio UI for visual debugging, in-memory state (lost on restart).
- **FastAPI** — long-running process for the Twilio webhook, SQLite-persisted checkpoints, runs in a container.

Both import `agent.graph:graph`. No code is duplicated.

### Tools never raise; they return `{"ok": False, "error": ...}`
LangGraph's checkpointer stores tool calls and their responses as a paired structure. If a tool call gets recorded but no response comes back (because the function raised), the dangling `tool_call_id` corrupts the thread — every future message on that thread fails. Wrapping every tool body in `try/except` and returning a structured error dict prevents this. The LLM sees the error and can recover; the checkpointer stays consistent.

---

## Critical gotchas (with where each is addressed)

1. **`reasoning_effort` breaks function tools on /v1/chat/completions for gpt-5.4-mini.** → Omitted in `agent/graph.py`. If you need reasoning, switch to the responses API.
2. **LangChain 1.0 renamed `prompt` to `system_prompt`** in `create_agent`. → Used correctly in `agent/graph.py`.
3. **Tool exceptions corrupt LangGraph checkpointer history.** → Every tool in `agent/tools.py` wraps its body in `try/except` returning `{"ok": False, "error": str(e)}`.
4. **Recovery for poisoned threads.** If `graph.invoke` fails with "tool_calls" + "tool_call_id" in the error, retry with a fresh `thread_id` (append timestamp salt). → Deferred to FastAPI mode.
5. **TwiML XML escaping.** Reply text must escape `&` → `&amp;`, `<` → `&lt;`, `>` → `&gt;` before going into `<Message>`. → Deferred to FastAPI mode.
6. **Supabase service_role key bypasses RLS.** Fine for the bot, never expose to client. → `schema.sql` enables RLS without anon policies; the key only lives in `.env` (gitignored).
7. **Twilio sandbox 24h window.** Free-form replies only within 24h of the user's last message. Proactive 7am nudges require a Twilio-approved template. → Deferred to FastAPI mode.
8. **External-managed Python on Ubuntu 24.04.** ALWAYS activate a venv before pip. → uv handles its own venv (`.venv/`); no system pip is touched.
9. **Date defaults must use Mexico_City timezone.** VPS is UTC; without timezone-aware defaults, meals logged after 6pm CST get attributed to the wrong day. → `schema.sql` and runtime tools (`zoneinfo`) both handle this.

## What NOT to do

- Don't add LangChain memory abstractions (the checkpointer handles state).
- Don't expose the Supabase MCP in the agent's tool set.
- Don't use Anthropic OAuth via Pro/Max subscription (banned April 4 2026).
- Don't add `reasoning_effort` to OpenAI calls with function tools on /v1/chat/completions.
- Don't put feature logic in `server/app.py` — keep it as a thin Twilio adapter that calls the graph.

---

## Deployment

Two run modes, same graph. The `agent.graph:graph` symbol is the single entry point — both modes import it.

### Mode 1 — `langgraph dev` (current default)

What you get out of this scaffold. Best for iteration and visual debugging.

```bash
cp .env.example .env   # then fill in keys
uv sync
uv run langgraph dev
```

- Server listens on `http://127.0.0.1:2024`.
- One process, one port. Many concurrent clients on that port (it's a normal HTTP server).
- Studio UI: <https://smith.langchain.com/studio/?baseUrl=http://127.0.0.1:2024> — chat, watch tool calls, time-travel.
- In-memory checkpointer. **Conversation state is lost on restart.** Fine while iterating.
- Custom port: `uv run langgraph dev --port 9000`.
- Bind to all interfaces: `uv run langgraph dev --host 0.0.0.0 --port 2024`.
- Safari users: add `--tunnel`.

If you genuinely want two independent servers (staging vs prod-like), launch two processes with different `--port` values. Each gets its own in-memory checkpointer.

### Mode 2 — FastAPI container (Stage 3, when wiring Twilio)

Long-running process, SQLite-persisted checkpoints, runs in a container behind a reverse proxy. Production path for a Twilio bot.

```python
# server/app.py (added later, not in this scaffold)
from fastapi import FastAPI, Form
from langgraph.checkpoint.sqlite import SqliteSaver

from agent.graph import graph as base_graph

checkpointer = SqliteSaver.from_conn_string("checkpoint.db")
graph = base_graph.with_config(configurable={"checkpointer": checkpointer})

app = FastAPI()


@app.post("/twilio/whatsapp")
async def twilio_webhook(From: str = Form(...), Body: str = Form(...)):
    # ... call graph.invoke({"messages": [...]}, config={"configurable": {"thread_id": From}})
    # ... wrap reply in TwiML, escape & < > before stuffing into <Message>
    ...
```

Run:
```bash
uv run uvicorn main:app --host 0.0.0.0 --port 8000
```

Container:
```dockerfile
FROM python:3.12-slim
RUN pip install -U uv
WORKDIR /app
COPY pyproject.toml ./
RUN uv sync --no-dev
COPY . .
CMD ["uv", "run", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

Mount a volume so `checkpoint.db` survives restarts:
```bash
docker run -d \
  --env-file .env \
  -p 8000:8000 \
  -v $(pwd)/data:/app/data \
  -e CHECKPOINT_DB=/app/data/checkpoint.db \
  agent
```

Reverse-proxy via Caddy/nginx for HTTPS — Twilio requires it.

### Side by side
Both modes can run on the same host, hitting the same Supabase project. Different ports (2024 vs 8000), same data, same `agent.graph:graph`. Use Studio against `langgraph dev` for visual debugging while the FastAPI process serves real Twilio traffic.

### Forward path (production-grade)
Deferred — the FastAPI + SQLite combo above is plenty for a single-user bot.
- `langgraph build` → Docker image with Postgres-backed checkpointing.
- LangSmith Deployment → managed cloud deployment.

---

## What's intentionally absent

- No FastAPI/Twilio webhook yet — the scaffold ends at `langgraph dev` working end-to-end.
- No on-demand skill loading. `skills/` currently holds only the always-loaded prompt files. Future workouts/progress/meal-planning skills would slot in here, loaded by middleware.
- No user authentication. Single-user bot. The Twilio webhook will gate by sender phone number when added.
- No web research tool. Adding one is explicitly opt-in (see CATALOG rule #5).
