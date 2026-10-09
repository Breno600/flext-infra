"""Native symbolic scans reject rebound and stale import-owner identities.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

import pytest
from flext_tests import tm

from flext_infra.codemod.batch_gates import FlextInfraModGateEngine
from flext_infra.codemod.batch_replacements import FlextInfraModReplacements
from tests import u

# Shared fixture line: the owned-constant read every receiver scenario asserts on.
_OWNED_CI_LINE = (
    "owned = utilities.TestsFlextInfraUtilities.CodegenTestSupport.Ci.value\n"
)


@pytest.fixture
def symbolic_workspace(mod_workspace: Path) -> Path:
    """Provide real Python modules consumed by the native engine and interpreter.

    Returns:
        The resulting ``Path``.
    """
    tests = mod_workspace / "tests"
    (tests / "unit" / "codegen").mkdir(parents=True)
    (tests / "__init__.py").write_text(
        "from tests.utilities import TestsFlextInfraUtilities as u\n",
        encoding="utf-8",
    )
    (tests / "utilities.py").write_text(
        "class TestsFlextInfraUtilities:\n"
        "    class CodegenTestSupport:\n"
        "        class Ci:\n"
        "            value = 'owned'\n",
        encoding="utf-8",
    )
    return mod_workspace


class TestsFlextInfraSymbolicBindingPublication:
    """Binding evidence must survive until the guarded phase's source barrier."""

    @staticmethod
    @pytest.mark.slow
    @pytest.mark.parametrize("receiver", ["source", "replacement", "intermediate"])
    def test_rebound_receiver_is_diagnostic_without_mutation(
        symbolic_workspace: Path,
        receiver: str,
    ) -> None:
        """Test rebound receiver is diagnostic without mutation."""
        root = symbolic_workspace
        consumer = root / "tests" / "unit" / "codegen" / "consumer.py"
        before = (
            "from tests import u, utilities\n"
            "import tests.utilities as canonical\n"
            "class Independent:\n"
            "    class TestsFlextInfraUtilities:\n"
            "        class CodegenTestSupport:\n"
            "            class Ci:\n"
            "                value = 'independent'\n"
        )
        if receiver == "source":
            before += (
                "utilities = Independent\n" + _OWNED_CI_LINE + "utilities = canonical\n"
            )
        elif receiver == "replacement":
            before += (
                "u = Independent.TestsFlextInfraUtilities\n"
                + _OWNED_CI_LINE
                + "u = canonical.TestsFlextInfraUtilities\n"
            )
        else:
            before += (
                "original = utilities.TestsFlextInfraUtilities\n"
                "utilities.TestsFlextInfraUtilities = "
                "Independent.TestsFlextInfraUtilities\n"
                + _OWNED_CI_LINE
                + "utilities.TestsFlextInfraUtilities = original\n"
            )
        before += "print(owned)\n"
        consumer.write_text(before, encoding="utf-8")
        u.Tests.git_bootstrap(root, ("add", "tests"))
        baseline = tm.ok(
            u.Cli.run((sys.executable, "-m", "tests.unit.codegen.consumer"), cwd=root)
        )
        report = tm.ok(FlextInfraModGateEngine.scan(root, fix=False))
        findings = tuple(
            entry
            for entry in report.entries
            if entry.rule_id.startswith("codegen-test-public-utility-")
        )
        tm.that(
            any(
                entry.rule_id == "codegen-test-public-utility-binding-required"
                for entry in findings
            ),
            eq=True,
        )
        tm.that(all(not entry.actionable for entry in findings), eq=True)
        tm.ok(
            FlextInfraModReplacements.publish(
                root, FlextInfraModGateEngine.recounted(findings)
            )
        )
        tm.that(consumer.read_text(encoding="utf-8"), eq=before)
        after = tm.ok(
            u.Cli.run((sys.executable, "-m", "tests.unit.codegen.consumer"), cwd=root)
        )
        tm.that(after.stdout, eq=baseline.stdout)

    @staticmethod
    @pytest.mark.slow
    @pytest.mark.parametrize("scope", ["module", "enclosing"])
    def test_rebound_outcome_receiver_is_never_an_enum_fixer(
        symbolic_workspace: Path,
        scope: str,
    ) -> None:
        """Test rebound outcome receiver is never an enum fixer."""
        root = symbolic_workspace
        consumer = root / "tests" / "unit" / "codegen" / "consumer.py"
        source = (
            "from flext_infra import c as canonical_c\n"
            "class Independent:\n"
            "    class Infra:\n"
            "        class ToolOutcome:\n"
            "            ERROR = 'independent'\n"
        )
        if scope == "module":
            source += (
                "c = Independent\n"
                "observed = c.Infra.ToolOutcome.ERROR == 'TOOL_ERROR'\n"
                "c = canonical_c\n"
                "print(observed)\n"
            )
        else:
            source += (
                "def outer():\n"
                "    c = Independent\n"
                "    def inner():\n"
                "        return c.Infra.ToolOutcome.ERROR == 'TOOL_ERROR'\n"
                "    observed = inner()\n"
                "    c = canonical_c\n"
                "    return observed\n"
                "print(outer())\n"
            )
        consumer.write_text(source, encoding="utf-8")
        u.Tests.git_bootstrap(root, ("add", "tests"))
        baseline = tm.ok(
            u.Cli.run((sys.executable, "-m", "tests.unit.codegen.consumer"), cwd=root)
        )
        report = tm.ok(FlextInfraModGateEngine.scan(root, fix=False))
        findings = tuple(
            entry
            for entry in report.entries
            if entry.rule_id.startswith("gate-tool-error-typed-")
        )
        tm.that(
            sum(
                entry.rule_id == "gate-tool-error-typed-binding-required"
                for entry in findings
            ),
            eq=1,
        )
        tm.that(all(not entry.actionable for entry in findings), eq=True)
        tm.ok(
            FlextInfraModReplacements.publish(
                root, FlextInfraModGateEngine.recounted(findings)
            )
        )
        tm.that(consumer.read_text(encoding="utf-8"), eq=source)
        after = tm.ok(
            u.Cli.run((sys.executable, "-m", "tests.unit.codegen.consumer"), cwd=root)
        )
        tm.that(after.stdout, eq=baseline.stdout)

    @staticmethod
    @pytest.mark.slow
    def test_dependency_only_drift_refuses_every_candidate_before_writes(
        symbolic_workspace: Path,
    ) -> None:
        """Test dependency only drift refuses every candidate before writes."""
        root = symbolic_workspace
        consumers = tuple(
            root / "tests" / "unit" / "codegen" / name
            for name in ("consumer.py", "peer.py")
        )
        source = "from tests import u, utilities\n" + _OWNED_CI_LINE + "print(owned)\n"
        for path in consumers:
            path.write_text(source, encoding="utf-8")
        u.Tests.git_bootstrap(root, ("add", "tests"))
        scanned = tm.ok(FlextInfraModGateEngine.scan(root, fix=False))
        findings = tuple(
            entry
            for entry in scanned.entries
            if entry.rule_id == "codegen-test-public-utility-namespace"
        )
        tm.that(len(findings), eq=len(consumers))
        initializer = root / "tests" / "__init__.py"
        tm.that(
            all(
                initializer in {state.path for state in entry.binding_states}
                for entry in findings
            ),
            eq=True,
        )
        changed = (
            "class Independent:\n"
            "    class CodegenTestSupport:\n"
            "        class Ci:\n"
            "            value = 'independent'\n"
            "u = Independent\n"
        )
        initializer.write_text(changed, encoding="utf-8")
        before = tuple(path.read_bytes() for path in consumers)
        published = FlextInfraModReplacements.publish(
            root, FlextInfraModGateEngine.recounted(findings)
        )
        tm.that(published.failure, eq=True)
        tm.that(tuple(path.read_bytes() for path in consumers), eq=before)
        tm.that(initializer.read_text(encoding="utf-8"), eq=changed)
        runtime = tm.ok(
            u.Cli.run((sys.executable, "-m", "tests.unit.codegen.consumer"), cwd=root)
        )
        tm.that(runtime.stdout.strip(), eq="owned")

    @staticmethod
    @pytest.mark.slow
    def test_type_alias_payloads_and_legacy_comparisons_remain_visible(
        symbolic_workspace: Path,
    ) -> None:
        """Test type alias payloads and legacy comparisons remain visible."""
        root = symbolic_workspace
        consumer = root / "tests" / "unit" / "codegen" / "consumer.py"
        source = (
            "from typing import Annotated, Literal\n"
            "from tests import u, utilities\n"
            "class Result:\n    code = 'TOOL_ERROR'\n"
            "result = Result()\n"
            "type Pep = Annotated[str, "
            "utilities.TestsFlextInfraUtilities.CodegenTestSupport.Ci]\n"
            "Assigned = Annotated[str, "
            "utilities.TestsFlextInfraUtilities.CodegenTestSupport.Ci]\n"
            "type Actual = utilities.TestsFlextInfraUtilities.CodegenTestSupport.Ci\n"
            "type LiteralData = Literal['TOOL_ERROR']\n"
            "type ComparedMetadata = Annotated[str, result.code == 'TOOL_ERROR']\n"
            'payload = \'{"status": "TOOL_ERROR"}\'\n'
            "ordinary = 'TOOL_ERROR'\n"
            "forward = result.code == 'TOOL_ERROR'\n"
            "reverse = 'TOOL_ERROR' == result.code\n"
            "different = result.code != 'TOOL_ERROR'\n"
        )
        consumer.write_text(source, encoding="utf-8")
        import_only = consumer.with_name("import_only.py")
        import_only.write_text("import tests.utilities\n", encoding="utf-8")
        u.Tests.git_bootstrap(root, ("add", "tests"))
        report = tm.ok(FlextInfraModGateEngine.scan(root, fix=False))
        symbolic = tuple(
            entry
            for entry in report.entries
            if entry.rule_id.startswith((
                "codegen-test-public-utility-",
                "gate-tool-error-typed-",
            ))
        )
        tm.that(sum(entry.actionable for entry in symbolic), eq=1)
        tm.that(
            sum(
                entry.rule_id == "gate-tool-error-typed-binding-required"
                for entry in symbolic
            ),
            eq=3,
        )
        tm.that(
            sum(
                entry.rule_id == "codegen-test-public-utility-import-semantic-required"
                for entry in symbolic
            ),
            eq=1,
        )
        tm.ok(
            FlextInfraModReplacements.publish(
                root, FlextInfraModGateEngine.recounted(symbolic)
            )
        )
        after = consumer.read_text(encoding="utf-8")
        protected = {
            "Pep",
            "Assigned",
            "LiteralData",
            "ComparedMetadata",
            "payload",
            "ordinary",
            "forward",
            "reverse",
            "different",
        }
        for name in protected:
            original = next(
                node
                for node in ast.walk(ast.parse(source))
                if (
                    (isinstance(node, ast.TypeAlias) and node.name.id == name)
                    or (
                        isinstance(node, ast.Assign)
                        and any(
                            isinstance(target, ast.Name) and target.id == name
                            for target in node.targets
                        )
                    )
                )
            )
            preserved = next(
                node
                for node in ast.walk(ast.parse(after))
                if (
                    (isinstance(node, ast.TypeAlias) and node.name.id == name)
                    or (
                        isinstance(node, ast.Assign)
                        and any(
                            isinstance(target, ast.Name) and target.id == name
                            for target in node.targets
                        )
                    )
                )
            )
            tm.that(ast.dump(preserved), eq=ast.dump(original))
        actual = next(
            node
            for node in ast.walk(ast.parse(after))
            if isinstance(node, ast.TypeAlias) and node.name.id == "Actual"
        )
        tm.that(ast.unparse(actual.value), eq="u.CodegenTestSupport.Ci")
        tm.that(import_only.read_text(encoding="utf-8"), eq="import tests.utilities\n")
