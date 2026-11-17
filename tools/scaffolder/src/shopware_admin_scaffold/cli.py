"""Console interface; configuration paths are relative to their TOML file."""

import argparse
import json
import os
import sys
import tomllib
from collections.abc import Sequence
from pathlib import Path
from typing import TextIO

from . import ScaffoldError, __version__
from .catalog import Catalog, Json, array_value, object_value
from .generator import render
from .naming import pascal_case
from .schema_client import Auth, SchemaBundle, SchemaClient
from .selection import select
from .writer import apply, inspect


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(
        prog="shopware-admin-scaffold", description="Generate typed Shopware models and contexts"
    )
    root.add_argument("--version", action="version", version=__version__)
    sub = root.add_subparsers(dest="command", required=True)
    for name in ("list", "snapshot", "generate"):
        command = sub.add_parser(name)
        command.add_argument("--config", type=Path)
        source = command.add_mutually_exclusive_group()
        source.add_argument("--url")
        source.add_argument("--schema-dir", type=Path)
        command.add_argument("--timeout", type=float, default=None)
        if name == "list":
            command.add_argument("--filter")
            command.add_argument("--json", action="store_true")
        else:
            command.add_argument("--output", type=Path)
            command.add_argument("--force", action="store_true")
        if name == "generate":
            command.add_argument("--package")
            selection = command.add_mutually_exclusive_group()
            selection.add_argument("--entity", action="append")
            selection.add_argument("--all", action=argparse.BooleanOptionalAction, default=None)
            command.add_argument(
                "--scaffold-related", action=argparse.BooleanOptionalAction, default=None
            )
            command.add_argument("--context")
            mode = command.add_mutually_exclusive_group()
            mode.add_argument("--dry-run", action="store_true")
            mode.add_argument("--check", action="store_true")
    return root


def _configuration(args: argparse.Namespace) -> Json:
    config: Json = {}
    if args.config:
        try:
            with args.config.open("rb") as stream:
                config = tomllib.load(stream)
        except (ValueError, OSError) as error:
            raise ScaffoldError(f"Cannot read configuration: {error}") from error
        unknown = set(config) - {
            "url",
            "schema_dir",
            "timeout",
            "output",
            "package",
            "entities",
            "all",
            "scaffold_related",
            "context",
            "entity",
            "field",
        }
        if unknown:
            raise ScaffoldError(f"Unknown configuration keys: {', '.join(sorted(unknown))}")
        for key in ("schema_dir", "output"):
            if key in config:
                if not isinstance(config[key], str):
                    raise ScaffoldError(f"Configuration {key} must be a path string")
                config[key] = args.config.absolute().parent / config[key]
    # An explicit CLI source replaces the source configured in TOML.
    if args.url is not None or args.schema_dir is not None:
        config.pop("url", None)
        config.pop("schema_dir", None)
    if getattr(args, "entity", None) is not None:
        config.pop("all", None)
    if getattr(args, "all", None) is True:
        config.pop("entities", None)
    for key in (
        "url",
        "schema_dir",
        "timeout",
        "output",
        "package",
        "context",
        "all",
        "scaffold_related",
    ):
        value = getattr(args, key, None)
        if value is not None:
            config[key] = value
    if getattr(args, "entity", None) is not None:
        config["entities"] = [
            name.strip() for group in args.entity for name in group.split(",") if name.strip()
        ]
    for key in ("all", "scaffold_related"):
        if key in config and type(config[key]) is not bool:
            raise ScaffoldError(f"Configuration {key} must be a boolean")
    for key in ("url", "package", "context"):
        if key in config and (not isinstance(config[key], str) or not config[key]):
            raise ScaffoldError(f"Configuration {key} must be a nonempty string")
    for key in ("entity", "field"):
        config[key] = object_value(config.get(key, {}), f"Configuration {key}")
    entities = config.get("entities", [])
    if not isinstance(entities, list) or any(
        not isinstance(name, str) or not name
        for name in array_value(config.get("entities", []), "Entities")
    ):
        raise ScaffoldError("Configuration entities must be a list of nonempty strings")
    config["entities"] = entities
    if bool(config.get("url")) == bool(config.get("schema_dir")):
        raise ScaffoldError("Specify exactly one --url or --schema-dir (or configure one)")
    timeout = config.get("timeout", 30.0)
    if type(timeout) not in (int, float):
        raise ScaffoldError("Configuration timeout must be numeric")
    return config


def run(args: argparse.Namespace, output: TextIO, errors: TextIO) -> int:
    config = _configuration(args)
    if args.command != "list" and "output" not in config:
        raise ScaffoldError("--output is required")
    if args.command == "generate":
        if "package" not in config:
            raise ScaffoldError("--package is required")
        if config.get("all", False) == bool(config["entities"]):
            raise ScaffoldError("Specify either --entity or --all")
        if args.force and args.check:
            raise ScaffoldError("--force cannot be combined with --check")
    if "schema_dir" in config:
        if args.command == "snapshot":
            raise ScaffoldError("snapshot requires a live --url")
        bundle = SchemaBundle.load(config["schema_dir"])
    else:
        auth = Auth(
            os.environ.get("SHOPWARE_API_CLIENT_ID"),
            os.environ.get("SHOPWARE_API_CLIENT_SECRET"),
            os.environ.get("SHOPWARE_API_ACCESS_TOKEN"),
        )
        with SchemaClient(config["url"], auth, config.get("timeout", 30.0)) as client:
            bundle = client.fetch()
    catalog = Catalog.parse(bundle.openapi, bundle.dal)
    if args.command == "snapshot":
        bundle.save(config["output"], args.force)
        output.write(f"Saved schema bundle to {config['output']}\n")
        return 0
    if args.command == "list":
        term = (args.filter or "").casefold()
        rows = [
            {
                "entity": entity.name,
                "route": entity.route,
                "class_name": pascal_case(entity.schema_name),
                "unsupported": entity.unsupported,
            }
            for entity in catalog.entities
            if any(
                term in name.casefold() for name in (entity.name, entity.route, entity.schema_name)
            )
        ]
        if args.json:
            output.write(json.dumps(rows, indent=2) + "\n")
        else:
            for row in rows:
                suffix = f" [unsupported: {row['unsupported']}]" if row["unsupported"] else ""
                output.write(f"{row['entity']}\t{row['route']}\t{row['class_name']}{suffix}\n")
            output.write(f"Listed {len(rows)} entities.\n")
        return 0
    selected = select(
        catalog, config["entities"], config.get("all", False), config.get("scaffold_related", False)
    )
    plan = render(
        catalog,
        selected,
        config["package"],
        config.get("context"),
        config["entity"],
        config["field"],
        bundle.hashes,
    )
    for diagnostic in plan.diagnostics:
        errors.write(f"Notice: {diagnostic}\n")
    root = config["output"]
    changes = inspect(root, plan) if args.dry_run or args.check else apply(root, plan, args.force)
    for change in changes:
        suffix = " (generated file was edited)" if change.edited else ""
        output.write(f"{change.action}: {change.path}{suffix}\n")
    if args.check:
        output.write("Generated files differ.\n" if changes else "Generated files are current.\n")
        return int(bool(changes))
    output.write(
        f"{'Planned' if args.dry_run else 'Scaffolded'} {len(selected)} models"
        + (" and a context" if config.get("context") else "")
        + ".\n"
    )
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        return run(args, sys.stdout, sys.stderr)
    except (ScaffoldError, OSError, UnicodeError) as error:
        sys.stderr.write(f"Error: {error}\n")
        return 2
