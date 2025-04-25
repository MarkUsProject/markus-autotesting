import sys
import json
import msgspec

# Different parts of data that we need is sent on stdin separated by newlines
tester_type = sys.stdin.readline().strip()
resource_settings = json.loads(sys.stdin.readline().strip())["resource_settings"]
specs_json = sys.stdin.read()

# Dynamically import the models module based on the tester type
models_module = __import__("testers.models", fromlist=[f"{tester_type.capitalize()}TestDatum"])
# This imports an msgspec Struct class used to decode the specs
TestDatum = getattr(models_module, f"{tester_type.capitalize()}TestDatum")
specs = msgspec.json.decode(specs_json, type=TestDatum)


# Dynamically import the tester module based on the tester type
tester_module = __import__(
    f"testers.{tester_type}.{tester_type}_tester", fromlist=[f"{tester_type.capitalize()}Tester"]
)
Tester = getattr(tester_module, f"{tester_type.capitalize()}Tester")

Tester(resource_settings=resource_settings, specs=specs).run()
