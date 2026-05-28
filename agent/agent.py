import os
import sys
from datetime import date
from dotenv import load_dotenv

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_groq import ChatGroq
from langgraph.prebuilt import create_react_agent

from agent.tools import (
    save_jobs_tool,
    check_gap_friendly_count,
    check_today_stats,
)

load_dotenv()

# ---------------------------------------------------------------------------
# Search terms from PROJECT.md
# ---------------------------------------------------------------------------

PRIMARY_TERMS = [
    "data analyst",
    "business analyst",
    "analytics analyst",
    "MIS analyst",
    "reporting analyst",
    "BI analyst",
]

SECONDARY_TERMS = [
    "data analyst 3 years",
    "data analyst Hyderabad",
    "SQL analyst",
    "Power BI analyst",
    "Tableau analyst",
    "Excel analyst",
    "Python data analyst",
]

GAP_TERMS = [
    "returnship",
    "return to work",
    "career gap welcome",
    "gap candidates welcome",
    "career break accepted",
]

ALL_SEARCH_TERMS = PRIMARY_TERMS + SECONDARY_TERMS + GAP_TERMS

LOCATION = "Hyderabad, India"
SITES = ["linkedin", "indeed", "glassdoor"]

# ---------------------------------------------------------------------------
# System prompt
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = f"""You are a job-scraping agent. Today is {date.today().isoformat()}.

Your goal is to collect today's data analyst jobs in Hyderabad for candidates
with approximately 3 years of experience, including those with a career gap.

## Instructions

1. Call save_jobs_tool for EVERY search term listed below, using:
   - location: "{LOCATION}"
   - sites: {SITES}

   Search terms to cover:
   Primary   : {', '.join(PRIMARY_TERMS)}
   Secondary : {', '.join(SECONDARY_TERMS)}
   Gap-specific: {', '.join(GAP_TERMS)}

2. Prioritise gap-friendly roles — make sure all gap-specific search terms
   are scraped even if earlier calls return zero results.

3. After ALL save_jobs_tool calls are complete, call check_today_stats once
   to retrieve the final summary from the database.

4. Also call check_gap_friendly_count to get the gap-friendly total.

5. Print a final report in this exact format:

   ============================================================
   DAILY JOB SCRAPE REPORT — {date.today().isoformat()}
   ============================================================
   Total jobs saved today  : <number>
   Gap-friendly jobs       : <number>

   Breakdown by job type
     Full-time  : <number>
     Remote     : <number>
     Hybrid     : <number>
     Walk-in    : <number>
   ============================================================

Do not skip any search term. Do not ask for confirmation — execute all steps
autonomously and finish with the report.
"""

# ---------------------------------------------------------------------------
# LLM factory helpers
# ---------------------------------------------------------------------------

def _make_gemini() -> ChatGoogleGenerativeAI:
    api_key = os.getenv("GOOGLE_API_KEY", "AIzaSyBs3frGkE_qB_PX6ghTFZ4u4bCuKtqO8Vk")
    if not api_key:
        raise EnvironmentError("GOOGLE_API_KEY is not set.")
    return ChatGoogleGenerativeAI(
        model="gemini-2.5-flash",
        google_api_key=api_key,
        temperature=0,
    )


def _make_groq() -> ChatGroq:
    api_key = os.getenv("GROQ_API_KEY", "")
    if not api_key:
        raise EnvironmentError("GROQ_API_KEY is not set.")
    return ChatGroq(
        model="llama-3.3-70b-versatile",
        groq_api_key=api_key,
        temperature=0,
    )


# ---------------------------------------------------------------------------
# Agent runner
# ---------------------------------------------------------------------------

TOOLS = [save_jobs_tool, check_gap_friendly_count, check_today_stats]


def _run_with_llm(llm, label: str) -> str:
    """Build a ReAct agent with the given LLM and run the scraping task."""
    print(f"\n[agent] Starting with {label}...")
    agent = create_react_agent(llm, tools=TOOLS)
    result = agent.invoke(
        {
            "messages": [
                SystemMessage(content=SYSTEM_PROMPT),
                HumanMessage(content="Start the daily job scrape now."),
            ]
        }
    )
    # Extract the last AI message as the final answer
    messages = result.get("messages", [])
    for msg in reversed(messages):
        if hasattr(msg, "content") and msg.content:
            return str(msg.content)
    return "(no output)"


def run_agent() -> None:
    """Entry point: try Gemini first, fall back to Groq on any error."""
    # --- Attempt 1: Gemini ---
    try:
        llm = _make_gemini()
        output = _run_with_llm(llm, "Gemini 2.5 Flash")
        print(output)
        return
    except EnvironmentError as env_err:
        print(f"[agent] Gemini skipped — {env_err}", file=sys.stderr)
    except Exception as gemini_err:
        print(
            f"[agent] Gemini failed ({type(gemini_err).__name__}: {gemini_err}). "
            "Falling back to Groq...",
            file=sys.stderr,
        )

    # --- Attempt 2: Groq fallback ---
    try:
        llm = _make_groq()
        output = _run_with_llm(llm, "Groq Llama 3.3 70B")
        print(output)
    except EnvironmentError as env_err:
        print(f"[agent] Groq skipped — {env_err}", file=sys.stderr)
        sys.exit(1)
    except Exception as groq_err:
        print(
            f"[agent] Groq also failed ({type(groq_err).__name__}: {groq_err}). "
            "Aborting.",
            file=sys.stderr,
        )
        sys.exit(1)


if __name__ == "__main__":
    run_agent()
