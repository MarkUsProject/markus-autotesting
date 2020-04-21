import os
import json
import glob
import autotester
from jsonschema import Draft7Validator, validators, ValidationError
from jsonschema.exceptions import best_match
from copy import deepcopy
from typing import Type, Generator, Dict, Union, List

ValidatorType = type(Draft7Validator)


def _extend_with_default(
    validator_class: Type[ValidatorType] = Draft7Validator,
) -> ValidatorType:
    """
    Extends a validator class to add defaults before validation.
    From: https://github.com/Julian/jsonschema/blob/master/docs/faq.rst
    """
    validate_props = validator_class.VALIDATORS["properties"]
    validate_array = validator_class.VALIDATORS["items"]

    def _set_defaults(
        validator: ValidatorType,
        properties: Dict,
        instance: Union[Dict, List],
        schema: Dict,
    ) -> Generator[BaseException, None, None]:
        """ Set defaults within a "properties" context """
        if not validator.is_type(instance, "object"):
            return
        for prop, subschema in properties.items():
            if instance.get(prop) is None:
                if "default" in subschema:
                    default_val = subschema["default"]
                elif subschema.get("type") == "array":
                    default_val = []
                elif subschema.get("type") == "object":
                    default_val = {}
                else:
                    continue
                instance[prop] = default_val

        for error in validate_props(validator, properties, instance, schema):
            yield error

    def _set_array_defaults(
        validator: ValidatorType, properties: Dict, instance: List, schema: Dict
    ) -> Generator[ValidationError, None, None]:
        """ Set defaults within an "array" context """
        if not validator.is_type(instance, "array"):
            return

        if not instance:
            default_val = None
            if "default" in properties:
                default_val = properties["default"]
            elif properties.get("type") == "array":
                default_val = []
            elif properties.get("type") == "object":
                default_val = {}
            if default_val is not None:
                instance.append(default_val)
        for error in validate_array(validator, properties, instance, schema):
            yield error

    def _set_oneof_defaults(
        validator: ValidatorType, properties: Dict, instance: Dict, schema: Dict
    ) -> Generator[ValidationError, None, None]:
        """ 
        Set defaults within a "oneOf" context. This ensures that only
        defaults from the matching subschema are set on the instance.

        TODO: If we ever use other optional subschema contexts (ex: allOf, anyOf)
              then we should implement custom validator functions for those as 
              well.
        """

        good_properties = []
        all_errors = []
        good_instance = None

        for i, subschema in enumerate(properties):
            new_instance = deepcopy(instance)
            # first time to fill in defaults since validating 'required', 'minProperties',
            # etc. can't be done until the instance has been properly filled with defaults.
            list(validator.descend(new_instance, subschema, schema_path=i))
            errs = list(validator.descend(new_instance, subschema, schema_path=i))
            if errs:
                all_errors.extend(errs)
            else:
                good_properties.append(subschema)
                good_instance = new_instance

        if len(good_properties) == 0:
            msg = f"{instance} is not valid under any of the given schemas"
            yield ValidationError(msg, context=all_errors)
        elif len(good_properties) > 1:
            msg = f'{instance} is valid under each of {", ".join(repr(p) for p in good_properties)}'
            yield ValidationError(msg)
        else:
            instance.clear()
            instance.update(good_instance)

    custom_validators = {
        "properties": _set_defaults,
        "items": _set_array_defaults,
        "oneOf": _set_oneof_defaults,
    }

    return validators.extend(validator_class, custom_validators)


def _validate_with_defaults(
    schema: Dict,
    obj: Union[Dict, List],
    validator_class: ValidatorType = Draft7Validator,
    best_only: bool = True,
) -> Union[ValidationError, List[ValidationError]]:
    """
    Return an iterator that yields errors from validating obj on schema 
    after first filling in defaults on obj.
    """
    validator = _extend_with_default(validator_class)(schema)
    # first time to fill in defaults since validating 'required', 'minProperties',
    # etc. can't be done until the instance has been properly filled with defaults.
    list(validator.iter_errors(obj))
    errors = list(validator.iter_errors(obj))
    if best_only:
        return best_match(errors)
    return errors


def get_schema() -> Dict:
    package_root = autotester.__path__[0]

    with open(os.path.join(package_root, "lib", "tester_schema_skeleton.json")) as f:
        schema_skeleton = json.load(f)

    glob_pattern = os.path.join(package_root, "testers", "*", "specs", ".installed")
    for path in sorted(glob.glob(glob_pattern)):
        tester_type = os.path.basename(os.path.dirname(os.path.dirname(path)))
        specs_dir = os.path.dirname(path)
        with open(os.path.join(specs_dir, "settings_schema.json")) as f:
            tester_schema = json.load(f)

        schema_skeleton["definitions"]["installed_testers"]["enum"].append(tester_type)
        schema_skeleton["definitions"]["tester_schemas"]["oneOf"].append(tester_schema)

    return schema_skeleton


def validate_against_schema(test_specs: Dict, filenames: List[str]) -> None:
    """
    Check if test_specs is valid according to the schema from calling get_schema.
    Raise an error if it is not valid.
    """
    schema = get_schema()
    if schema is not None:
        schema["definitions"]["files_list"]["enum"] = filenames
        # don't validate based on categories
        schema["definitions"]["test_data_categories"].pop("enum")
        schema["definitions"]["test_data_categories"].pop("enumNames")
        error = _validate_with_defaults(schema, test_specs, best_only=True)
        if error:
            raise error
