"""Execute migrated dynamic environment boundaries with real typed policy.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

import inspect
import sys
from pathlib import Path

import pytest
from flext_tests import tm

from flext_infra import config, infra, settings
from tests import c, m, u


class TestsFlextInfraDynamicEnvironmentCutover:
    """Preserve unset, empty, and populated values without default normalization."""

    @pytest.mark.parametrize("value", [None, "", "literal value"])
    @pytest.mark.parametrize("required", [False, True])
    def test_real_settings_consumer_preserves_lookup_contract(
        self,
        tmp_path: Path,
        value: str | None,
        *,
        required: bool,
    ) -> None:
        """Test real settings consumer preserves lookup contract."""
        root, package = u.Tests.create_lazy_init_workspace(tmp_path)
        path = package / "consumer.py"
        access = (
            "os.environ[str(policy.data_home_environment_variable)]"
            if required
            else "os.environ.get(str(policy.data_home_environment_variable))"
        )
        source = (
            "import os\nimport sys\nfrom flext_infra import config\n"
            "def read_value():\n"
            "    policy = config.Infra.codegen.make.mypy_cache\n"
            f"    return {access}\n"
            "if sys.argv[1] == 'missing-required':\n"
            "    try:\n"
            "        read_value()\n"
            "    except KeyError as error:\n"
            "        assert error.args == (str(config.Infra.codegen.make.mypy_cache"
            ".data_home_environment_variable),)\n"
            "    else:\n"
            "        raise AssertionError('required key was defaulted')\n"
            "else:\n"
            "    print(repr(read_value()))\n"
        )
        settings_path = Path(inspect.getfile(type(settings)))
        sources = {
            path: source,
            settings_path: settings_path.read_text(encoding="utf-8"),
        }
        finding = self._finding(path.relative_to(root), access)
        with infra.rope_workspace(root) as rope:
            edits = tm.ok(
                u.Infra.plan_semantic_cutover(
                    c.Infra.SemanticCutoverPhase.DYNAMIC_ENVIRONMENT,
                    rope_workspace=rope,
                    sources=sources,
                    findings=(finding,),
                ),
            )
            tm.that(len(edits), eq=1)
            sources[path] = edits[0].updated_source
            remaining = tm.ok(
                u.Infra.plan_semantic_cutover(
                    c.Infra.SemanticCutoverPhase.DYNAMIC_ENVIRONMENT,
                    rope_workspace=rope,
                    sources=sources,
                    findings=(finding,),
                ),
            )
        tm.that(remaining, empty=True)
        path.write_text(sources[path], encoding="utf-8")
        key = str(config.Infra.codegen.make.mypy_cache.data_home_environment_variable)
        environment = {} if value is None else {key: value}
        mode = "missing-required" if required and value is None else "value"
        output = tm.ok(
            u.Cli.run_raw(
                (sys.executable, "-I", str(path), mode),
                env=environment,
                remove_env_keys=(key,) if value is None else (),
            ),
        )
        tm.that(u.Cli.process_succeeded(output.outcome), eq=True, msg=output.stderr)
        tm.that(output.stdout, eq="" if mode == "missing-required" else f"{value!r}\n")

    @pytest.mark.parametrize(
        "access",
        ["os.environ.get('STATIC_KEY')", "os.environ.get(unknown_key)"],
    )
    def test_unproven_environment_key_stays_red(
        self,
        tmp_path: Path,
        access: str,
    ) -> None:
        """Test unproven environment key stays red."""
        root, package = u.Tests.create_lazy_init_workspace(tmp_path)
        path = package / "consumer.py"
        source = f"import os\ndef value(unknown_key: str):\n    return {access}\n"
        with infra.rope_workspace(root) as rope:
            result = u.Infra.plan_semantic_cutover(
                c.Infra.SemanticCutoverPhase.DYNAMIC_ENVIRONMENT,
                rope_workspace=rope,
                sources={path: source},
                findings=(self._finding(path.relative_to(root), access),),
            )
        tm.fail(result, has="typed-config provenance")

    @staticmethod
    def _finding(path: Path, access: str) -> m.Infra.ModScanFinding:
        rule = c.Infra.SEMANTIC_CUTOVER_RULE_IDS[
            c.Infra.SemanticCutoverPhase.DYNAMIC_ENVIRONMENT
        ]
        return m.Infra.ModScanFinding(
            rule_file=f"{rule}.yml",
            rule_id=rule,
            repository="fixture",
            file=path,
            range={},
            text=access,
            actionable=False,
            classification=c.Infra.ModScanFindingClass.DETECTION_ONLY,
            payload={},
        )
