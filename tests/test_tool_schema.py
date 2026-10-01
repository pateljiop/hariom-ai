import unittest

from app.tool_schema import ToolSchema, ToolSchemaError


class ToolSchemaTests(unittest.TestCase):
    def test_required_unknown_and_type_validation(self):
        schema = ToolSchema(required=("name",), optional=("count",), types={"name": (str,), "count": (int,)})
        with self.assertRaises(ToolSchemaError):
            schema.validate({})
        with self.assertRaises(ToolSchemaError):
            schema.validate({"name": "x", "extra": True})
        with self.assertRaises(ToolSchemaError):
            schema.validate({"name": 123})
        self.assertTrue(schema.validate({"name": "x", "count": 2}))

    def test_constraints_and_enum(self):
        schema = ToolSchema(
            required=("mode", "count"),
            types={"mode": (str,), "count": (int,)},
            enums={"mode": ("safe", "fast")},
            min_values={"count": 1},
            max_values={"count": 3},
            min_lengths={"mode": 4},
            max_lengths={"mode": 5},
        )
        self.assertTrue(schema.validate({"mode": "safe", "count": 2}))
        for payload in (
            {"mode": "other", "count": 2},
            {"mode": "safe", "count": 0},
            {"mode": "safe", "count": 4},
            {"mode": "x", "count": 2},
        ):
            with self.assertRaises(ToolSchemaError):
                schema.validate(payload)

    def test_bool_is_not_accepted_as_integer(self):
        schema = ToolSchema(required=("count",), types={"count": (int,)})
        with self.assertRaises(ToolSchemaError):
            schema.validate({"count": True})
