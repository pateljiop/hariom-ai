from dataclasses import dataclass
from pathlib import Path


@dataclass
class Skill:
    name: str
    description: str
    instructions: str


class SkillRegistry:
    """Local, file-backed skills loaded only when relevant."""

    def __init__(self, root):
        self.root = Path(root)
        self.skills = {}
        self.reload()

    def reload(self):
        self.skills = {}
        if not self.root.exists():
            return
        for path in sorted(self.root.glob("*/SKILL.md")):
            text = path.read_text(encoding="utf-8", errors="replace")
            name = path.parent.name
            description = ""
            for line in text.splitlines():
                if line.lower().startswith("description:"):
                    description = line.split(":", 1)[1].strip()
                    break
            self.skills[name] = Skill(name, description or name, text)

    def catalog(self):
        return [{"name": s.name, "description": s.description} for s in self.skills.values()]

    def relevant(self, request, limit=3):
        words = {w.lower() for w in request.split() if len(w) > 2}
        scored = []
        for skill in self.skills.values():
            haystack = (skill.name + " " + skill.description).lower()
            score = sum(1 for word in words if word in haystack)
            if score:
                scored.append((score, skill))
        scored.sort(key=lambda item: (-item[0], item[1].name))
        return [skill for _, skill in scored[:limit]]

    def instructions_for(self, request):
        return [skill.instructions for skill in self.relevant(request)]
