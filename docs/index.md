# Documentation

`shopware-admin` expresses Shopware API contracts through Python models. Use the
separate scaffolder to generate an initial model, then refine it for your shop.

These docs follow [Diátaxis](https://diataxis.fr/): tutorials teach through a guided
experience, how-to guides solve tasks, reference describes behavior, and explanation
covers the reasons behind the design.

## Tutorials — learn by doing

Start here if you are new to the library.

- [Your first typed query](tutorials/first-query.md): declare a model, query a mock
  API, inspect typed results, and preview a patch without a live shop.
- [Scaffold and extend models](tutorials/scaffold-and-extend.md): generate models
  from a shop and add a handwritten custom-field mapping.

## How-to guides — complete a task

These guides assume you have a model and can construct a context.

- [Query products and load associations](how-to/query-products.md)
- [Patch selected fields](how-to/patch-fields.md)
- [Add missing or custom fields to a model](how-to/add-model-fields.md)
- [Scaffold and regenerate models](how-to/scaffold-models.md)

## Reference — look up the contract

- [Models and contexts](reference/models.md)
- [Queries, pagination, execution, and field presence](reference/queries.md)
- [Writes and prepared requests](reference/writes.md)
- [Client, authentication, request context, and transport](reference/client.md)
- [Scaffolder CLI and configuration](../tools/scaffolder/README.md)

## Explanation — understand the design

- [Why typed Python?](explanation/why-typed-python.md)
- [Schema gaps and model ownership](explanation/schema-gaps.md)
- [Explicit writes and field presence](explanation/explicit-writes.md)

## Project maintenance

[Development](development.md) · [Releasing](releasing.md) ·
[Scaffolder architecture proposal](scaffolding-proposal.md)

The architecture proposal records design background; use the scaffolder reference
for its current behavior.
