"""Normalize Shopware OpenAPI and DAL metadata without executing generated code."""

from dataclasses import dataclass
from typing import Any, cast

from . import ScaffoldError
from .naming import pascal_case

Json = dict[str, Any]


def object_value(value: object, label: str) -> Json:
    result = cast(dict[object, Any], value)
    if not isinstance(value, dict):
        raise ScaffoldError(f"{label} must be a JSON object")
    if any(not isinstance(key, str) for key in result):
        raise ScaffoldError(f"{label} must have string keys")
    return cast(Json, result)


def field_flags(value: Any) -> Json:
    # PHP serializes an empty associative array as [].
    return {} if value == [] else object_value(value, "Field flags")


def array_value(value: object, label: str) -> list[Any]:
    result = cast(list[Any], value)
    if not isinstance(value, list):
        raise ScaffoldError(f"{label} must be a JSON array")
    return result


def string_array(value: object, label: str) -> list[str]:
    values = array_value(value, label)
    if any(not isinstance(item, str) for item in values):
        raise ScaffoldError(f"{label} must contain strings")
    return cast(list[str], values)


@dataclass(frozen=True)
class FieldSpec:
    wire_name: str
    json_path: tuple[str, ...]
    value_type: str
    nullable: bool
    writable: bool
    required_on_create: bool
    target: str | None = None
    many: bool = False


@dataclass(frozen=True)
class EntitySpec:
    name: str
    route: str
    schema_name: str
    fields: tuple[FieldSpec, ...]
    unsupported: str | None = None


class SchemaResolver:
    def __init__(self, document: Json):
        self.document = document

    def reference(self, ref: Any) -> Json:
        if not isinstance(ref, str) or not ref.startswith("#/components/"):
            raise ScaffoldError(f"Unsupported schema reference {ref!r}; use local components")
        current: Any = self.document
        for token in ref[2:].split("/"):
            token = token.replace("~1", "/").replace("~0", "~")
            current = object_value(current, ref).get(token)
        return object_value(current, f"Reference {ref}")

    def resolve(self, value: Any, seen: tuple[str, ...] = ()) -> Json:
        source = object_value(value, "Schema")
        result: Json = {}
        if "$ref" in source:
            ref = source["$ref"]
            if not isinstance(ref, str) or ref in seen:
                raise ScaffoldError(f"Circular schema composition at {ref!r}")
            result = self.resolve(self.reference(ref), (*seen, ref))
        for component in array_value(source.get("allOf", []), "allOf"):
            result = self._merge(result, self.resolve(component, seen))
        return self._merge(result, {k: v for k, v in source.items() if k not in {"$ref", "allOf"}})

    @staticmethod
    def _merge(left: Json, right: Json) -> Json:
        merged = {**left, **right}
        if "properties" in left or "properties" in right:
            properties = dict(object_value(left.get("properties", {}), "Properties"))
            for name, schema in object_value(right.get("properties", {}), "Properties").items():
                if name in properties and properties[name] != schema:
                    # Compatible allOf constraints can extend the same property.
                    old = object_value(properties[name], name)
                    new = object_value(schema, name)
                    if any(key in old and old[key] != new[key] for key in new):
                        raise ScaffoldError(f"Conflicting allOf property {name!r}")
                    schema = {**old, **new}
                properties[name] = schema
            merged["properties"] = properties
        if "required" in left or "required" in right:
            merged["required"] = sorted(
                set(string_array(left.get("required", []), "Required fields"))
                | set(string_array(right.get("required", []), "Required fields"))
            )
        if "type" in left and "type" in right and left["type"] != right["type"]:
            raise ScaffoldError("Conflicting allOf schema types")
        return merged


def _type(
    schema: Json, resolver: SchemaResolver, diagnostics: list[str], label: str, depth: int = 0
) -> tuple[str, bool | None]:
    if depth > 12:
        diagnostics.append(f"{label}: recursive/complex JSON value emitted as Any")
        return "Any", None
    schema = resolver.resolve(schema)
    alternatives = schema.get("oneOf", schema.get("anyOf"))
    if alternatives is not None:
        values = [
            _type(object_value(item, label), resolver, diagnostics, label, depth + 1)
            for item in array_value(alternatives, "Schema alternatives")
        ]
        names = sorted({name for name, _ in values if name != "None"})
        union_nullable = any(name == "None" or null for name, null in values)
        if "Any" in names or not names:
            return "Any", union_nullable
        return " | ".join(names), union_nullable
    kind = schema.get("type")
    nullable: bool | None = schema.get("nullable")
    if nullable is not None and type(nullable) is not bool:
        raise ScaffoldError(f"{label}: nullable must be a boolean")
    if isinstance(kind, list):
        nullable = "null" in kind
        kinds = [item for item in string_array(schema["type"], "Schema types") if item != "null"]
        if len(kinds) != 1:
            diagnostics.append(f"{label}: ambiguous JSON type emitted as Any")
            return "Any", nullable
        kind = kinds[0]
    scalar = {
        "string": "str",
        "integer": "int",
        "number": "float",
        "boolean": "bool",
        "null": "None",
    }
    if isinstance(kind, str) and kind in scalar:
        name = scalar[kind]
        if kind == "string" and schema.get("format") == "date-time":
            name = "datetime"
        return name, nullable
    if kind == "array":
        item, item_null = _type(schema.get("items", {}), resolver, diagnostics, label, depth + 1)
        if item_null and item not in {"Any", "None"}:
            item += " | None"
        return f"list[{item}]", nullable
    if kind == "object" or "properties" in schema:
        additional = schema.get("additionalProperties")
        if isinstance(additional, dict) and not schema.get("properties"):
            item, item_null = _type(cast(Json, additional), resolver, diagnostics, label, depth + 1)
            if item_null and item not in {"Any", "None"}:
                item += " | None"
            return f"dict[str, {item}]", nullable
        diagnostics.append(f"{label}: JSON object emitted as dict[str, Any]")
        return "dict[str, Any]", nullable
    diagnostics.append(f"{label}: unknown JSON shape emitted as Any")
    return "Any", nullable


def _schema_name(operation: Json, resolver: SchemaResolver) -> str | None:
    responses = object_value(operation.get("responses", {}), "Responses")
    for status, response in responses.items():
        if not status.startswith("2"):
            continue
        response = resolver.resolve(response)
        content = object_value(response.get("content", {}), "Response content")
        for mime in ("application/json", "application/vnd.api+json"):
            if mime not in content:
                continue
            envelope = resolver.resolve(object_value(content[mime], mime).get("schema", {}))
            data = resolver.resolve(
                object_value(envelope.get("properties", {}), "Envelope").get("data", {})
            )
            items = object_value(data.get("items", {}), "Collection items")
            ref = items.get("$ref")
            if isinstance(ref, str) and ref.startswith("#/components/schemas/"):
                return ref.rsplit("/", 1)[-1]
    return None


def _write_protected(flags: Json) -> bool:
    scopes = flags.get("write_protected")
    if scopes is None or scopes is False:
        return False
    if not isinstance(scopes, list):
        return True
    return not any(
        "user" in group
        for group in array_value(flags["write_protected"], "Write scopes")
        if isinstance(group, list)
    )


@dataclass(frozen=True)
class Catalog:
    entities: tuple[EntitySpec, ...]
    diagnostics: tuple[str, ...]

    @classmethod
    def parse(cls, openapi: Json, dal: Json) -> "Catalog":
        paths = object_value(openapi.get("paths"), "OpenAPI paths")
        schemas = object_value(
            object_value(openapi.get("components"), "Components").get("schemas"), "Schemas"
        )
        resolver = SchemaResolver(openapi)
        diagnostics: list[str] = []
        entities: list[EntitySpec] = []
        for path, raw_operation in sorted(paths.items()):
            route = path.removeprefix("/api/").lstrip("/")
            if "/" in route or "{" in route or route.startswith("_"):
                continue
            path_item = resolver.resolve(raw_operation)
            if "get" not in path_item:
                continue
            operation = object_value(path_item["get"], f"GET {path}")
            schema_name = _schema_name(operation, resolver)
            if schema_name is None:
                operation_id = operation.get("operationId", "")
                if not isinstance(operation_id, str) or not (
                    operation_id.startswith("get") and operation_id.endswith("List")
                ):
                    continue
                candidates = [
                    name for name in schemas if name.casefold() == operation_id[3:-4].casefold()
                ]
                if len(candidates) != 1:
                    raise ScaffoldError(f"{path}: cannot identify the flat entity schema")
                schema_name = candidates[0]
                diagnostics.append(f"{path}: entity schema inferred from operationId")
            if schema_name.endswith("JsonApi") and schema_name[:-7] in schemas:
                schema_name = schema_name[:-7]
            schema = resolver.resolve({"$ref": f"#/components/schemas/{schema_name}"})
            explicit = operation.get("x-entity-name", schema.get("x-entity-name"))
            matches = [
                name
                for name in dal
                if (
                    name == explicit
                    if explicit is not None
                    else name.replace("_", "-") == route
                    or pascal_case(name) == pascal_case(schema_name)
                )
            ]
            if not matches and explicit is None:
                diagnostics.append(
                    f"{path}: no exposed DAL metadata for {schema_name!r}; endpoint omitted"
                )
                continue
            if len(matches) != 1:
                raise ScaffoldError(f"{path}: ambiguous or missing DAL entity for {schema_name!r}")
            name = matches[0]
            metadata = object_value(dal[name], f"DAL entity {name}")
            if metadata.get("entity", name) != name:
                raise ScaffoldError(f"{name}: inconsistent DAL entity identity")
            dal_fields = object_value(metadata.get("properties"), f"DAL fields {name}")
            primary = [
                key
                for key, value in dal_fields.items()
                if field_flags(object_value(value, key).get("flags", {})).get("primary_key")
            ]
            unsupported = None
            if "id" not in dal_fields or dal_fields["id"].get("type") != "uuid":
                unsupported = "requires a conventional UUID id field"
            elif primary and set(primary) not in ({"id"}, {"id", "versionId"}):
                unsupported = f"unsupported composite primary key: {', '.join(primary)}"
            elif metadata.get("read-protected"):
                unsupported = "entity is read protected"
            creation: Json = {}
            if "post" in path_item:
                post = object_value(path_item["post"], f"POST {path}")
                body = resolver.resolve(post.get("requestBody", {}))
                content = object_value(body.get("content", {}), "Request content")
                if "application/json" in content:
                    creation = resolver.resolve(
                        object_value(content["application/json"], "Create content").get(
                            "schema", {}
                        )
                    )
            create_required = set(
                string_array(creation.get("required", []), "Creation requirements")
            )
            properties = object_value(schema.get("properties"), f"Entity properties {name}")
            exposed: list[tuple[str, tuple[str, ...], Json]] = []
            for key, value in properties.items():
                if key == "extensions":
                    extension = resolver.resolve(value)
                    for member, wire_schema in object_value(
                        extension.get("properties", {}), "Extensions"
                    ).items():
                        exposed.append(
                            (member, ("extensions", member), object_value(wire_schema, member))
                        )
                elif key not in {"relationships", "links", "type"} or key in dal_fields:
                    exposed.append((key, (key,), object_value(value, key)))
            fields: list[FieldSpec] = []
            for key, json_path, wire_schema in exposed:
                if key not in dal_fields:
                    diagnostics.append(f"{name}.{key}: absent from DAL metadata; omitted")
                    continue
                field = object_value(dal_fields[key], f"{name}.{key}")
                flags = field_flags(field.get("flags", {}))
                if field.get("type") == "association":
                    relation = field.get("relation")
                    if relation not in {"one_to_one", "many_to_one", "one_to_many", "many_to_many"}:
                        raise ScaffoldError(
                            f"{name}.{key}: unsupported association relation {relation!r}"
                        )
                    target = field.get("entity")
                    if not isinstance(target, str):
                        raise ScaffoldError(f"{name}.{key}: association has no entity target")
                    fields.append(
                        FieldSpec(
                            key,
                            json_path,
                            "",
                            False,
                            False,
                            False,
                            target,
                            relation in {"one_to_many", "many_to_many"},
                        )
                    )
                    continue
                wire_schema = resolver.resolve(wire_schema)
                value_type, nullable = _type(wire_schema, resolver, diagnostics, f"{name}.{key}")
                expected = {"uuid": "str", "int": "int", "float": "float", "boolean": "bool"}.get(
                    field.get("type", "")
                )
                if expected and value_type != "Any" and expected not in value_type.split(" | "):
                    raise ScaffoldError(f"{name}.{key}: conflicting OpenAPI/DAL scalar types")
                if nullable is None:
                    nullable = not bool(flags.get("required")) and key != "id"
                writable = not (
                    wire_schema.get("readOnly")
                    or flags.get("runtime")
                    or _write_protected(flags)
                    or metadata.get("write-protected")
                )
                input_field = object_value(creation.get("properties", {}), "Creation fields").get(
                    key, {}
                )
                required = (
                    key in create_required
                    and "default" not in input_field
                    and key != "id"
                    and writable
                )
                fields.append(FieldSpec(key, json_path, value_type, nullable, writable, required))
            identity = next((item for item in fields if item.wire_name == "id"), None)
            if not unsupported and (
                identity is None or identity.value_type != "str" or identity.nullable
            ):
                unsupported = "requires an exposed nonnullable string UUID id"
            entities.append(EntitySpec(name, route, schema_name, tuple(fields), unsupported))
        if not entities:
            raise ScaffoldError("The schemas contain no exposed Shopware entity endpoints")
        if len({entity.name for entity in entities}) != len(entities):
            raise ScaffoldError("Multiple OpenAPI routes map to the same DAL entity")
        return cls(tuple(sorted(entities, key=lambda entity: entity.name)), tuple(diagnostics))
