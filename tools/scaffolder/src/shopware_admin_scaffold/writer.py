"""Preflight all destinations, preserve public files, replace owned files atomically."""

import json
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path

from . import ScaffoldError
from .catalog import Json, object_value
from .generator import MANIFEST, OWNER, FilePlan, digest


def safe_path(root: Path, relative: str) -> Path:
    if root.exists() and not root.is_dir():
        raise ScaffoldError(f"Output package is not a directory: {root}")
    path = root / relative
    if Path(relative).is_absolute() or ".." in Path(relative).parts:
        raise ScaffoldError(f"Unsafe output path {relative!r}")
    for ancestor in (path, *path.parents):
        if ancestor.is_symlink():
            raise ScaffoldError(f"Refusing a symlink output path: {ancestor}")
        if ancestor != path and ancestor.exists() and not ancestor.is_dir():
            raise ScaffoldError(f"Output parent is not a directory: {ancestor}")
        if ancestor == root:
            break
    if path.exists() and not path.is_file():
        raise ScaffoldError(f"Output destination is not a file: {path}")
    return path


def atomic_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as stream:
            stream.write(content)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


@dataclass(frozen=True)
class Change:
    path: str
    action: str
    edited: bool = False


def _previous(root: Path) -> Json | None:
    path = safe_path(root, MANIFEST)
    if not path.exists():
        return None
    try:
        metadata = object_value(json.loads(path.read_text(encoding="utf-8")), "Generation manifest")
    except (ValueError, OSError) as error:
        raise ScaffoldError(f"Cannot read generation manifest: {error}") from error
    if metadata.get("owner") != OWNER or metadata.get("format") != 1:
        raise ScaffoldError("Existing manifest does not belong to a supported scaffolder")
    generated = object_value(metadata.get("generated"), "Owned generated files")
    allowed = {"_generated/__init__.py", "_generated/model_bases.py", "_generated/context_base.py"}
    if set(generated) - allowed or any(not isinstance(value, str) for value in generated.values()):
        raise ScaffoldError("Invalid generated file ownership in manifest")
    for name, raw in object_value(metadata.get("entities"), "Previous entities").items():
        model = object_value(raw, name)
        if any(
            not isinstance(model.get(key), str) for key in ("class_name", "module_name", "set_name")
        ):
            raise ScaffoldError(f"Invalid previous model names for {name}")
        fields = object_value(model.get("fields"), "Previous field names")
        if any(not isinstance(value, str) for value in fields.values()):
            raise ScaffoldError(f"Invalid previous field names for {name}")
    return metadata


def inspect(root: Path, plan: FilePlan) -> tuple[Change, ...]:
    root = root.absolute()
    previous = _previous(root)
    owned: Json = {}
    if previous:
        owned = object_value(previous.get("generated"), "Owned generated files")
        if previous.get("package") != plan.manifest["package"]:
            raise ScaffoldError("Package name changed; use a new output directory")
        old_names = object_value(previous.get("entities"), "Previous entities")
        for name, old in old_names.items():
            new = plan.manifest["entities"].get(name)
            if new is None:
                public_path = f"models/{object_value(old, name)['module_name']}.py"
                if safe_path(root, public_path).exists():
                    raise ScaffoldError(
                        f"Removed entity {name!r} still has {public_path}; "
                        "relocate/remove its public model before regenerating"
                    )
                continue
            for key in ("class_name", "module_name", "set_name"):
                if old[key] != new[key]:
                    raise ScaffoldError(
                        f"Public {key} changed for {name!r}; use a new output directory"
                    )
            for wire, python in old["fields"].items():
                if wire in new["fields"] and python != new["fields"][wire]:
                    raise ScaffoldError(
                        f"Public field name changed for {name}.{wire}; use a new output directory"
                    )
        if (
            previous.get("context") != plan.manifest["context"]
            and safe_path(root, "context.py").exists()
        ):
            raise ScaffoldError(
                "Public context changed; relocate/remove context.py before regenerating"
            )
        stale = set(owned) - set(plan.generated)
        stale = {name for name in stale if safe_path(root, name).exists()}
        if stale:
            raise ScaffoldError(
                f"Stale generated files require reconciliation: {', '.join(sorted(stale))}"
            )
    changes: list[Change] = []
    for relative in sorted(plan.public):
        path = safe_path(root, relative)
        if not path.exists():
            changes.append(Change(relative, "create public"))
    for relative, content in sorted(plan.generated.items()):
        path = safe_path(root, relative)
        if not path.exists():
            changes.append(Change(relative, "create generated"))
            continue
        current = path.read_text(encoding="utf-8")
        if relative != MANIFEST and relative not in owned:
            raise ScaffoldError(
                f"Refusing to adopt unowned file {relative}; use a clean output directory"
            )
        if current != content:
            edited = relative != MANIFEST and digest(current) != owned[relative]
            changes.append(Change(relative, "replace generated", edited))
    return tuple(changes)


def apply(root: Path, plan: FilePlan, force: bool = False) -> tuple[Change, ...]:
    changes = inspect(root, plan)
    replacements = [change.path for change in changes if change.action == "replace generated"]
    if replacements and not force:
        raise ScaffoldError(
            "Existing generated files differ; inspect with --dry-run and use --force: "
            + ", ".join(replacements)
        )
    # Manifest is committed last so a failed multi-file write cannot claim completion.
    for change in sorted(changes, key=lambda item: (item.path == MANIFEST, item.path)):
        content = (
            plan.public[change.path]
            if change.action == "create public"
            else plan.generated[change.path]
        )
        atomic_write(safe_path(root.absolute(), change.path), content)
    return changes
