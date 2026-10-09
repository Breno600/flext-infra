"""Public utility evidence for semantic API-alias cutovers.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from pathlib import Path

import pytest
from flext_tests import tm

from flext_infra import c, infra, m, u


class TestsFlextInfraApiAliasCutover:
    """Exercise owner-first alias removal only through ``u.Infra``."""

    @staticmethod
    @pytest.mark.parametrize(
        "consumer_source",
        [
            "from flext_sample.api import sample\n\nfacade = sample\n",
            (
                "if condition:\n"
                "    from flext_sample.api import sample\n"
                "else:\n"
                "    from flext_sample import sample\n"
                "facade = sample\n"
            ),
        ],
    )
    def test_rewires_consumer_before_removing_owner(
        tmp_path: Path,
        consumer_source: str,
    ) -> None:
        """Plan the complete owner/export/import/reference cutover together."""
        owner = tmp_path / "flext-sample/src/flext_sample/api.py"
        consumer = tmp_path / "flext-sample/tests/test_api.py"
        sources = {
            owner: (
                "class FlextSample:\n"
                "    pass\n\n"
                "sample = FlextSample\n"
                "facade = sample\n"
                '__all__ = ["FlextSample", "sample"]\n'
            ),
            consumer: consumer_source,
        }
        finding = m.Infra.ModScanFinding(
            rule_file="ban-compat-alias.yml",
            rule_id="ban-compat-alias",
            repository="flext-sample",
            file=owner.relative_to(tmp_path),
            range={},
            text="sample = FlextSample",
            actionable=False,
            classification=c.Infra.ModScanFindingClass.DETECTION_ONLY,
            payload={},
        )

        with infra.rope_workspace(tmp_path) as rope:
            planned = u.Infra.plan_semantic_cutover(
                c.Infra.SemanticCutoverPhase.COMPAT_ALIAS,
                rope_workspace=rope,
                sources=sources,
                findings=(finding,),
            )
        tm.ok(planned)
        edits = planned.value
        by_path = {edit.file_path: edit.updated_source for edit in edits}

        tm.that(len(edits), eq=2)
        tm.that(by_path[owner], lacks="sample = FlextSample")
        tm.that(by_path[owner], lacks='"sample"')
        tm.that(by_path[owner], has="facade = FlextSample")
        tm.that(by_path[consumer], has="from flext_sample.api import FlextSample")
        tm.that(by_path[consumer], has="facade = FlextSample")
        tm.that(by_path[consumer], lacks="import sample")

    @staticmethod
    @pytest.mark.parametrize(
        ("module", "receiver"),
        [
            ("flext_sample.api as sample_api", "sample_api"),
            ("flext_sample as sample_api", "sample_api"),
            ("flext_sample.api", "flext_sample.api"),
        ],
    )
    def test_module_attributes_require_import_identity(
        tmp_path: Path,
        module: str,
        receiver: str,
    ) -> None:
        """Rewrite proven module reads without changing shadowed or literal uses."""
        owner = tmp_path / "flext-sample/src/flext_sample/api.py"
        consumer = tmp_path / "flext-sample/tests/test_api.py"
        binding = receiver.split(".", maxsplit=1)[0]
        unchanged = (
            f"def shadowed({binding}):\n"
            f"    return {receiver}.sample\n\n"
            "def rebound(values):\n"
            f"    {binding} = values\n"
            f"    return {receiver}.sample\n\n"
            "def homonym():\n"
            f"    import unrelated as {binding}\n"
            f"    return {receiver}.sample\n\n"
            "def comprehension(values):\n"
            f"    return [{receiver}.sample for {binding} in values]\n\n"
            'payload = "sample_api.sample"\n'
            'literal = Literal["sample_api.sample"]\n'
            'metadata = Annotated[str, "sample_api.sample"]\n'
            'reflection_name = "sample"\n'
            f'reflected_target = getattr({receiver}, "FlextSample")\n'
            f'other_attribute = getattr({receiver}, "__name__")\n'
            f"def reflective_shadowed({binding}):\n"
            f'    return getattr({receiver}, "sample")\n\n'
            "def getter_shadowed(getattr, value):\n"
            '    return getattr(value, "sample")\n\n'
            "def local_getter(value):\n"
            "    def getattr(value, name):\n"
            "        return name\n"
            '    return getattr(value, "sample")\n\n'
            "def reflective_homonym():\n"
            f"    import unrelated as {binding}\n"
            f'    return getattr({receiver}, "sample")\n\n'
            f"def reflective_dynamic_shadowed({binding}, attribute):\n"
            f"    return getattr({receiver}, attribute)\n"
        )
        sources = {
            owner: (
                "class FlextSample:\n"
                "    pass\n\n"
                "sample = FlextSample\n"
                '__all__ = ["FlextSample", "sample"]\n'
            ),
            consumer: (
                f"import {module}\n"
                "from typing import Annotated, Literal\n\n"
                f"facade = {receiver}.sample\n\n"
                "def local_import():\n"
                f"    import {module}\n"
                f"    return {receiver}.sample\n\n" + unchanged
            ),
        }
        finding = m.Infra.ModScanFinding(
            rule_file="ban-compat-alias.yml",
            rule_id="ban-compat-alias",
            repository="flext-sample",
            file=owner.relative_to(tmp_path),
            range={},
            text="sample = FlextSample",
            actionable=False,
            classification=c.Infra.ModScanFindingClass.DETECTION_ONLY,
            payload={},
        )

        with infra.rope_workspace(tmp_path) as rope:
            planned = u.Infra.plan_semantic_cutover(
                c.Infra.SemanticCutoverPhase.COMPAT_ALIAS,
                rope_workspace=rope,
                sources=sources,
                findings=(finding,),
            )
            tm.ok(planned)
            rewritten = {edit.file_path: edit.updated_source for edit in planned.value}
            tm.that(len(rewritten), eq=2)
            tm.that(rewritten[consumer], has=f"facade = {receiver}.FlextSample")
            tm.that(
                rewritten[consumer],
                has=f"    import {module}\n    return {receiver}.FlextSample",
            )
            tm.that(rewritten[consumer], has=unchanged)
            tm.that(rewritten[owner], lacks="sample = FlextSample")
            converged = u.Infra.plan_semantic_cutover(
                c.Infra.SemanticCutoverPhase.COMPAT_ALIAS,
                rope_workspace=rope,
                sources=rewritten,
                findings=(finding,),
            )
        tm.ok(converged)
        tm.that(converged.value, eq=())

    @staticmethod
    @pytest.mark.parametrize(
        ("consumer_source", "diagnostic"),
        [
            (
                (
                    "if condition:\n    from flext_sample.api import sample\n"
                    "else:\n    from unrelated.api import sample\nfacade = sample\n"
                ),
                "ambiguous qualified alias",
            ),
            (
                (
                    "from flext_sample.api import sample\n"
                    "if condition:\n    sample = value\nfacade = sample\n"
                ),
                "ambiguous qualified alias",
            ),
            (
                "from flext_sample.api import sample as selected\nfacade = selected\n",
                "ambiguous compatibility import alias",
            ),
            (
                "from flext_sample.api import sample as sample\nfacade = sample\n",
                "ambiguous compatibility import alias",
            ),
            ("import flext_sample.api as api\nmodule = api\n", "module escape"),
            ("import flext_sample.api\nmodule = flext_sample.api\n", "module escape"),
            (
                "import flext_sample.api as api\ndef expose():\n    return api\n",
                "module escape",
            ),
            ("import flext_sample.api as api\nconsume(api)\n", "module escape"),
            ("import flext_sample.api as api\nmodules = [api]\n", "module escape"),
            (
                (
                    "import flext_sample.api as api\n"
                    'def opaque(getattr):\n    return getattr(api, "sample")\n'
                ),
                "module escape",
            ),
            (
                (
                    "def ambiguous(condition):\n"
                    "    if condition:\n        import flext_sample.api as sample_api\n"
                    "    else:\n        import unrelated.api as sample_api\n"
                    "    return sample_api.sample\n"
                ),
                "ambiguous qualified alias",
            ),
            (
                (
                    "import flext_sample.api\n"
                    "if condition:\n    flext_sample = value\n"
                    "facade = flext_sample.api.sample\n"
                ),
                "ambiguous qualified alias",
            ),
            (
                (
                    "import flext_sample.api\n"
                    "if condition:\n    import unrelated as flext_sample\n"
                    'facade = getattr(flext_sample.api, "sample")\n'
                ),
                "ambiguous qualified alias",
            ),
            (
                (
                    "import flext_sample.api as api\nimport builtins\n"
                    "def opaque(builtins):\n"
                    '    return builtins.getattr(api, "FlextSample")\n'
                ),
                "module escape",
            ),
        ],
    )
    def test_unproven_consumers_reject_complete_plan(
        tmp_path: Path,
        consumer_source: str,
        diagnostic: str,
    ) -> None:
        """Refuse mixed bindings, import-as bindings and opaque module escapes."""
        owner = tmp_path / "flext-sample/src/flext_sample/api.py"
        consumer = tmp_path / "flext-sample/tests/test_api.py"
        sources = {
            owner: (
                "class FlextSample:\n"
                "    pass\n\n"
                "sample = FlextSample\n"
                '__all__ = ["FlextSample", "sample"]\n'
            ),
            consumer: consumer_source,
        }
        finding = m.Infra.ModScanFinding(
            rule_file="ban-compat-alias.yml",
            rule_id="ban-compat-alias",
            repository="flext-sample",
            file=owner.relative_to(tmp_path),
            range={},
            text="sample = FlextSample",
            actionable=False,
            classification=c.Infra.ModScanFindingClass.DETECTION_ONLY,
            payload={},
        )

        with infra.rope_workspace(tmp_path) as rope:
            planned = u.Infra.plan_semantic_cutover(
                c.Infra.SemanticCutoverPhase.COMPAT_ALIAS,
                rope_workspace=rope,
                sources=sources,
                findings=(finding,),
            )
        tm.fail(planned, has=diagnostic)

    @staticmethod
    @pytest.mark.parametrize(
        ("module_import", "receiver"),
        [
            ("import flext_sample.api as sample_api", "sample_api"),
            ("import flext_sample as sample_api", "sample_api"),
            ("from flext_sample import api as sample_api", "sample_api"),
            ("import flext_sample.api", "flext_sample.api"),
        ],
    )
    @pytest.mark.parametrize(
        "reflection",
        [
            'getattr(sample_api, "sample")',
            'getattr(sample_api, "sample", None)',
            'getattr(sample_api, "sam" "ple")',
            "getattr(sample_api, attribute)",
            "getattr(sample_api, *attributes)",
            'hasattr(sample_api, "sample")',
            'setattr(sample_api, "sample", None)',
            'delattr(sample_api, "sample")',
            'builtins.getattr(sample_api, "sample")',
            'lookup(sample_api, "sample")',
        ],
    )
    def test_reflective_alias_access_rejects_complete_plan(
        tmp_path: Path,
        module_import: str,
        receiver: str,
        reflection: str,
    ) -> None:
        """Retain the complete owner when a proven reflective consumer is unsafe."""
        owner = tmp_path / "flext-sample/src/flext_sample/api.py"
        consumer = tmp_path / "flext-sample/tests/test_api.py"
        sources = {
            owner: (
                "class FlextSample:\n"
                "    pass\n\n"
                "sample = FlextSample\n"
                '__all__ = ["FlextSample", "sample"]\n'
            ),
            consumer: (
                "import builtins\n"
                "from builtins import getattr as lookup\n"
                f"{module_import}\n\n"
                "def reflective(attribute, attributes):\n"
                f"    return {reflection.replace('sample_api', receiver)}\n"
            ),
        }
        finding = m.Infra.ModScanFinding(
            rule_file="ban-compat-alias.yml",
            rule_id="ban-compat-alias",
            repository="flext-sample",
            file=owner.relative_to(tmp_path),
            range={},
            text="sample = FlextSample",
            actionable=False,
            classification=c.Infra.ModScanFindingClass.DETECTION_ONLY,
            payload={},
        )

        with infra.rope_workspace(tmp_path) as rope:
            planned = u.Infra.plan_semantic_cutover(
                c.Infra.SemanticCutoverPhase.COMPAT_ALIAS,
                rope_workspace=rope,
                sources=sources,
                findings=(finding,),
            )
        tm.fail(planned, has="reflective")
