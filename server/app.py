"""FastAPI entry point — Twilio WhatsApp webhook + agent + persistent checkpoints.

Run: `uv run uvicorn server.app:app --host 0.0.0.0 --port 8000`
"""

import logging
import os
import sqlite3
from datetime import datetime
from html import escape
from time import time
from zoneinfo import ZoneInfo

from dotenv import load_dotenv
from fastapi import FastAPI, Form, HTTPException, Request
from fastapi.responses import Response
from langchain_core.messages import HumanMessage
from langgraph.checkpoint.sqlite import SqliteSaver
from twilio.request_validator import RequestValidator

from agent.graph import make_graph

load_dotenv()
logger = logging.getLogger("server")
TZ = ZoneInfo("America/Mexico_City")

CHECKPOINT_DB = os.getenv("CHECKPOINT_DB", "checkpoint.db")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN", "")

# check_same_thread=False because uvicorn handlers cross threads.
_conn = sqlite3.connect(CHECKPOINT_DB, check_same_thread=False)
_graph = make_graph(checkpointer=SqliteSaver(_conn))
_validator = RequestValidator(TWILIO_AUTH_TOKEN) if TWILIO_AUTH_TOKEN else None

app = FastAPI(title="agent-server")


@app.get("/health")
async def health():
    return {"ok": True}


def _twiml(body: str) -> Response:
    """Wrap text in TwiML <Message>, escaping & < > so Twilio doesn't drop it."""
    xml = f"<?xml version='1.0' encoding='UTF-8'?><Response><Message>{escape(body)}</Message></Response>"
    return Response(content=xml, media_type="application/xml")


async def _validate(request: Request) -> None:
    """Reject unsigned requests in prod. Skipped if TWILIO_AUTH_TOKEN is empty (local dev)."""
    if _validator is None:
        return
    sig = request.headers.get("X-Twilio-Signature", "")
    form = dict(await request.form())
    if not _validator.validate(str(request.url), form, sig):
        raise HTTPException(status_code=403, detail="invalid Twilio signature")


@app.post("/twilio/whatsapp")
async def twilio_whatsapp(request: Request, From: str = Form(...), Body: str = Form(...)):
    await _validate(request)

    # Per-day-per-sender thread bounds context cost and isolates conversations.
    today = datetime.now(TZ).date().isoformat()
    thread_id = f"{From}-{today}"
    config = {"configurable": {"thread_id": thread_id}}

    try:
        result = _graph.invoke({"messages": [HumanMessage(content=Body)]}, config=config)
    except Exception as exc:
        msg = str(exc)
        # Gotcha #4: a dangling tool_call_id corrupts the thread; retry with a salted id.
        if "tool_call" in msg:
            logger.warning("poisoned thread, retrying with salt: %s", thread_id)
            salted = f"{thread_id}-{int(time())}"
            try:
                result = _graph.invoke(
                    {"messages": [HumanMessage(content=Body)]},
                    config={"configurable": {"thread_id": salted}},
                )
            except Exception:
                logger.exception("retry also failed")
                return _twiml("hubo un error procesando tu mensaje, intenta de nuevo")
        else:
            logger.exception("graph invoke failed")
            return _twiml("hubo un error procesando tu mensaje, intenta de nuevo")

    reply = ""
    for m in reversed(result["messages"]):
        if getattr(m, "type", None) == "ai" and m.content:
            reply = m.content if isinstance(m.content, str) else str(m.content)
            break
    return _twiml(reply or "(sin respuesta)")
