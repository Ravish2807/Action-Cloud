"""LLM-backed routing from a task description to an ActionCloud agent role."""
from __future__ import annotations

import json
import logging
import re
from typing import Any

from ..llm import LLM, get_llm
from ..schema import AgentRole

log = logging.getLogger(__name__)


class CoordinatorAgent:
    """Select an implemented role and provide a short rationale."""

    def __init__(self, llm: LLM | None = None) -> None:
        self.llm = llm or get_llm()

    def assign(self, task: str) -> dict[str, Any]:
        roles = ", ".join(role.value for role in AgentRole)
        response = self.llm.complete(
            f"Choose the best role for this task. Return JSON only with keys role and reason.\n"
            f"Allowed roles: {roles}\nTask: {task}",
            system="You route tasks to specialized agents. Never invent a role.",
        )
        try:
            raw = response.text.strip()
            raw = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw)
            data = json.loads(raw)
            role = AgentRole(data["role"])
            reason = str(data.get("reason", ""))[:500]
            return {"role": role, "reason": reason}
        except (ValueError, KeyError, TypeError, json.JSONDecodeError):
            log.warning("Coordinator returned an invalid role; applying deterministic task routing")
            text = task.lower()
            role = (AgentRole.TESTING if any(x in text for x in ("test", "verify", "assert"))
                    else AgentRole.CODING if any(x in text for x in ("code", "implement", "write", "fix"))
                    else AgentRole.DOCUMENTATION if any(x in text for x in ("document", "readme", "explain"))
                    else AgentRole.RESEARCH)
            return {"role": role, "reason": "Deterministic fallback after invalid coordinator output"}
