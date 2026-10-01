"""Personal Intelligence Layer.

Combines identity, memory, mode, workspace and safety context into one
deterministic profile that can be supplied to any model/provider.
"""

from .identity import profile


class PersonalIntelligence:
    def __init__(self, memory, workspace, tools, skills):
        self.memory = memory
        self.workspace = workspace
        self.tools = tools
        self.skills = skills

    def build(self, request, mode="general"):
        request = str(request).strip()
        memories = self.memory.search(request, limit=8)
        important = self.memory.important(limit=6)
        recent = self.memory.recent(limit=5)
        skill_instructions = self.skills.instructions_for(request)
        return {
            **profile(mode),
            "request": request,
            "memory": {
                "relevant": memories,
                "important": important,
                "recent": recent,
            },
            "skills": {
                "catalog": self.skills.catalog(),
                "instructions": skill_instructions,
            },
            "tools": self.tools.describe(),
            "workspace_root": str(self.workspace.root),
            "principles": [
                "Prefer small observable steps.",
                "Use tools when the user asks for an action.",
                "Treat tool output as evidence.",
                "Protected actions require approval.",
                "Do not store secrets in memory.",
                "Do not expose provider routing as the product identity.",
            ],
        }

    @staticmethod
    def system_prompt():
        return (
            "You are Hariom AI, a personal AI assistant and computer/workspace agent. "
            "Reply only in English or Hinglish and match the user's input language. "
            "Do not use Devanagari Hindi unless explicitly requested. "
            "Be direct, practical, personalized and objective. "
            "Use the supplied personal intelligence context as authoritative for this session. "
            "Never claim an action happened unless tool output and verification support it. "
            "Do not expose internal provider routing unless relevant to the user's request."
        )
