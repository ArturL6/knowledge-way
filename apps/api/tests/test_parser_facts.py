import pytest

from app.parser_facts import PARSER_VERSION, analyze_source


def test_python_facts_preserve_nested_scopes_aliases_calls_and_unicode_bytes():
    source = '''import package.tools as tools
from service.client import invoke as run

class Café(Base):
    def nested(self, value):
        return run(value) + tools.execute(value)
'''
    facts = analyze_source(source, "python")

    assert facts.parser_version == PARSER_VERSION
    assert [(d.qualified_name, d.kind, d.parent_qualified_name) for d in facts.declarations] == [
        ("Café", "class", None),
        ("Café.nested", "function", "Café"),
    ]
    assert [(i.module, i.imported_name, i.local_name) for i in facts.imports] == [
        ("package.tools", None, "tools"),
        ("service.client", "invoke", "run"),
    ]
    assert [(r.target_name, r.qualifier, r.scope_qualified_name) for r in facts.references] == [
        ("run", None, "Café.nested"),
        ("execute", "tools", "Café.nested"),
    ]
    cafe = facts.declarations[0]
    assert cafe.name_range.start_byte == source.encode().index("Café".encode())
    assert cafe.name_range.start_line == 4


def test_typescript_facts_include_exports_import_aliases_and_qualified_calls():
    source = '''import { invoke as run } from "service-client";
export interface Runner { execute(): void }
export class Worker extends Base implements Runner {
  execute() { return run().finish(); }
}
export function launch() { return Worker; }
'''
    facts = analyze_source(source, "ts")

    assert [(d.qualified_name, d.kind, d.exported) for d in facts.declarations] == [
        ("Runner", "interface", True),
        ("Worker", "class", True),
        ("Worker.execute", "method", True),
        ("launch", "function", True),
    ]
    assert [(i.module, i.imported_name, i.local_name) for i in facts.imports] == [
        ("service-client", "invoke", "run"),
    ]
    assert [(r.target_name, r.qualifier, r.scope_qualified_name) for r in facts.references] == [
        ("finish", "run()", "Worker.execute"),
        ("run", None, "Worker.execute"),
    ]


def test_references_are_evidence_only_and_duplicate_names_are_not_resolved():
    facts = analyze_source("def one(): return target()\ndef two(): return target()\n", "python")
    assert [(r.target_name, r.scope_qualified_name) for r in facts.references] == [
        ("target", "one"),
        ("target", "two"),
    ]
    assert not hasattr(facts.references[0], "resolved_target")


def test_syntax_errors_are_reported_and_unsupported_languages_fail_explicitly():
    facts = analyze_source("def broken(:\n    pass\n", "python")
    assert facts.diagnostics
    assert facts.diagnostics[0].range.start_line == 1
    with pytest.raises(ValueError, match="unsupported parser language"):
        analyze_source("x", "go")
