# from typing import Any, get_args, get_origin, Annotated, List, Dict, Union, Optional
# from .models import TesterType, CustomTestSpecs, CustomTesterSchema, PyTesterSchema, PyTestSpecs
# import msgspec
# import json


# def get_schema(testers: list[TesterType], tester_settings: dict[TesterType, dict]) -> dict:
#     """Get the schema for the tester"""
#     schema = {
#         "$defs": {},
#         "properties": {
#             "testers": {
#                 "title": "Testers",
#                 "type": "array",
#                 "items": {
#                     "anyOf": [{"$ref": f"#/$defs/{t.get_schema_type().__name__}"} for t in testers],
#                     "discriminator": {
#                         "propertyName": "tester_type",
#                         "mapping": {
#                             t.get_schema_type().__name__: f"#/$defs/{t.get_schema_type().__name__}" for t in testers
#                         },
#                     },
#                 },
#                 "minItems": 1,
#             },
#         },
#         "required": ["testers"],
#         "type": "object",
#     }
#
#     for t in testers:
#         schema["$defs"].update(**msgspec.json.schema(t.get_schema_type())["$defs"])
#         schema["$defs"][t.get_schema_type().__name__].update({"title": t.value})
#
#     return schema


# Schema generation for CustomTesterSchema that matches the old one
# t = CustomTesterSchema
# st = CustomTestSpecs
# sc = msgspec.json.schema(t)
# del sc["$ref"]
# sc = sc["$defs"]
# sc = sc[list(sc.keys())[0]]
# del sc["title"]
# del sc["additionalProperties"]
# del sc["required"]
# sc["properties"]["tester_type"]["type"] = "string"
#
# del sc["properties"]["test_data"]["items"]["$ref"]
# cts = msgspec.json.schema(st)
#
# sc["properties"]["test_data"]["items"] = cts["$defs"][list(cts["$defs"].keys())[0]]
# cts = sc["properties"]["test_data"]["items"]
# del cts["title"]

# t = PyTesterSchema
# st = PyTestSpecs
# sc = msgspec.json.schema(t)
# del sc["$ref"]
# sc = sc["$defs"]
# sc = sc[list(sc.keys())[0]]
# del sc["title"]
# del sc["additionalProperties"]
# del sc["required"]
# sc["properties"]["tester_type"]["type"] = "string"
#
# del sc["properties"]["env_data"]["$ref"]
# cts = msgspec.json.schema()
#
# sc["properties"]["test_data"]["items"] = cts["$defs"][list(cts["$defs"].keys())[0]]
# cts = sc["properties"]["test_data"]["items"]
# del cts["title"]

# class A(msgspec.Struct):
#     abc: str
#
# class B(A):
#     b: str
#
# # with open("generated_schema.json", "w") as f:
# #     json.dump(sc, f, indent=2)
# from typing import Any, get_args, get_origin, Annotated, List, Dict, Union
# import inspect
#
# def to_schema(cls: Any) -> dict:
#     """Generate JSON Schema from a Python class."""
#     properties = {}
#     required = []
#
#     # Get fields from msgspec
#     fields = msgspec.structs.fields(cls)
#     for field in fields:
#         print(field)
#         annotation = field.type
#         properties[field.name] = type_to_schema(annotation)
#
#         if field.default is msgspec.NODEFAULT and field.default_factory is msgspec.NODEFAULT:
#             required.append(field.name)
#
#     schema_dict = {
#         "type": "object",
#         "properties": properties,
#     }
#
#     if required:
#         schema_dict["required"] = required
#
#     return schema_dict
#
#
#
#
# def type_to_schema(annotation) -> dict:
#     """Converts Python types to JSON Schema."""
#     # print(annotation)
#     origin = get_origin(annotation)
#     args = get_args(annotation)
#
#     if annotation == str:
#         return {"type": "string"}
#     elif annotation == int:
#         return {"type": "integer"}
#     elif annotation == float:
#         return {"type": "number"}
#     elif annotation == bool:
#         return {"type": "boolean"}
#     elif origin in (list, List):
#         return {"type": "array", "items": type_to_schema(args[0])}
#     elif origin in (dict, Dict):
#         return {
#             "type": "object",
#             "additionalProperties": type_to_schema(args[1]),
#         }
#     elif origin is Union:
#         schemas = [type_to_schema(arg) for arg in args if arg is not type(None)]
#         if len(schemas) == 1:
#             return schemas[0]
#         else:
#             return {"anyOf": schemas}
#     elif origin is Annotated:
#         base_type, *metadata = args
#         schema = type_to_schema(base_type)
#         for meta in metadata:
#             if isinstance(meta, msgspec.Meta):
#                 if meta.title:
#                     schema["title"] = meta.title
#                 if meta.description:
#                     schema["description"] = meta.description
#         return schema
#     elif isinstance(annotation, type) and issubclass(annotation, msgspec.Struct):
#         return sschema(annotation)
#     else:
#         return {"type": "object"}  # fallback generic object


# with open("generated_schema.json", "w") as f:
#     json.dump(sschema(PyTesterSchema), f, indent=2)
# with open("generated_schema.json", "w") as f:
#     json.dump(sschema(PyTesterSchema), f, indent=2)
# sschema(PyTesterSchema)
# sschema(B)
# def replace_refs(schema: dict, defs: dict) -> None:
#     """Replace $ref with the actual schema."""
#     if "$ref" in schema:
#         ref = schema.pop("$ref")
#         ref_schema = defs[ref.split("/")[-1]]
#         if "title" in ref_schema:
#             del ref_schema["title"]
#         schema.update(ref_schema)
#
#     for key, value in schema.items():
#         if isinstance(value, dict):
#             replace_refs(value, defs)
#         elif isinstance(value, list):
#             for item in value:
#                 if isinstance(item, dict):
#                     replace_refs(item, defs)
#     if "$defs" in schema:
#         del schema["$defs"]
#
# base_schema = msgspec.json.schema(PyTesterSchema)
# defs = base_schema["$defs"]
# replace_refs(base_schema, defs)
# # del base_schema["title"]
# del base_schema["additionalProperties"]
# with open("generated_schema.json", "w") as f:
#     json.dump(base_schema, f, indent=2)
