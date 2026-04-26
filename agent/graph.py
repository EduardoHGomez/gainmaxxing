from pathlib import Path

from dotenv import load_dotenv
from langchain.agents import create_agent
from langchain_openai import ChatOpenAI

from agent.tools import TOOLS

load_dotenv()

SKILLS_DIR = Path(__file__).resolve().parent.parent / "skills"
SKILL_FILES = ("PROFILE.md", "BEHAVIOR.md", "CATALOG.md")

SYSTEM_PROMPT = "\n\n".join(
    (SKILLS_DIR / name).read_text(encoding="utf-8").strip() for name in SKILL_FILES
)

# Do NOT pass `reasoning_effort` — it breaks function tools on gpt-5.4-mini's chat-completions endpoint.
model = ChatOpenAI(model="gpt-5.4-mini")

# No checkpointer here: langgraph dev provides one in-memory; the server/ entry point binds a SqliteSaver.
graph = create_agent(
    model=model,
    tools=TOOLS,
    system_prompt=SYSTEM_PROMPT,
)
