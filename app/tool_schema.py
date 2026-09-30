"""Strict, extensible tool contract validation."""
from dataclasses import dataclass, field
from typing import Any, Dict, Mapping


class ToolSchemaError(ValueError):
    """Raised when tool arguments do not match a registered schema."""


@dataclass(frozen=True)
class ToolSchema:
    required: tuple = ()
    optional: tuple = ()
    types: Dict[str, tuple] = None
    enums: Dict[str, tuple] = field(default_factory=dict)
    nested: Dict[str, "ToolSchema"] = field(default_factory=dict)

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
        for key, choices in self.enums.items():
            if key in arguments and arguments[key] not in choices:
                raise ToolSchemaError(f"Argument '{key}' has an invalid value.")
        for key, schema in self.nested.items():
            if key in arguments:
                schema.validate(arguments[key])
        return True

    def to_dict(self):
        return {
            "required": list(self.required),
            "optional": list(self.optional),
            "types": {key: [t.__name__ for t in value] if isinstance(value, tuple) else [value.__name__] for key, value in (self.types or {}).items()},
            "enums": {key: list(value) for key, value in self.enums.items()},
            "nested": {key: schema.to_dict() for key, schema in self.nested.items()},
        }
