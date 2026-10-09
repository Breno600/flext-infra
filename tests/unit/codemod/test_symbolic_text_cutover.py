"""Resolved AST cutovers preserve payloads and independent spelling owners.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest
from flext_tests import tm

from flext_infra import c, m, t
from flext_infra.codemod import FlextInfraModTextGateEngine
from flext_infra.codemod.batch_gates import FlextInfraModGateEngine
from flext_infra.codemod.batch_replacements import FlextInfraModReplacements
from tests import u


class TestsFlextInfraSymbolicTextCutover:
    """Exercise native findings, binding admission, and public publication."""

    @staticmethod
    def test_occurrence_identity_is_lexical_and_immutable(mod_workspace: Path) -> None:
        """Identical spelling in another scope never borrows a module binding."""
        owner = mod_workspace / "definer.py"
        owner.write_text("class Public:\n    pass\nu = Public\n", encoding="utf-8")
        consumer = mod_workspace / "consumer.py"
        source = (
            "from definer import Public, u\n"
            "note = '\u00e9'\n"
            "value = Public\n"
            "def independent(Public):\n"
            "    return Public\n"
        )
        consumer.write_text(source, encoding="utf-8")
        rule = m.Infra.CodemodRule(
            id="binding-probe",
            digest="probe",
            provider="probe",
            resource=Path("probe.yml"),
            fixable=True,
            context=(
                m.Infra.CodemodContextCondition(
                    variable="OWNER",
                    predicate=c.Infra.CodemodContextPredicate.RESOLVED_SYMBOL,
                    arg=("definer", "Public"),
                    holds=True,
                ),
                m.Infra.CodemodContextCondition(
                    variable="OWNER",
                    predicate=c.Infra.CodemodContextPredicate.SAME_BINDING,
                    arg=("u",),
                    holds=True,
                ),
            ),
        )
        facts = u.Infra.codemod_project_facts(mod_workspace, (rule,))
        for start, expected in (
            (source.index("Public", source.index("value =")), True),
            (source.rindex("Public"), False),
        ):
            start_byte = len(source[:start].encode("utf-8"))
            capture: t.JsonMapping = {
                "OWNER": {
                    "text": "Public",
                    "range": {
                        "byteOffset": {
                            "start": start_byte,
                            "end": start_byte + len("Public"),
                        }
                    },
                },
            }
            for _ in range(2):
                tm.that(
                    u.Infra.codemod_context_admits(
                        m.Infra.CodemodAdmission(
                            root=mod_workspace,
                            rule=rule,
                            file_path=consumer,
                            captures=capture,
                            facts=facts,
                        ),
                    ),
                    eq=expected,
                )
        tm.that(consumer.read_text(encoding="utf-8"), eq=source)
        closed = u.Infra.codemod_binding_snapshot(
            mod_workspace,
            (tm.ok(u.Cli.atomic_read_binary_file_state(consumer, required=True)),),
            ("definer",),
        )
        start = source.index("Public", source.index("value ="))
        start_byte = len(source[:start].encode("utf-8"))
        positive: t.JsonMapping = {
            "OWNER": {
                "text": "Public",
                "range": {
                    "byteOffset": {
                        "start": start_byte,
                        "end": start_byte + len("Public"),
                    }
                },
            }
        }
        owner.write_text(
            "class Public:\n    pass\nclass Independent:\n    pass\nu = Independent\n",
            encoding="utf-8",
        )
        tm.that(
            u.Infra.codemod_context_admits(
                m.Infra.CodemodAdmission(
                    root=mod_workspace,
                    rule=rule,
                    file_path=consumer,
                    captures=positive,
                    facts=facts,
                    snapshot=closed,
                ),
            ),
            eq=True,
        )
        tm.that(
            u.Infra.codemod_context_admits(
                m.Infra.CodemodAdmission(
                    root=mod_workspace,
                    rule=rule,
                    file_path=consumer,
                    captures=positive,
                    facts=facts,
                ),
            ),
            eq=False,
        )
        tm.that(consumer.read_text(encoding="utf-8"), eq=source)

    @staticmethod
    def test_binding_receipt_cannot_resolve_another_occurrence(
        mod_workspace: Path,
    ) -> None:
        """A stale span is rejected instead of falling back to another same name."""
        consumer = mod_workspace / "consumer.py"
        consumer.write_text("value = 1\n", encoding="utf-8")
        rule = m.Infra.CodemodRule(
            id="binding-probe",
            digest="probe",
            provider="probe",
            resource=Path("probe.yml"),
            fixable=True,
            context=(
                m.Infra.CodemodContextCondition(
                    variable="OWNER",
                    predicate=c.Infra.CodemodContextPredicate.SAME_BINDING,
                    arg=("value",),
                    holds=True,
                ),
            ),
        )
        with pytest.raises(ValueError, match="binding capture differs from source"):
            u.Infra.codemod_context_admits(
                m.Infra.CodemodAdmission(
                    root=mod_workspace,
                    rule=rule,
                    file_path=consumer,
                    captures={
                        "OWNER": {
                            "text": "other",
                            "range": {"byteOffset": {"start": 0, "end": 5}},
                        }
                    },
                    facts=u.Infra.codemod_project_facts(mod_workspace, (rule,)),
                ),
            )
        tm.that(consumer.read_text(encoding="utf-8"), eq="value = 1\n")

    @staticmethod
    @pytest.mark.slow
    @pytest.mark.parametrize("binding", ["same", "absent", "independent"])
    def test_packaged_cutover_preserves_json_and_same_spelling_owners(
        mod_workspace: Path,
        binding: str,
    ) -> None:
        """The real legacy payload survives while proven code references migrate."""
        tests = mod_workspace / "tests"
        codegen = tests / "unit" / "codegen"
        codegen.mkdir(parents=True)
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
        consumer = codegen / "consumer.py"
        imports = (
            "from tests import u, utilities\n"
            if binding == "same"
            else "from tests import utilities\n"
        )
        separate = (
            "class SeparateFacade:\n    pass\nu = SeparateFacade\n"
            if binding == "independent"
            else ""
        )
        source = (
            '"""utilities.TestsFlextInfraUtilities.CodegenTestSupport.Ci"""\n'
            "from __future__ import annotations\n"
            "import json\n"
            "from typing import Annotated, Literal\n"
            f"{imports}{separate}"
            "from flext_infra import c\n"
            '\npayload = \'{"status": "TOOL_ERROR"}\'\n'
            'spelling = "utilities.TestsFlextInfraUtilities.CodegenTestSupport.Ci"\n'
            'tag: Literal["utilities.TestsFlextInfraUtilities.CodegenTestSupport.Ci"]\n'
            "meta: Annotated[str, "
            '"utilities.TestsFlextInfraUtilities.CodegenTestSupport.Ci"]\n'
            "identity_metadata: Annotated[str, "
            "utilities.TestsFlextInfraUtilities.CodegenTestSupport.Ci]\n"
            "owned = utilities.TestsFlextInfraUtilities.CodegenTestSupport.Ci.value\n"
            'outcome = c.Infra.ToolOutcome.ERROR == "TOOL_ERROR"\n'
            "class Other:\n"
            "    class TestsFlextInfraUtilities:\n"
            "        class CodegenTestSupport:\n"
            "            class Ci:\n"
            "                value = 'independent'\n"
            "def independent(utilities):\n"
            "    return utilities.TestsFlextInfraUtilities."
            "CodegenTestSupport.Ci.value\n"
            "print(json.dumps([json.loads(payload), owned, independent(Other), "
            "spelling, __doc__, outcome]))\n"
        )
        consumer.write_text(source, encoding="utf-8")
        u.Tests.git_bootstrap(mod_workspace, ("add", "tests"))
        scanned = tm.ok(FlextInfraModGateEngine.scan(mod_workspace, fix=False))
        ids = {"codegen-test-public-utility-namespace", "gate-tool-error-typed-code"}
        selected = FlextInfraModGateEngine.recounted(
            tuple(entry for entry in scanned.entries if entry.rule_id in ids)
        )
        # The provider's c lives outside this synthetic closed project. Its
        # NoProject inference is explicitly unsupported, never a guessed fixer.
        tm.that(selected.actionable, eq=1 if binding == "same" else 0)
        binding_findings = tuple(
            entry
            for entry in scanned.entries
            if entry.rule_id == "codegen-test-public-utility-binding-required"
        )
        tm.that(len(binding_findings), eq=0 if binding == "same" else 1)
        tm.that(all(not entry.actionable for entry in binding_findings), eq=True)
        tm.that(consumer.read_text(encoding="utf-8"), eq=source)
        tm.ok(FlextInfraModReplacements.publish(mod_workspace, selected))
        published = consumer.read_bytes()
        output = tm.ok(
            u.Cli.run(
                (sys.executable, "-m", "tests.unit.codegen.consumer"),
                cwd=mod_workspace,
            )
        )
        observed = json.loads(output.stdout)
        tm.that(observed[0], eq={"status": "TOOL_ERROR"})
        tm.that(observed[1:3], eq=["owned", "independent"])
        tm.that(observed[3], eq=observed[4])
        tm.that(observed[5], eq=c.Infra.ToolOutcome.ERROR == "TOOL_ERROR")
        remaining = tm.ok(FlextInfraModGateEngine.scan(mod_workspace, fix=False))
        tm.that(
            tuple(entry for entry in remaining.entries if entry.rule_id in ids),
            empty=True,
        )
        tm.that(consumer.read_bytes(), eq=published)

    @staticmethod
    def test_packaged_text_phase_preserves_the_json_counterexample(
        mod_workspace: Path,
    ) -> None:
        """Python syntax is insufficient: the actual consumer must still parse JSON."""
        project = mod_workspace / c.PYPROJECT_FILENAME
        project.write_text(
            project.read_text(encoding="utf-8").replace(
                'name = "mod-workspace"', 'name = "flext-infra"'
            ),
            encoding="utf-8",
        )
        guide = mod_workspace / "docs" / "guides" / "testing.md"
        guide.parent.mkdir(parents=True)
        guide.write_text("", encoding="utf-8")
        consumer = mod_workspace / "tests" / "payload.py"
        consumer.parent.mkdir(exist_ok=True)
        consumer.write_text(
            "import json\n"
            'payload = \'{"status": "TOOL_ERROR"}\'\n'
            "print(json.loads(payload)['status'])\n",
            encoding="utf-8",
        )
        original = consumer.read_bytes()
        tm.ok(FlextInfraModTextGateEngine.scan(mod_workspace, fix=True))
        tm.that(consumer.read_bytes(), eq=original)
        result = tm.ok(u.Cli.run((sys.executable, str(consumer)), cwd=mod_workspace))
        tm.that(result.stdout.strip(), eq="TOOL_ERROR")
