"""Conservative Tree-sitter facts for source-code graph ingestion.

This module is deliberately storage-agnostic: callers can persist its facts without
making parser output resolve names or manufacture graph edges.  Every fact retains
its source range so later resolution remains explainable.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from tree_sitter_language_pack import get_parser

PARSER_VERSION = "kw-003-tree-sitter-v1"
LanguageName = Literal["python", "typescript", "tsx", "javascript", "jsx"]
_LANGUAGE_ALIASES = {"js": "javascript", "jsx": "jsx", "ts": "typescript", "tsx": "tsx"}


@dataclass(frozen=True)
class SourceRange:
    start_byte: int
    end_byte: int
    start_line: int
    end_line: int


@dataclass(frozen=True)
class DeclarationFact:
    name: str
    qualified_name: str
    kind: str
    parent_qualified_name: str | None
    signature: str
    range: SourceRange
    name_range: SourceRange
    exported: bool = False


@dataclass(frozen=True)
class ImportFact:
    module: str
    imported_name: str | None
    local_name: str | None
    range: SourceRange


@dataclass(frozen=True)
class ReferenceFact:
    kind: str
    target_name: str
    qualifier: str | None
    scope_qualified_name: str | None
    range: SourceRange


@dataclass(frozen=True)
class DiagnosticFact:
    message: str
    range: SourceRange


@dataclass(frozen=True)
class AnalysisFacts:
    language: str
    parser_version: str
    declarations: tuple[DeclarationFact, ...]
    imports: tuple[ImportFact, ...]
    references: tuple[ReferenceFact, ...]
    diagnostics: tuple[DiagnosticFact, ...]


def _range(node) -> SourceRange:
    return SourceRange(node.start_byte, node.end_byte, node.start_point.row + 1, node.end_point.row + 1)


def _text(node, source: bytes) -> str:
    return source[node.start_byte : node.end_byte].decode("utf-8")


def _named(node, kind: str):
    return next((child for child in node.named_children if child.type == kind), None)


def _descendants(node):
    yield node
    for child in node.children:
        yield from _descendants(child)


def _declaration(node, source: bytes, parent: str | None, exported: bool) -> DeclarationFact | None:
    python_kinds = {"class_definition": "class", "function_definition": "function"}
    ts_kinds = {
        "class_declaration": "class", "function_declaration": "function",
        "method_definition": "method", "interface_declaration": "interface",
        "enum_declaration": "enum", "type_alias_declaration": "type",
    }
    kind = python_kinds.get(node.type) or ts_kinds.get(node.type)
    name_node = None
    if kind:
        name_node = next((c for c in node.named_children if c.type in {"identifier", "type_identifier", "property_identifier"}), None)
    elif node.type == "variable_declarator":
        kind, name_node = "variable", _named(node, "identifier")
    if not kind or name_node is None:
        return None
    name = _text(name_node, source)
    qualified = f"{parent}.{name}" if parent else name
    # A declaration signature is intentionally only its header/initializer, never a body.
    signature_end = next((c.start_byte for c in node.children if c.type in {"block", "statement_block", "class_body"}), node.end_byte)
    return DeclarationFact(name, qualified, kind, parent, source[node.start_byte:signature_end].decode("utf-8").rstrip(), _range(node), _range(name_node), exported)


def _imports(node, source: bytes) -> list[ImportFact]:
    results: list[ImportFact] = []
    if node.type == "import_statement" and any(c.type == "from" for c in node.children):  # TypeScript
        string = _named(node, "string")
        module = _text(string, source)[1:-1] if string else ""
        specs = [n for n in _descendants(node) if n.type == "import_specifier"]
        default = next((n for n in node.named_children if n.type == "identifier"), None)
        if default:
            results.append(ImportFact(module, "default", _text(default, source), _range(default)))
        for spec in specs:
            names = [c for c in spec.named_children if c.type == "identifier"]
            imported = _text(names[0], source) if names else None
            local = _text(names[-1], source) if names else None
            results.append(ImportFact(module, imported, local, _range(spec)))
        if not specs and not default:
            results.append(ImportFact(module, None, None, _range(node)))
    elif node.type == "import_statement":  # Python
        for item in node.named_children:
            if item.type not in {"dotted_name", "aliased_import"}:
                continue
            names = [c for c in item.named_children if c.type in {"dotted_name", "identifier"}]
            module = _text(names[0], source) if names else _text(item, source)
            local = _text(names[-1], source) if item.type == "aliased_import" and len(names) > 1 else module.split(".")[0]
            results.append(ImportFact(module, None, local, _range(item)))
    elif node.type == "import_from_statement":
        dotted = _named(node, "dotted_name")
        module = _text(dotted, source) if dotted else ""
        for item in node.named_children:
            if item.type not in {"dotted_name", "aliased_import", "wildcard_import"} or item is dotted:
                continue
            names = [c for c in item.named_children if c.type in {"dotted_name", "identifier"}]
            imported = _text(names[0], source) if names else "*"
            local = _text(names[-1], source) if item.type == "aliased_import" and len(names) > 1 else imported
            results.append(ImportFact(module, imported, local, _range(item)))
    return results


def _call_reference(node, source: bytes, scope: str | None) -> ReferenceFact | None:
    callee = node.named_children[0] if node.named_children else None
    if callee is None:
        return None
    if callee.type in {"identifier", "type_identifier"}:
        return ReferenceFact("call", _text(callee, source), None, scope, _range(callee))
    if callee.type in {"attribute", "member_expression"}:
        property_node = next((c for c in reversed(callee.named_children) if c.type in {"identifier", "property_identifier"}), None)
        if property_node:
            qualifier = _text(callee, source)[: property_node.start_byte - callee.start_byte].rstrip(".")
            return ReferenceFact("call", _text(property_node, source), qualifier, scope, _range(callee))
    return ReferenceFact("call", _text(callee, source), None, scope, _range(callee))


def analyze_source(source: str, language: str) -> AnalysisFacts:
    """Parse Python or TypeScript-like source into evidence-bearing facts.

    Unsupported language names fail explicitly rather than silently falling back to
    another grammar. References intentionally have no resolved target: resolution
    belongs to the graph layer and may record them as unresolved or ambiguous.
    """
    normalized = _LANGUAGE_ALIASES.get(language.lower(), language.lower())
    if normalized not in {"python", "typescript", "tsx", "javascript", "jsx"}:
        raise ValueError(f"unsupported parser language: {language}")
    raw = source.encode("utf-8")
    root = get_parser(normalized).parse(raw).root_node
    declarations: list[DeclarationFact] = []
    imports: list[ImportFact] = []
    references: list[ReferenceFact] = []
    diagnostics: list[DiagnosticFact] = []

    def visit(node, parent: str | None = None, exported: bool = False) -> None:
        if node.type == "ERROR" or node.is_missing:
            diagnostics.append(DiagnosticFact("syntax error" if node.type == "ERROR" else f"missing {node.type}", _range(node)))
        if node.type in {"import_statement", "import_from_statement"}:
            imports.extend(_imports(node, raw))
        declared = _declaration(node, raw, parent, exported)
        current_parent = parent
        if declared:
            declarations.append(declared)
            current_parent = declared.qualified_name
        if node.type in {"call", "call_expression"}:
            reference = _call_reference(node, raw, parent)
            if reference:
                references.append(reference)
        for child in node.children:
            visit(child, current_parent, exported or node.type == "export_statement")

    visit(root)
    return AnalysisFacts(normalized, PARSER_VERSION, tuple(declarations), tuple(imports), tuple(references), tuple(diagnostics))
