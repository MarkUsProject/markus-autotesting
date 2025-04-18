import sys
from testers.specs import TestSpecs
import json

resource_settings = json.loads(sys.stdin.readline().strip())["resource_settings"]

specs = TestSpecs.from_json(sys.stdin.read())
tester_type = specs["tester_type"]

imported_module = __import__(
    f"testers.{tester_type}.{tester_type}_tester", fromlist=[f"{tester_type.capitalize()}Tester"]
)

Tester = getattr(imported_module, f"{tester_type.capitalize()}Tester")
Tester(resource_settings=resource_settings, specs=specs).run()
