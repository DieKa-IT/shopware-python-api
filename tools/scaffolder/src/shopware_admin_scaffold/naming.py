"""Stable Python identifiers with explicit collision handling."""

import keyword
import re

from shopware_admin import Context, Entity

from . import ScaffoldError

MODEL_RESERVED = {"Entity", "Field", "ToOne", "ToMany", "Any", "datetime"}
FIELD_RESERVED = set(dir(Entity))
SET_RESERVED = set(dir(Context)) | {"context", "registry"}


def snake_case(value: str) -> str:
    value = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1_\2", value)
    value = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", value)
    return re.sub(r"[^a-zA-Z0-9]+", "_", value).strip("_").lower()


def pascal_case(value: str) -> str:
    return "".join(part.capitalize() for part in snake_case(value).split("_"))


def pluralize(value: str) -> str:
    irregular = {"person": "people", "child": "children", "media": "media"}
    if value in irregular:
        return irregular[value]
    if value.endswith("y") and len(value) > 1 and value[-2] not in "aeiou":
        return value[:-1] + "ies"
    if value.endswith(("s", "x", "z", "ch", "sh")):
        return value + "es"
    return value + "s"


def identifier(value: str, label: str, reserved: set[str] | None = None) -> str:
    if (
        not value.isidentifier()
        or not value.isascii()
        or keyword.iskeyword(value)
        or value.startswith("_")
        or value in (reserved or set())
    ):
        raise ScaffoldError(f"Invalid or reserved {label} {value!r}; supply a naming override")
    return value


def package_name(value: str) -> str:
    for part in value.split("."):
        identifier(part, "package name")
    return value
