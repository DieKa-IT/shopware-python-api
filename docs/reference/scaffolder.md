# Scaffolder reference

[Documentation](../index.md) · [Getting started](../../tools/scaffolder/README.md)

## What each command does

The scaffolder works with **schemas**: descriptions of your shop's entities,
fields, types, and associations. These describe the API structure, not the
customer or product records stored in the shop.

| Command | Reads | Produces | Use it when you want to… |
| --- | --- | --- | --- |
| `list` | Schemas from a live shop or saved directory | Entity names printed to the terminal | Find which entities you can select for generation. |
| `snapshot` | Schemas from a live shop | JSON schema files and an ownership manifest on disk | Save the API structure for offline generation or repeatable CI runs. |
| `generate` | Schemas from a live shop or saved directory | Python model classes, public extension files, and optionally a context | Create or update the Python code your application imports. |

**`snapshot` saves the input; `generate` creates Python code from that input.**
A snapshot contains no generated Python models and is not a backup of shop data.
You can generate code directly from a live shop without taking a snapshot first.

For example, save your shop's schemas, then generate a customer model from them:

```bash
shopware-admin-scaffold snapshot \
  --url https://shop.example --output ./schemas/shopware

shopware-admin-scaffold generate \
  --schema-dir ./schemas/shopware \
  --output ./src/my_shop_api --package my_shop_api \
  --entity customer --context ShopContext
```

The first command writes schema JSON under `schemas/shopware`. The second reads
that directory without contacting the shop and writes importable Python code
under `src/my_shop_api`. You can reuse the saved schemas for subsequent generation
runs; they change only when you explicitly replace the snapshot.

To generate directly from the current live schemas instead:

```bash
shopware-admin-scaffold generate \
  --url https://shop.example \
  --output ./src/my_shop_api --package my_shop_api \
  --entity customer --context ShopContext
```

This reads schemas over HTTP and generates Python code without saving a separate
schema bundle. Generation creates declarations; application code later uses those
models with `shopware-admin` to query or update actual records.

## Command syntax

```text
shopware-admin-scaffold --version
shopware-admin-scaffold list [OPTIONS]
shopware-admin-scaffold snapshot [OPTIONS]
shopware-admin-scaffold generate [OPTIONS]
```

A subcommand is required unless using root `--help` or `--version`. There are no
positional arguments. Options belong after the subcommand, except root `--version`.
In a checkout, run the command through `uv run` from `tools/scaffolder` after
`uv sync --locked`.

Requirements below apply **after merging CLI options and configuration**. An option
marked required may be supplied by its TOML key instead. No configuration file is
automatically discovered; pass `--config` explicitly.

| Command | Required settings | Result |
| --- | --- | --- |
| `list` | Exactly one of `url` or `schema_dir` | Lists exposed entities; writes no files. |
| `snapshot` | Live `url` and `output` | Saves a schema bundle; `schema_dir` is rejected. |
| `generate` | Exactly one source, `output`, `package`, and either nonempty `entities` or `all = true` | Generates the complete selected model package. |

## Root options

| Argument | Required? / default | Meaning |
| --- | --- | --- |
| `-h`, `--help` | Optional | Show root help and exit 0. Also available on every subcommand for its own help. |
| `--version` | Optional | Print the installed scaffolder version and exit 0. Only available before a subcommand. |

## Shared subcommand options

These options are accepted by `list`, `snapshot`, and `generate`.

| Argument | Value | Required? / default | Meaning |
| --- | --- | --- | --- |
| `--config PATH` | TOML file path | Optional; no file loaded by default | Load configuration. CLI paths are relative to the working directory; paths inside TOML are relative to that file. |
| `--url URL` | Shop base URL, e.g. `https://shop.example` | Required source alternative; no default | Fetch both schemas from the live shop. Mutually exclusive with CLI `--schema-dir`. Required source for `snapshot`. |
| `--schema-dir PATH` | Schema bundle directory | Required source alternative; no default | Load saved schemas without network or credential inspection. Allowed for `list` and `generate`; rejected by `snapshot`. |
| `--timeout SECONDS` | Number | Optional; `30.0` | HTTP timeout for live schema requests. Must be finite and greater than zero for a live source. Has no effect on offline schema loading. |

There must be exactly one source after configuration is merged. Passing either
CLI source discards both configured source keys before applying the selected one.

## `list` options

Inspect the available entity catalog without creating schema files or Python code.

In addition to the shared options:

| Argument | Value | Required? / default | Meaning |
| --- | --- | --- | --- |
| `--filter TEXT` | Search text | Optional; no filtering | Case-insensitive substring search over entity, route, and schema names. Does not select models for generation. |
| `--json` | Flag | Optional; false | Print a JSON array instead of tab-separated rows and a count summary. |

JSON rows contain `entity` (DAL name), `route` (API route), `class_name` (derived
Python class name), and `unsupported` (reason string or null). Unsupported entities
remain visible in listings; selecting them for generation fails.

## `snapshot` options

Download and save the shop's OpenAPI and DAL schemas as `openapi.json` and
`entity-schema.json`, together with an ownership manifest. This preserves the
schema input for later offline generation. It does not create Python code or
export customer/product records.

In addition to the shared options:

| Argument | Value | Required? / default | Meaning |
| --- | --- | --- | --- |
| `--output PATH` | Bundle directory | Required; no default | Destination for the two schema files and ownership manifest. |
| `--force` | Flag | Optional; false | Permit replacement of an existing owned schema bundle. Does not adopt an arbitrary existing directory. Not configurable in TOML. |

`snapshot` requires live `--url` or configured `url`. It does not accept generation
options such as `--package`, `--entity`, `--dry-run`, or `--check`.

## `generate` options

Build Python code for selected entities using either live schemas (`--url`) or
saved schemas (`--schema-dir`). The output includes generated model bases and
public subclasses for handwritten extensions. `--context` also creates a context
with named entity sets. See [generated files and overwrite behavior](#generated-files-and-overwrite-behavior)
for the output layout and regeneration rules.

In addition to the shared options:

| Argument | Value | Required? / default | Meaning |
| --- | --- | --- | --- |
| `--output PATH` | Package directory | Required; no default | Destination package directory, e.g. `src/my_shop_api`. |
| `--package NAME` | Dotted Python import name | Required; no default | Import name corresponding to the output directory, e.g. `my_shop_api` or `application.my_shop_api`. Includes any namespace prefixes. |
| `--entity NAME` | Entity, route, or schema/class name | Required selection alternative; none by default | Select entities by case-insensitive exact match. Repeat the option or comma-separate names: `--entity product --entity category` or `--entity product,category`. Replaces the configured entity list and clears configured `all`. |
| `--all` | Flag | Required selection alternative; false by default | Select every catalog entity and clear configured `entities`. Mutually exclusive with CLI `--entity`. Fails if any selected entity is unsupported. |
| `--no-all` | Flag | Optional | Disable configured `all`. Does not itself select any entities; a nonempty configured entity list must remain. Mutually exclusive with CLI `--entity`. |
| `--scaffold-related` | Flag | Optional; false | Add direct association targets of the initially selected entities once. Does not recursively traverse the graph. |
| `--no-scaffold-related` | Flag | Optional | Disable configured related-entity expansion. |
| `--context NAME` | Python class name | Optional; no context generated by default | Generate a context base and public subclass with entity sets for selected public models, e.g. `ShopContext`. |
| `--force` | Flag | Optional; false | Allow changed owned generated files to be replaced. Public files remain untouched. Cannot be combined with `--check`. |
| `--dry-run` | Flag | Optional; false | Inspect and report planned changes without writing. Mutually exclusive with `--check`. May be combined with `--force`, but still writes nothing. |
| `--check` | Flag | Optional; false | Inspect without writing; exit 1 if generated files differ or public files need creation. Cannot be combined with `--dry-run` or `--force`. |

`--dry-run` and `--check` still fetch schemas when using a live source. They are
read-only with respect to the destination. `--force`, `--dry-run`, and `--check`
are CLI-only; they are not configuration keys.

Associations to entities outside the final selection are omitted with a notice.
Missing or ambiguous selection names fail; use `list --filter` to find a name.
Each generation replaces the complete selection rather than appending entities.

## Configuration keys

All keys are optional individually. The selected command's required settings must
be satisfied by the merged result. Unknown keys are rejected.

| TOML key | Type | Commands using it | Default / meaning |
| --- | --- | --- | --- |
| `url` | Nonempty string | All | No default; live schema source. |
| `schema_dir` | Path string | `list`, `generate` | No default; offline schema source. Rejected by `snapshot`. |
| `timeout` | Number | All, for live sources | `30.0` seconds. |
| `output` | Path string | `snapshot`, `generate` | No default; required destination. |
| `package` | Nonempty string | `generate` | No default; required dotted import name. |
| `entities` | Array of nonempty strings | `generate` | Empty list; requires explicit selection or `all = true`. |
| `all` | Boolean | `generate` | `false`; select all catalog entities. |
| `scaffold_related` | Boolean | `generate` | `false`; one-level association expansion. |
| `context` | Nonempty string | `generate` | Absent; no context generated. |
| `entity` | Table of entity override tables | `generate` | Empty; naming overrides described below. |
| `field` | Table of entity/field override tables | `generate` | Empty; field overrides described below. |

Shared configuration files may contain settings for other commands; those settings
do not make the corresponding CLI flags available on that command. For example,
`list` accepts a config containing `output` but does not use it.

Explicit CLI values override their corresponding configuration keys. Source and
selection replacement follow the rules in the option tables. Configuration
`all = true` and a nonempty `entities` list conflict unless a CLI selection clears
one of them. Credentials are not valid TOML keys.

### Entity overrides

Use `[entity.DAL_ENTITY_NAME]`, for example `[entity.product_manufacturer]`.
Overrides refer to selected entities by DAL name.

| Key | Type | Default when omitted | Meaning |
| --- | --- | --- | --- |
| `class_name` | Python identifier string | Derived from schema name | Public model class name, e.g. `Manufacturer`. |
| `set_name` | Python identifier string | Pluralized snake_case class name | Context entity-set name, e.g. `manufacturers`. |

### Field overrides

Use `[field.DAL_ENTITY_NAME.WIRE_PROPERTY]`. The property must already exist in
the catalog; these overrides cannot add a missing field. Use a
[public model extension](../how-to/add-model-fields.md) to add one.

| Key | Type | Default when omitted | Meaning |
| --- | --- | --- | --- |
| `name` | Python identifier string | Derived from wire property | Python attribute name. Supported for scalars and associations. |
| `nullable` | Boolean | Inferred from schemas | Whether a scalar's type permits null. Not supported for associations. |
| `writable` | Boolean | Inferred from schemas | Whether a scalar can be assigned and written. Not supported for associations. |
| `required_on_create` | Boolean | Inferred from POST input schema | Whether a scalar must have a write value when creating an entity. Not supported for associations. |

A primary ID cannot be nullable or required on create. A read-only field cannot be
required on create. Unknown names, unsupported override keys, Python keywords,
reserved runtime members, and naming collisions fail before writes.

```toml
schema_dir = "schemas/shopware"
output = "src/my_shop_api"
package = "my_shop_api"
entities = ["product", "product_manufacturer"]
context = "ShopContext"

[entity.product_manufacturer]
class_name = "Manufacturer"
set_name = "manufacturers"

[field.product.stock]
required_on_create = true

[field.product.name]
nullable = true
```

## Authentication environment variables

These variables are used only for live sources. There are no credential CLI flags.

| Variable | Required? | Meaning |
| --- | --- | --- |
| `SHOPWARE_API_CLIENT_ID` | Required with client secret | Integration client ID. |
| `SHOPWARE_API_CLIENT_SECRET` | Required with client ID | Integration client secret. |
| `SHOPWARE_API_ACCESS_TOKEN` | Alternative to the integration pair | Existing access token. |

Use either the complete integration pair or an access token. Mixing modes or
supplying an incomplete pair fails. With no credentials, requests are anonymous.
Rejected supplied credentials fail without anonymous fallback. Schema HTTP errors
do not echo credentials or response bodies.

## Exit codes and output

| Code | Meaning |
| --- | --- |
| `0` | Success, including help/version, `--dry-run`, and a current `--check`. |
| `1` | `generate --check` found generated differences or public files needing creation. |
| `2` | Argument parsing, configuration, schema, generation, or filesystem error. |

Listings, snapshot confirmations, and file-change reports go to stdout. Generation
notices and handled errors go to stderr. In `--check` mode, an error is code 2,
not a difference result.

## Schema input contract

Live discovery reads both endpoints from the same shop:

- `/api/_info/openapi3.json?type=jsonapi`: API routes, flat entity schemas, and create-input requirements.
- `/api/_info/entity-schema.json`: DAL identities, cardinality, and field flags.

Offline bundles require `openapi.json` and `entity-schema.json`. A saved bundle
also has an ownership manifest with canonical content hashes and reported schema
version. Manually exported pairs without a manifest are accepted; if a manifest
exists, hashes must match. Offline commands do not connect to Shopware.

OpenAPI endpoints without matching exposed DAL metadata are omitted with a notice.
Explicit entity identities and ambiguous matches fail rather than guessing.
Unsupported primary-key contracts remain visible in listings and fail on selection.

## Generated files and overwrite behavior

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
