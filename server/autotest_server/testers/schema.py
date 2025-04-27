from .models import TesterType
import msgspec


def get_schema(testers: list[TesterType], tester_settings: dict[TesterType, dict]) -> dict:
    """Get the schema for the tester"""
    schema = {
        "$defs": {},
        "properties": {
            "testers": {
                "title": "Testers",
                "type": "array",
                "items": {
                    "anyOf": [{"$ref": f"#/$defs/{t.get_schema_type().__name__}"} for t in testers],
                    "discriminator": {
                        "propertyName": "tester_type",
                        "mapping": {
                            t.get_schema_type().__name__: f"#/$defs/{t.get_schema_type().__name__}" for t in testers
                        },
                    },
                },
                "minItems": 1,
            },
        },
        "required": ["testers"],
        "type": "object",
    }

    for t in testers:
        schema["$defs"].update(**msgspec.json.schema(t.get_schema_type())["$defs"])
        schema["$defs"][t.get_schema_type().__name__].update({"title": t.value})

    return schema
