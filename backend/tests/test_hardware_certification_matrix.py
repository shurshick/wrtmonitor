import ast
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_hardware_certification_order_covers_complete_command_contract():
    source = (ROOT / "scripts" / "hardware_certify.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    values = {}
    for node in tree.body:
        if isinstance(node, (ast.Assign, ast.AnnAssign)):
            target = node.targets[0] if isinstance(node, ast.Assign) else node.target
            if isinstance(target, ast.Name) and target.id in {
                "ORDER",
                "NOT_APPLICABLE",
            }:
                values[target.id] = ast.literal_eval(node.value)

    assert set(values) == {"ORDER", "NOT_APPLICABLE"}

    contract = json.loads(
        (ROOT / "contracts" / "command-contract.json").read_text(encoding="utf-8")
    )["commands"]
    covered = set(values["ORDER"]) | set(values["NOT_APPLICABLE"])

    assert covered == set(contract)
    assert len(values["ORDER"]) == len(set(values["ORDER"]))
