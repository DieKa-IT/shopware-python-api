# Releasing packages

A release makes a numbered version available for other people to install from
[PyPI](https://pypi.org). This repository publishes two packages:

- `shopware-admin`: the runtime library (Python import: `shopware_admin`).
- `shopware-admin-scaffold`: the model generator (Python import: `shopware_admin_scaffold`).

Both start at `0.1.0a1`, the first alpha preview of version 0.1.0.
Publishing a GitHub Release starts the upload; pushing code alone does not.

## One-time setup: GitHub

Open the [repository settings](https://github.com/DieKa-IT/shopware-python-api/settings),
then **Environments → New environment**. Create `pypi` and `pypi-scaffold`.

These are GitHub publishing settings, unrelated to your Python virtual environment
(`.venv`). Their names must match the workflow and PyPI settings exactly. You may
add required reviewers if you want an approval step before an upload.

The workflow is already in `.github/workflows/publish.yml`. GitHub runs it on its
own servers; you do not need to run a publishing command on your computer.

## One-time setup: PyPI

Create a [PyPI account](https://pypi.org/account/register/) if needed, verify your
email, and enable two-factor authentication. Sign in and open
[account Publishing settings](https://pypi.org/manage/account/publishing/).
For each new package, register a pending publisher with these values:

| PyPI project | GitHub owner | Repository | Workflow filename | Environment |
| --- | --- | --- | --- | --- |
| `shopware-admin` | `DieKa-IT` | `shopware-python-api` | `publish.yml` | `pypi` |
| `shopware-admin-scaffold` | `DieKa-IT` | `shopware-python-api` | `publish.yml` | `pypi-scaffold` |

Use only `publish.yml` in the filename field, not the full path. These settings
allow that specific GitHub workflow and environment to publish the named package.
No PyPI password or API token needs to be stored in GitHub.

A pending publisher does not upload anything or reserve a project name. The first
successful upload creates the PyPI project; the name must be available. If the
project already exists and you own it, add the publisher under that project's
**Manage → Publishing** settings instead.

## Run tests without publishing

Open the repository's **Actions** tab, select **Test packages**, and choose
**Run workflow** on `master`. Pushes to `master` and pull requests also run this
workflow automatically.

The reusable `.github/workflows/test.yml` workflow tests both packages and checks
types, lint, and formatting. It does not build or publish packages.

The separate `.github/workflows/publish.yml` workflow starts only when a GitHub
Release is published. It first calls the same testing workflow for the exact
release code. After those checks pass, it builds both packages, validates their
metadata and installation, and publishes them. The built distributions are also
available as artifacts on the release workflow run.

## Publish the first release

1. Complete both one-time setup sections above.
2. Confirm both `pyproject.toml` files and the scaffolder's `__version__` say
   `0.1.0a1`. The repository is prepared with this version already.
3. Push the release code to `master` and wait for the Actions checks to pass.
4. Open [Releases](https://github.com/DieKa-IT/shopware-python-api/releases), then
   **Draft a new release**, or open the
   [new release form](https://github.com/DieKa-IT/shopware-python-api/releases/new)
   directly.
5. Choose a new tag named `v0.1.0a1` and select `master` as the target. A tag labels
   the exact code belonging to the release. Set the title to `v0.1.0a1`, describe
   the release, and mark it as a **pre-release**, because this is an alpha.
6. Click **Publish release**. Saving a draft or creating a tag alone does not
   upload packages.
7. Open **Actions** and watch **Publish packages**. It checks and builds
   both packages, then uploads the runtime first and the scaffolder second.
   Approve the jobs if you configured required reviewers on the environments.

The tag must exactly match both package versions with a leading `v`; otherwise
the workflow stops before publishing. TestPyPI is not configured.

## Verify the published packages

In a fresh Python 3.12+ virtual environment:

```bash
python -m pip install shopware-admin==0.1.0a1
python -m pip install shopware-admin-scaffold==0.1.0a1
shopware-admin-scaffold --version
```

These commands work only after the uploads succeed. Explicitly selecting an alpha
version avoids pip's usual preference for stable releases.

## Later releases and retries

For a later alpha, use a new version such as `0.1.0a2` in both `pyproject.toml`
files and the scaffolder's `__version__`. Keep the scaffolder's runtime dependency
and generated `RUNTIME_REQUIREMENT` compatible, then run `uv lock` in the root
and in `tools/scaffolder` and commit both lockfiles. Repeat the release steps with
the matching tag.

PyPI does not let you replace already uploaded files with different contents.
If only the scaffolder upload fails after the runtime succeeds, use **Re-run
failed jobs** in GitHub Actions to retry it without uploading the runtime again.
