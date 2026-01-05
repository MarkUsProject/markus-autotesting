"""Helper functions for defining tester schemas."""

from __future__ import annotations

from markus_autotesting_core.types import BaseTesterSettings
import msgspec


def generate_schema(tester_class: type[BaseTesterSettings]) -> tuple[dict, list]:
    """Generate a schema for a given tester class. This handles common post-processing for all tester classes.

    Returns a schema and list of definitions used by the schema.
    """
    _, components = msgspec.json.schema_components([tester_class])
    tester_component = components[tester_class.__name__]
    tester_name = tester_component["title"].removesuffix("TesterSettings")

    # Modify tester title
    tester_component["title"] = tester_name
    tester_component["properties"]["tester_type"]["default"] = tester_name.removesuffix("TesterSettings").lower()

    # Remove private schema properties
    del tester_component["properties"]["_env"]

    return tester_component, components
