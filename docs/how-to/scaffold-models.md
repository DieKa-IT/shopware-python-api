# Scaffold and regenerate models

[Documentation](../index.md)

The scaffolder is a separate development tool. Generated applications depend on
the runtime, not on the generator. For initial setup, follow
[scaffold and extend models](../tutorials/scaffold-and-extend.md).

Run the commands below from `tools/scaffolder` after `uv sync --locked`. Paths in
these examples are relative to that directory. Substitute your application paths.

## Select the schema source and entities

```bash
uv run shopware-admin-scaffold snapshot \
  --url https://shop.example --output ./schemas/shopware
uv run shopware-admin-scaffold list --schema-dir ./schemas/shopware --filter product
uv run shopware-admin-scaffold generate \
  --schema-dir ./schemas/shopware \
  --output ./src/my_shop_api --package my_shop_api \
  --entity product --entity category --context ShopContext
```

Both OpenAPI and DAL schemas are required. Authentication uses
`SHOPWARE_API_CLIENT_ID` plus `SHOPWARE_API_CLIENT_SECRET`, or
`SHOPWARE_API_ACCESS_TOKEN`. Offline generation does not inspect credentials or
connect to a shop. `--scaffold-related` adds direct association targets once;
it does not recursively include the whole shop.

## Record repeatable settings

Create `shopware-scaffold.toml`:

```toml
schema_dir = "schemas/shopware"
output = "src/my_shop_api"
package = "my_shop_api"
entities = ["product", "category"]
context = "ShopContext"
```

Configuration paths are relative to that file. `package` must match the dotted
import name of the output package. Keep handwritten fields and behavior in public
model and context subclasses.

## Preview and apply regeneration

```bash
uv run shopware-admin-scaffold generate --config shopware-scaffold.toml --dry-run
uv run shopware-admin-scaffold generate --config shopware-scaffold.toml --force
uv run shopware-admin-scaffold generate --config shopware-scaffold.toml --check
```

`--dry-run` reports changes without writing. `--force` replaces changed owned
generated files; public model shells and public initializers are never rewritten.
The tool rejects unowned generated destinations. Review changes in version control.

Each run generates the complete selection. Keep all intended entities in the
configuration. Renaming public models or removing entities needs manual
reconciliation; generation does not automatically delete stale files.

For CI, pin the generator, use a saved schema bundle, and run `--check`. Exit 0
means current, 1 means generated changes or missing public files, and 2 means an
error. See the [scaffolder reference](../reference/scaffolder.md) for overrides,
snapshot replacement, ownership rules, and all CLI details.
