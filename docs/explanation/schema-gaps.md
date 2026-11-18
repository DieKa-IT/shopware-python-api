# Schema gaps and model ownership

[Documentation](../index.md)

A shop's API behavior, its exported schemas, and your Python model describe related
but different things. A field may be reachable through the API without being
fully described in the exported metadata. Dynamic custom-field names and plugin
extensions make this especially relevant.

The scaffolder combines OpenAPI and DAL metadata to produce a useful starting
point. It cannot infer every application-specific field or guarantee that every
schema detail matches your installation. Unknown response fields remain available
in `raw_data`; adding a model declaration gives a verified field a typed interface.

## Separate generated facts from handwritten decisions

Generated bases live under `_generated/`. Public model subclasses and context
subclasses belong to your application. Regeneration updates the bases while
preserving handwritten public files, including under `--force`.

This boundary lets you add a field, give it a Python name, describe its nullability,
and restrict writes without editing files that generation replaces. Configuration
overrides refine fields already known to the generator; handwritten declarations
cover additional mappings such as dynamic custom-field keys.

Generated contexts refer to public model classes. The runtime registry resolves
associations to those public classes, so related objects can expose your added
fields too. Registering the public types is part of maintaining the model contract.

## A declaration maps an existing capability

Adding `erp_reference` to a Python model does not create a Shopware custom field,
install a plugin, grant permissions, or make the field filterable. Reading, filtering,
and writing can have different contracts. JSON paths and DAL criteria paths may
differ, particularly for plugin extensions.

Verify those capabilities against your shop and record what you know in the
model. See [add model fields](../how-to/add-model-fields.md) for the procedure and
[scaffold and regenerate](../how-to/scaffold-models.md) for maintenance.
