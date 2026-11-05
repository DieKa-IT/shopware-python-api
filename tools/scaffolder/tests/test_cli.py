import io
import json
from pathlib import Path

import pytest

from shopware_admin_scaffold import ScaffoldError
from shopware_admin_scaffold.cli import main, parser, run

FIXTURES = Path(__file__).parent / "fixtures"


def invoke(*arguments):
    output, errors = io.StringIO(), io.StringIO()
    code = run(parser().parse_args(arguments), output, errors)
    return code, output.getvalue(), errors.getvalue()


def test_offline_listing_filter_json_and_no_matches():
    code, output, _ = invoke("list", "--schema-dir", str(FIXTURES), "--filter", "dieka", "--json")
    assert code == 0
    assert json.loads(output)[0]["route"] == "dieka-erp-product-sync"
    assert "Listed 0" in invoke("list", "--schema-dir", str(FIXTURES), "--filter", "missing")[1]


def test_config_paths_cli_precedence_dry_run_and_check(tmp_path, monkeypatch):
    config = tmp_path / "scaffold.toml"
    config.write_text(f"""schema_dir = {json.dumps(str(FIXTURES))}
output = "src/shop"
package = "shop"
entities = ["product"]
context = "ShopContext"
""")
    monkeypatch.chdir(tmp_path.parent)
    code, output, _ = invoke("generate", "--config", str(config), "--dry-run")
    assert code == 0 and "create public" in output
    assert not (tmp_path / "src").exists()
    assert invoke("generate", "--config", str(config), "--check")[0] == 1
    assert invoke("generate", "--config", str(config))[0] == 0
    assert (tmp_path / "src/shop/models/product.py").exists()
    assert invoke("generate", "--config", str(config), "--check")[0] == 0
    assert invoke("generate", "--config", str(config))[0] == 0
    assert (
        invoke(
            "generate",
            "--config",
            str(config),
            "--output",
            str(tmp_path / "elsewhere"),
            "--entity",
            "category,media",
        )[0]
        == 0
    )
    assert (tmp_path / "elsewhere/models/media.py").exists()
    assert not (tmp_path / "elsewhere/models/product.py").exists()


def test_bad_options_fail_before_creating_output(tmp_path):
    with pytest.raises(ScaffoldError, match="either --entity or --all"):
        invoke(
            "generate",
            "--schema-dir",
            str(FIXTURES),
            "--output",
            str(tmp_path / "out"),
            "--package",
            "shop",
        )
    with pytest.raises(ScaffoldError, match="--force"):
        invoke(
            "generate",
            "--schema-dir",
            str(FIXTURES),
            "--output",
            str(tmp_path / "out"),
            "--package",
            "shop",
            "--entity",
            "product",
            "--check",
            "--force",
        )
    assert not (tmp_path / "out").exists()


def test_errors_have_nonzero_exit_and_no_traceback(capsys):
    assert main(["list"]) == 2
    assert "Specify exactly one" in capsys.readouterr().err


def test_unknown_config_keys_and_bad_types(tmp_path):
    config = tmp_path / "bad.toml"
    config.write_text('schema_dir = "fixtures"\nsecrets = "oops"\n')
    with pytest.raises(ScaffoldError, match="Unknown configuration"):
        invoke("list", "--config", str(config))
    config.write_text('schema_dir = "fixtures"\nentities = "product"\n')
    with pytest.raises(ScaffoldError, match="list of nonempty strings"):
        invoke("list", "--config", str(config))
