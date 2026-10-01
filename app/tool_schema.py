"""Strict, extensible validation for tool input contracts."""

from dataclasses import dataclass, field
from typing import Any, Dict


class ToolSchemaError(ValueError):
    """Raised when tool arguments do not match a registered schema."""


@dataclass(frozen=True)
class ToolSchema:
    required: tuple = ()
    optional: tuple = ()
    types: Dict[str, tuple] = None
    enums: Dict[str, tuple] = field(default_factory=dict)
    nested: Dict[str, "ToolSchema"] = field(default_factory=dict)
    min_values: Dict[str, Any] = field(default_factory=dict)
    max_values: Dict[str, Any] = field(default_factory=dict)
    min_lengths: Dict[str, int] = field(default_factory=dict)
    max_lengths: Dict[str, int] = field(default_factory=dict)

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
            if key not in arguments:
                continue
            value = arguments[key]
            expected_types = expected if isinstance(expected, tuple) else (expected,)
            if not isinstance(value, expected_types):
                raise ToolSchemaError(f"Argument '{key}' has an invalid type.")
            if isinstance(value, bool) and int in expected_types and bool not in expected_types:
                raise ToolSchemaError(f"Argument '{key}' has an invalid type.")
            if bool in expected_types and type(value) is not bool and expected_types == (bool,):
                raise ToolSchemaError(f"Argument '{key}' has an invalid type.")
            if key in self.enums and value not in self.enums[key]:
                raise ToolSchemaError(f"Argument '{key}' has an invalid value.")
            if key in self.min_values and value < self.min_values[key]:
                raise ToolSchemaError(f"Argument '{key}' is below the minimum value.")
            if key in self.max_values and value > self.max_values[key]:
                raise ToolSchemaError(f"Argument '{key}' exceeds the maximum value.")
            if key in self.min_lengths and len(value) < self.min_lengths[key]:
                raise ToolSchemaError(f"Argument '{key}' is shorter than the minimum length.")
            if key in self.max_lengths and len(value) > self.max_lengths[key]:
                raise ToolSchemaError(f"Argument '{key}' exceeds the maximum length.")

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
            "types": {
                key: [t.__name__ for t in value] if isinstance(value, tuple)
                else [value.__name__]
                for key, value in (self.types or {}).items()
            },
            "enums": {key: list(value) for key, value in self.enums.items()},
            "nested": {key: schema.to_dict() for key, schema in self.nested.items()},
            "min_values": dict(self.min_values),
            "max_values": dict(self.max_values),
            "min_lengths": dict(self.min_lengths),
            "max_lengths": dict(self.max_lengths),
        }
