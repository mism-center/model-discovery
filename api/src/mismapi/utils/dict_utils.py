from collections.abc import Mapping


def get_string_or_empty_from_dict(mapping: Mapping[str, object], key: str) -> str:
    """Return mapping[key] when it is a str; otherwise return "" (including missing key)."""
    if key not in mapping:
        return ""
    value = mapping[key]
    return value if isinstance(value, str) else ""
