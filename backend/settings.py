"""Model, limits, and paths for the Campus Customs agent team.

Everything that controls cost lives here, in one place, so the token budget can
be read and changed without going through the agent code.

Why these numbers: five agents that can delegate to each other will spend tokens
far faster than a single assistant, and the expensive part of a reasoning model
is the reasoning, not the prose. So the model runs at **low** reasoning effort
with **low** verbosity, every agent has a hard ceiling on model requests, and the
delegation graph is capped by depth and by total hand-offs per ticket. A run that
hits a limit stops and says so; it does not quietly keep going.
"""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
DB_PATH = ROOT / "data" / "campus_customs_new.db"
ORIGINAL_DB_PATH = ROOT / "data" / "campus_customs.db"
MCP_DIR = ROOT / "mcp_server"
PROMPT_DIR = HERE / "prompts"
AUDIT_PATH = ROOT / "output" / "audit_trail.json"


def _load_env() -> None:
    """Load the first .env found walking up from this file."""
    here = Path(__file__).resolve()
    for folder in (here.parent, *here.parents):
        candidate = folder / ".env"
        if candidate.exists():
            load_dotenv(candidate)
            return


_load_env()

# --- model -----------------------------------------------------------------

# Only the gpt-6 family is allowed for this homework. `gpt-6-luna` is the model;
# there is no smaller variant of it on the gateway, so the saving comes from the
# settings below rather than from a different model id.
MODEL_NAME = os.getenv("MODEL_NAME", "gpt-6-luna").strip() or "gpt-6-luna"
PORTKEY_BASE_URL = os.getenv("PORTKEY_BASE_URL", "https://api.portkey.ai/v1").rstrip("/")

# The single biggest lever. Reasoning tokens are charged as output and are
# invisible in the reply; at "low" a simple shop question costs near zero of them.
REASONING_EFFORT = "low"
# Agents report; they do not write essays. Keeps replies short without a prompt
# having to beg for brevity.
VERBOSITY = "low"

# --- per-agent limits ------------------------------------------------------

# A model request is one round trip. A specialist that needs more than four has
# usually lost the thread rather than found something.
MAX_REQUESTS_SPECIALIST = 4
# The boss reads the ticket, delegates, and decides, so it needs a little more.
MAX_REQUESTS_BOSS = 8
# Hard ceiling on output tokens per agent turn, so one runaway reply cannot
# dominate the bill.
MAX_OUTPUT_TOKENS = 1200

# --- delegation limits -----------------------------------------------------

# The boss is depth 0. A specialist it calls is depth 1. That specialist may ask
# one other specialist (depth 2) and no further, which is what stops a mesh of
# five agents from calling each other indefinitely.
MAX_DELEGATION_DEPTH = 2
# Total hand-offs allowed while resolving one ticket, across every agent.
MAX_DELEGATIONS_PER_TICKET = 6

# --- audit -----------------------------------------------------------------

AUDIT_ARG_CHARS = 200
AUDIT_RESULT_CHARS = 400
AUDIT_TEXT_CHARS = 600
