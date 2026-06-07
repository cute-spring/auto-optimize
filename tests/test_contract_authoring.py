from __future__ import annotations

from pathlib import Path

from auto_optimize.cli import main
from auto_optimize.contract.loader import load_contract
from auto_optimize.contract.validator import validate_contract

ROOT = Path(__file__).resolve().parents[1]


def test_minimal_faq_contract_validates() -> None:
    contract_path = ROOT / "examples" / "contracts" / "minimal_faq.contract.yaml"
    contract = load_contract(contract_path)

    result = validate_contract(contract)

    assert result.valid


def test_explain_contract_command_writes_markdown(tmp_path: Path) -> None:
    contract_path = ROOT / "examples" / "contracts" / "minimal_faq.contract.yaml"
    output_path = tmp_path / "contract_explanation.md"

    exit_code = main(["explain-contract", str(contract_path), "--output", str(output_path)])

    assert exit_code == 0
    assert output_path.exists()
    content = output_path.read_text(encoding="utf-8")
    assert "Contract Explanation" in content
    assert "Defaults Applied" in content
    assert "search_space" in content


def test_validation_report_includes_field_and_hint(tmp_path: Path) -> None:
    contract_path = ROOT / "examples" / "contracts" / "minimal_faq.contract.yaml"
    contract = load_contract(contract_path)
    contract.workspace.path = "missing-workspace"
    contract.workspace_path = (contract.contract_dir / "missing-workspace").resolve()

    result = validate_contract(contract)

    assert not result.valid
    issue = next(issue for issue in result.issues if issue.code == "missing_workspace")
    assert issue.field == "workspace.path"
    assert issue.hint is not None
