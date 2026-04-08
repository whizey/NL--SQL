"""
vanna_setup.py
Groq as primary LLM, Ollama as automatic rate-limit fallback.
"""

import os
from dotenv import load_dotenv

load_dotenv()

# ── Vanna imports ────────────────────────────────────────────────────────────
from vanna import Agent, AgentConfig
from vanna.core.registry import ToolRegistry
from vanna.core.user import UserResolver, User, RequestContext
from vanna.tools import RunSqlTool, VisualizeDataTool
from vanna.tools.agent_memory import (
    SaveQuestionToolArgsTool,
    SearchSavedCorrectToolUsesTool,
)
from vanna.integrations.sqlite import SqliteRunner
from vanna.integrations.local.agent_memory import DemoAgentMemory
from vanna.integrations.openai import OpenAILlmService

# ── Config ───────────────────────────────────────────────────────────────────
DB_PATH      = os.getenv("DB_PATH", "./clinic.db")
GROQ_MODEL   = "llama-3.3-70b-versatile"
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.1:8b")
OLLAMA_URL   = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434/v1")


# ── LLM builders ─────────────────────────────────────────────────────────────
def build_llm():
    """Primary: Groq."""
    groq_key = os.getenv("GROQ_API_KEY")
    if not groq_key:
        raise ValueError(
            "❌ GROQ_API_KEY not found.\n"
            "Add GROQ_API_KEY=your_key to your .env file."
        )
    print("✅ Primary LLM: Groq (llama-3.3-70b-versatile)")
    return OpenAILlmService(
        api_key=groq_key,
        model=GROQ_MODEL,
        base_url="https://api.groq.com/openai/v1",
    )


def build_ollama_client():
    """
    Returns a raw OpenAI-compatible client pointed at local Ollama.
    Used directly in main.py for the fallback call — NOT wrapped in
    OpenAILlmService so we keep full control over the retry logic.
    """
    from openai import OpenAI
    print(f"✅ Fallback LLM: Ollama ({OLLAMA_MODEL}) at {OLLAMA_URL}")
    return OpenAI(
        api_key="ollama",   # Ollama ignores this; openai SDK requires a value
        base_url=OLLAMA_URL,
    )


# ── User Resolver ─────────────────────────────────────────────────────────────
class DefaultUserResolver(UserResolver):
    async def resolve_user(self, request_context: RequestContext) -> User:
        return User(
            id="default-user",
            email="user@clinic.local",
            group_memberships=["users"],
        )


# ── Build Agent ───────────────────────────────────────────────────────────────
def build_agent() -> Agent:
    llm          = build_llm()
    agent_memory = DemoAgentMemory(max_items=1000)
    sql_runner   = SqliteRunner(database_path=DB_PATH)
    db_tool      = RunSqlTool(sql_runner=sql_runner)
    tools        = ToolRegistry()

    tools.register_local_tool(db_tool,                          access_groups=["users"])
    tools.register_local_tool(VisualizeDataTool(),              access_groups=["users"])
    tools.register_local_tool(SaveQuestionToolArgsTool(),       access_groups=["users"])
    tools.register_local_tool(SearchSavedCorrectToolUsesTool(), access_groups=["users"])

    agent = Agent(
        llm_service=llm,
        tool_registry=tools,
        user_resolver=DefaultUserResolver(),
        agent_memory=agent_memory,
        config=AgentConfig(),
    )
    print("✅ Vanna Agent ready")
    return agent


# ── Singletons ────────────────────────────────────────────────────────────────
agent         = build_agent()
