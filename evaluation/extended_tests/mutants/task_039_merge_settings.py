# Wrong on purpose: a None override removes the key only at the top level;
# in nested dictionaries the key is kept with the value None.
import copy


def merge_settings(defaults, overrides, top=True):
    result = copy.deepcopy(defaults)
    for key, value in overrides.items():
        if value is None and top:
            result.pop(key, None)
        elif isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = merge_settings(result[key], value, top=False)
        else:
            result[key] = copy.deepcopy(value)
    return result
