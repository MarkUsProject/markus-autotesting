import sys
import msgspec
import importlib

# Different parts of data that we need is sent on stdin separated by newlines
tester_type = sys.stdin.readline().strip()
resource_settings = msgspec.json.decode(sys.stdin.readline().strip())
specs_json = sys.stdin.read()

# Dynamically import the models module based on the tester type
models_module = importlib.import_module("testers.models")
# This imports an msgspec Struct class used to decode the specs
TestSpecs = getattr(models_module, f"{tester_type.capitalize()}TestSpecs")
specs = msgspec.json.decode(specs_json, type=TestSpecs)

# Dynamically import the tester module based on the tester type
tester_module = importlib.import_module(f"testers.{tester_type}.{tester_type}_tester")
Tester = getattr(tester_module, f"{tester_type.capitalize()}Tester")

Tester(resource_settings=resource_settings, specs=specs).run()
