from pathlib import Path

from dotenv import load_dotenv
from langchain.agents import create_agent
from langchain.agents.middleware import ModelFallbackMiddleware
from langchain.chat_models.base import BaseChatModel
from langchain_anthropic import ChatAnthropic
from langchain_openai import ChatOpenAI

from agent.tools import TOOLS

load_dotenv()

SKILLS_DIR = Path(__file__).resolve().parent.parent / "skills"
SKILL_FILES = ("PROFILE.md", "BEHAVIOR.md", "CATALOG.md")

SYSTEM_PROMPT = "\n\n".join(
    (SKILLS_DIR / name).read_text(encoding="utf-8").strip() for name in SKILL_FILES
)


def build_model() -> BaseChatModel:
    """Primary model. Haiku 4.5 — cheap, fast, warm tone. Swap to claude-sonnet-4-6 or claude-opus-4-7 if you need more."""
    return ChatAnthropic(model="claude-haiku-4-5")


# Fallback chain: if Haiku fails (rate limit, 5xx, provider down), try Sonnet, then OpenAI.
# Triggers only on API errors, not on poor answers. Cross-provider redundancy.
FALLBACK = ModelFallbackMiddleware(
    ChatAnthropic(model="claude-sonnet-4-6"),
    ChatOpenAI(model="gpt-5.4-mini"),
)


# No checkpointer here: langgraph dev provides one in-memory; the server/ entry point binds a SqliteSaver.
graph = create_agent(
    model=build_model(),
    tools=TOOLS,
    system_prompt=SYSTEM_PROMPT,
    middleware=[FALLBACK],
)
