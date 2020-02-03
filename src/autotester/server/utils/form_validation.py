from jsonschema import Draft7Validator, validators, ValidationError
from jsonschema.exceptions import best_match
from copy import deepcopy

def extend_with_default(validator_class=Draft7Validator):
    """
    Extends a validator class to add defaults before validation.
    From: https://github.com/Julian/jsonschema/blob/master/docs/faq.rst
    """
    validate_props = validator_class.VALIDATORS["properties"]
    validate_array = validator_class.VALIDATORS["items"]

    def set_defaults(validator, properties, instance, schema):
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

    def set_array_defaults(validator, properties, instance, schema):
        """ Set defaults within an "array" context """
        if not validator.is_type(instance, "array"):
            return
        
        if not instance:
            default_val = None
            if "default" in properties:
                default_val = properties['default']
            elif properties.get("type") == "array":
                default_val = []
            elif properties.get("type") == "object":
                default_val = {}
            if default_val is not None:
                instance.append(default_val)
        for error in validate_array(validator, properties, instance, schema):
            yield error

    def set_oneOf_defaults(validator, properties, instance, schema):
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
            msg = f'{instance} is not valid under any of the given schemas'
            yield ValidationError(msg, context=all_errors)
        elif len(good_properties) > 1:
            msg = f'{instance} is valid under each of {", ".join(repr(p) for p in good_properties)}'
            yield ValidationError(msg)
        else:
            instance.clear()
            instance.update(good_instance)

    custom_validators = {"properties": set_defaults,
                         "items": set_array_defaults,
                         "oneOf": set_oneOf_defaults}

    return validators.extend(validator_class, custom_validators)

def validate_with_defaults(schema, obj, validator_class=Draft7Validator, best_only=True):
    """
    Return an iterator that yields errors from validating obj on schema 
    after first filling in defaults on obj.
    """
    validator = extend_with_default(validator_class)(schema)
    # first time to fill in defaults since validating 'required', 'minProperties',
    # etc. can't be done until the instance has been properly filled with defaults.
    list(validator.iter_errors(obj))
    errors = list(validator.iter_errors(obj))
    if best_only:
        return best_match(errors)
    return errors

def is_valid(obj, schema, validator_class=Draft7Validator):
    """
    Return True if <obj> is valid for schema <schema> using the
    validator <validator_class>.
    """
    return validator_class(schema).is_valid(obj)
