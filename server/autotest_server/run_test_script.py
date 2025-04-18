import sys
from testers.specs import TestSpecs
import json

# Read the tester_type first (assuming it's one line)
tester_type = sys.stdin.readline().strip()

# Then read the resource settings as JSON
resource_settings = json.loads(sys.stdin.readline().strip())["resource_settings"]

# Then read the rest as JSON specs
specs_json = sys.stdin.read()

imported_module = __import__(
    f"testers.{tester_type}.{tester_type}_tester", fromlist=[f"{tester_type.capitalize()}Tester"]
)

Tester = getattr(imported_module, f"{tester_type.capitalize()}Tester")

Tester(resource_settings=resource_settings, specs=TestSpecs.from_json(specs_json)).run()
