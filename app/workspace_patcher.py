"""Safe text patching within the configured workspace."""
from dataclasses import dataclass

from .workspace import Workspace


class PatchError(Exception):
    """Base error for invalid or unsafe patches."""


@dataclass(frozen=True)
class TextPatch:
    path: str
    old: str
    new: str
    expected_count: int = 1


class WorkspacePatcher:
    def __init__(self, workspace=None):
        self.workspace = workspace or Workspace()

    def apply(self, patch: TextPatch):
        if not isinstance(patch, TextPatch):
            raise PatchError("A TextPatch is required.")
        if patch.expected_count < 1:
            raise PatchError("expected_count must be at least 1.")
        content = self.workspace.read_file(patch.path)
        count = content.count(patch.old)
        if count != patch.expected_count:
            raise PatchError(f"Patch matched {count} occurrences; expected {patch.expected_count}.")
        updated = content.replace(patch.old, patch.new)
        self.workspace.write_file(patch.path, updated)
        return {"path": patch.path, "replacements": count}

    def apply_many(self, patches):
        if patches is None:
            raise PatchError("Patches are required.")
        results = []
        for patch in patches:
            results.append(self.apply(patch))
        return results
