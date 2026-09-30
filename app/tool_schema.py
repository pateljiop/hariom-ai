"""Strict tool argument validation for task plans."""
from dataclasses import dataclass
from typing import Any, Dict


class ToolSchemaError(ValueError):
    """Raised when tool arguments do not match a registered schema."""


@dataclass(frozen=True)
class ToolSchema:
    required: tuple = ()
    optional: tuple = ()
    types: Dict[str, tuple] = None

    def validate(self, arguments):
        if not isinstance(arguments, dict):
            raise ToolSchemaError("Tool arguments must be an object.")
        types = self.types or {}
        allowed = set(self.required) | set(self.optional)
        missing = [key for key in self.required if key not in arguments]
        if missing:
            raise ToolSchemaError(f"Missing required arguments: {', '.join(missing)}")
        unknown = [key for key in arguments if key not in allowed]
        if unknown:
            raise ToolSchemaError(f"Unknown arguments: {', '.join(unknown)}")
        for key, expected in types.items():
            if key in arguments and not isinstance(arguments[key], expected):
                raise ToolSchemaError(f"Argument '{key}' has an invalid type.")
        return True
