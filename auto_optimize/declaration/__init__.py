"""Declaration loading and conversion."""

from auto_optimize.declaration.converter import declaration_to_contract_data, write_contract_from_declaration
from auto_optimize.declaration.loader import DeclarationValidationError, load_declaration
from auto_optimize.declaration.models import OptimizationDeclaration
from auto_optimize.declaration.reverse_converter import contract_to_declaration_data, write_declaration_from_contract

__all__ = [
    "DeclarationValidationError",
    "OptimizationDeclaration",
    "contract_to_declaration_data",
    "declaration_to_contract_data",
    "load_declaration",
    "write_declaration_from_contract",
    "write_contract_from_declaration",
]
