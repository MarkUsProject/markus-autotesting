from .models import TesterType, CustomTestSpecs, CustomTesterSchema
import msgspec
import json


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


# Schema generation for CustomTesterSchema that matches the old one
t = CustomTesterSchema
st = CustomTestSpecs
sc = msgspec.json.schema(t)
del sc["$ref"]
sc = sc["$defs"]
sc = sc[list(sc.keys())[0]]
del sc["title"]
del sc["additionalProperties"]
del sc["required"]
sc["properties"]["tester_type"]["type"] = "string"

del sc["properties"]["test_data"]["items"]["$ref"]
cts = msgspec.json.schema(st)

sc["properties"]["test_data"]["items"] = cts["$defs"][list(cts["$defs"].keys())[0]]
cts = sc["properties"]["test_data"]["items"]
del cts["title"]

with open("generated_schema.json", "w") as f:
    json.dump(sc, f, indent=2)
