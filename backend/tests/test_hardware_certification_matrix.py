import importlib.util
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_hardware_certification_order_covers_complete_command_contract():
    spec = importlib.util.spec_from_file_location(
        "hardware_certify", ROOT / "scripts" / "hardware_certify.py"
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)

    contract = json.loads(
        (ROOT / "contracts" / "command-contract.json").read_text(encoding="utf-8")
    )["commands"]
    covered = set(module.ORDER) | set(module.NOT_APPLICABLE)

    assert covered == set(contract)
    assert len(module.ORDER) == len(set(module.ORDER))
