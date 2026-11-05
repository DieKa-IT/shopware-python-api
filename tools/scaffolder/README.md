# shopware-admin-scaffold

> **Early alpha — work in progress.** Available for experimentation and evaluation.
> APIs and generated code may change without backward compatibility. Compatibility
> with individual Shopware versions and plugins is still being validated.
> Not yet recommended for production use.

Licensed under the [MIT License](LICENSE).

A separate development tool for generating typed models and optional contexts for
`shopware-admin-python`. The runtime library does not include this tool or generated
Shopware models. Requires Python 3.12+ and uv.

## Local development and use

From this directory:

```bash
uv sync --locked
uv run shopware-admin-scaffold --help
uv run shopware-admin-scaffold list --url http://127.0.0.1:8000 --filter customer
uv run shopware-admin-scaffold generate \
  --url http://127.0.0.1:8000 \
  --output /absolute/path/to/application/src/my_shop_api --package my_shop_api \
  --entity customer --entity country --context ShopContext
```

The tool has its own `pyproject.toml` and lockfile, and an editable local runtime
dependency for development. It builds an independent wheel with a versioned runtime
dependency. It is not published to a package registry yet. From another uv project,
add this directory as a development dependency:

```bash
uv add --dev --editable /absolute/path/to/shopware-admin-python/tools/scaffolder
```

The generated application must depend on `shopware-admin-python>=0.1.0a1,<0.2`.
For local development, add the runtime with an editable path too. Generated modules
import only the runtime, never the scaffolder. Set `--package` to the dotted import
name of the directory supplied as `--output`, including namespace prefixes if used.

## Schema sources and authentication

Live discovery reads these endpoints from the same shop:

- `/api/_info/openapi3.json?type=jsonapi` for API routes, flat entity schemas, and
  create-input requirements.
- `/api/_info/entity-schema.json` for DAL identities, cardinality, and field flags.

Set `SHOPWARE_API_CLIENT_ID` and `SHOPWARE_API_CLIENT_SECRET`, or use
`SHOPWARE_API_ACCESS_TOKEN`. Do not set both authentication modes. With neither,
the tool requests schemas anonymously. Rejected supplied credentials fail without
falling back. Schema HTTP errors do not echo credentials or response bodies.
`--timeout` controls the request timeout in seconds (default 30).

Save a bundle for offline generation and CI:

```bash
uv run shopware-admin-scaffold snapshot \
  --url http://127.0.0.1:8000 --output ./schemas/shopware

uv run shopware-admin-scaffold list --schema-dir ./schemas/shopware --json
uv run shopware-admin-scaffold generate \
  --schema-dir ./schemas/shopware \
  --output ./src/my_shop_api --package my_shop_api \
  --entity product --scaffold-related --context ShopContext
```

Bundles contain `openapi.json`, `entity-schema.json`, and an ownership manifest
with canonical content hashes and the schema's reported version. A pair of manually
exported JSON files is also accepted without a manifest. If a manifest exists,
the hashes must match. Snapshot replacement requires an existing owned bundle and
`--force`; arbitrary directories are never adopted. Both schemas are required.
Offline commands do not connect to Shopware or inspect credential settings.

`list --filter` searches entity, route, and schema names without generating files.
`generate` requires explicit `--entity` selections (repeat or comma-separate), or
`--all`. Selections accept entity, route, or schema/class names. `--scaffold-related`
adds direct association targets only once; it does not recursively generate the
entire shop. Associations whose targets are outside the selection are omitted with
a notice. Unsupported UUID/primary-key contracts appear in listings and fail when
selected, including with `--all`.

OpenAPI endpoints without matching exposed DAL metadata are omitted with a notice.
For example, the shop may include `/notification` in OpenAPI while excluding that
entity from the DAL export. Explicit entity identities and ambiguous matches still
fail rather than guessing a mapping.

## Configuration and regeneration

```toml
# shopware-scaffold.toml
schema_dir = "schemas/shopware"
output = "src/my_shop_api"
package = "my_shop_api"
entities = ["product", "category", "product_manufacturer"]
context = "ShopContext"
scaffold_related = false

[entity.product_manufacturer]
class_name = "Manufacturer"
set_name = "manufacturers"

[field.product.stock]
required_on_create = true

[field.product.name]
nullable = true
```

Paths in TOML are relative to the configuration file; CLI paths are relative to
the working directory. Explicit CLI values override configuration. Choosing a CLI
source replaces the configured source; a CLI selection replaces the configured
selection. `--no-all` and `--no-scaffold-related` can disable configured flags.
Credentials are not configuration keys.

Entity overrides accept `class_name` and `set_name`. Field overrides use the DAL
wire property name and accept `name`, `nullable`, `writable`, and
`required_on_create`; association overrides only accept `name`. Unknown overrides,
Python keywords, reserved runtime members, and naming collisions fail before writes.

```bash
uv run shopware-admin-scaffold generate --config shopware-scaffold.toml --dry-run
uv run shopware-admin-scaffold generate --config shopware-scaffold.toml --force
uv run shopware-admin-scaffold generate --config shopware-scaffold.toml --check
```

`--dry-run` lists file changes and diagnostics without writing. `--check` is also
read-only and exits 1 when generated files differ or public files need creation;
0 means current and 2 means an error. With a live source, either mode still fetches
schemas. Other successful commands exit 0. Pin the generator and use a saved bundle
for repeatable CI checks.

Generation creates this package:

```text
my_shop_api/
  __init__.py
  models/
    __init__.py
    product.py                 # Public Product(ProductBase); create once
    category.py                # Public Category(CategoryBase); create once
    manufacturer.py            # Public Manufacturer(ManufacturerBase); create once
  context.py                   # Public ShopContext(ShopContextBase); create once
  _generated/
    __init__.py
    model_bases.py              # Generated bases and association declarations
    context_base.py             # Optional; uses public model classes
    manifest.json              # Names, ownership, runtime range, schema/file hashes
```

Add fields and behavior to public subclasses. They and public package initializers
are never rewritten, even under `--force`. Generated files are replaced only with
`--force` when content differs; identical content is a no-op. Unowned generated
destinations and symlink paths are rejected. A changed generated file is reported
as edited. Files are individually replaced atomically after complete preflight;
the set of writes is not a filesystem transaction.

Changing existing public class/module/field/set names or the package requires a
new output directory. Removing a selected entity requires reconciling its existing
public model before regeneration; removing/renaming a context also requires
reconciling its public and stale generated files. The tool does not delete those
files automatically. Each run regenerates the complete selection rather than
appending models or entity sets.

## Generated model behavior

Models use `Field`, `ToOne`, and `ToMany`, retaining wire aliases and exact routes.
All model bases live in one module. Associations refer to public types through
public module aliases imported after every base definition. This supports cyclic
graphs, runtime annotation resolution, and typing of handwritten related fields.
Keep model module bodies and package initializers free of association queries or
other premature annotation evaluation. Import public models from their files,
for example `from my_shop_api.models.product import Product`.

The context inherits the runtime `Context`, declares `entity_set(PublicModel)`,
and inherits connection/authentication behavior; it needs no generated constructor.
Public context subclasses can add queries and action helpers.

Writable scalar constructors allow omission without inserting defaults. Explicit
null stays distinct from omission. Creation requirements come from the POST input
schema, excluding primary IDs, defaults, and read-only fields; overrides can refine
them. Explicit OpenAPI nullability takes precedence; when omitted, DAL required
flags conservatively determine scalar nullability. Associations stay read-only.
To-one values are optional, while an unloaded to-many collection raises
`FieldNotLoadedError`, as in the runtime contract.

Numbers use `float`, UUIDs use `str`, and date-times use `datetime`. Date-only values
remain strings. Opaque objects use `dict[str, Any]`; unknown shapes use `Any` with
notices. Price containers follow OpenAPI, including its array shape rather than
the DAL's broad JSON classification. No Decimal or nested value-object codecs are
introduced. Dynamic custom-field names remain handwritten model extensions.
Plugin extension fields use their nested `extensions` JSON path and their DAL
criteria name; unknown fields remain available through runtime `raw_data`.

## Validation

```bash
uv run pytest
uv run mypy
uv run pyright
uv run ruff check .
uv run ruff format --check .
uv build
```

Tests use HTTPX MockTransport and compact schema pairs derived from the local
Shopware schema builders. They cover generated consumer typing and runtime
behavior, import orders, cyclic associations, custom fields, explicit writes,
authentication, configuration, and overwrite protection. No test requires a live
shop. Live compatibility with a particular Shopware/plugin version still needs
verification against that installation's exported schemas and payloads.

See the [architecture proposal](../../docs/scaffolding-proposal.md) for the design
background and package boundary.
