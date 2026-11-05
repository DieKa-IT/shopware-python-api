"""Schema pairs derived from the local Shopware schema builders; no live HTTP."""

from pathlib import Path

import pytest

from shopware_admin_scaffold.catalog import Catalog
from shopware_admin_scaffold.schema_client import SchemaBundle


@pytest.fixture
def bundle():
    return SchemaBundle.load(Path(__file__).parent / "fixtures")


@pytest.fixture
def catalog(bundle):
    return Catalog.parse(bundle.openapi, bundle.dal)
