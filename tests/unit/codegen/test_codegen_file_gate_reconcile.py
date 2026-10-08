"""Rendered contract for the fleet-wide file-gate verb and the setup lock law.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from pathlib import Path

import pytest
from flext_tests import tm

from flext_infra import config
from flext_infra.codegen import FlextInfraCodegenConform
from tests import c, m, u

pytestmark = [pytest.mark.slow]


class TestsFlextInfraFileGateAndReconcileMakefile:
    """`file-gate` reaches every profile; setup never writes the lock.

    The fast per-file pre-gate (operator P0, val2026100417xx) is a fleet
    surface declared once in the codegen SSOT. The `make setup` lifecycle
    never rebuilds `mise.lock`: locks update only through `make upg`
    (operator P0, flext-k538b), and the drift branch warns and installs
    unlocked instead.
    """

    @staticmethod
    def _render_root_makefile(tmp_path: Path, *, role: c.Infra.MakeProfile) -> str:
        # The engine is consumer-agnostic, so this fixture models a
        # neutral downstream root and takes its provider from the engine's own
        # configured provider catalog instead of naming a real consumer.
        provider = u.Tests.provider()
        root_repository = m.Infra.RepositoryRef(
            name="demo-root",
            distribution="demo-root",
            url=f"{provider.base_url}/demo-root.git",
            path=Path(),
            role=role,
            provider=provider.name,
            kind=c.Infra.ProjectKind.INTERNAL_FLEXT,
            codegen=c.Infra.CodegenKind.CONFORM,
            package=False,
            editable=False,
            read_only=False,
        )
        workspace = u.Tests.workspace_spec(
            root_repository,
            project=u.Tests.project_spec("demo-root"),
        )
        root = tmp_path / "demo-root"
        request = u.Tests.conform_request(
            root,
            what=c.Infra.CodegenConformSurface.MAKEFILE,
            scope=c.Infra.CodegenConformScope.SELF,
            mode=c.Infra.CodegenConformMode.CHECK,
        )
        planned = FlextInfraCodegenConform(
            repository_root=root,
            request=request,
            initial_workspace=workspace,
        ).plan(request)
        plan = tm.ok(planned)
        makefile = next(
            file for file in plan.files if file.path.name == c.Infra.MAKEFILE_FILENAME
        )
        return u.Tests.codegen_file_text(makefile)

    @staticmethod
    def _file_gate_body(rendered: str) -> str:
        """Extract the rendered `_builtin_file_gate_all` recipe body.

        Returns:
            The recipe text up to the next top-level target.

        """
        return rendered.split("_builtin_file_gate_all:", 1)[1].split("\n\n", 1)[0]

    def test_file_gate_verb_is_declared_fleet_wide(self, tmp_path: Path) -> None:
        """The codegen SSOT declares file-gate once with no profile restriction."""
        verb = next(
            verb for verb in config.Infra.codegen.make.verbs if verb.name == "file-gate"
        )
        rendered = self._render_root_makefile(
            tmp_path,
            role=c.Infra.MakeProfile.STANDALONE,
        )
        tm.that(rendered, has=verb.description)
        tm.that(
            verb.profiles,
            eq=tuple(c.Infra.MakeProfile),
        )

    def test_file_gate_renders_in_both_profiles(self, tmp_path: Path) -> None:
        """Every profile renders the verb, its mapping and its hard-gate chain."""
        for role in (c.Infra.MakeProfile.WORKSPACE, c.Infra.MakeProfile.STANDALONE):
            rendered = self._render_root_makefile(tmp_path, role=role)
            public_line = next(
                line
                for line in rendered.splitlines()
                if line.startswith("PUBLIC_VERBS :=")
            )
            tm.that(" file-gate" in public_line, eq=True, msg=public_line)
            builtin_line = next(
                line
                for line in rendered.splitlines()
                if line.startswith("BUILTIN_VERBS :=")
            )
            tm.that(" file-gate" in builtin_line, eq=True, msg=builtin_line)
            tm.that(
                "_builtin-file-gate: _builtin_file_gate_all" in rendered,
                eq=True,
            )
            body = self._file_gate_body(rendered)
            tm.that(
                body,
                has=[
                    (
                        "$(PROJECT_FLEXT_INFRA) check run"
                        ' --repository-root "$(PROJECT_ROOT)"'
                    ),
                    ' --gates "',
                    ' --file "$$FLEXT_FILE_GATE_FILE"',
                ],
            )
            tm.that(rendered, has="export FLEXT_FILE_GATE_FILE := $(value FILE)")
            selection = body.split(' --gates "', 1)[1].split('"', 1)[0]
            tm.that(len(selection.split(",")), gt=1)
            tm.that(selection, lacks=" ")
            tm.that(body, lacks=["|| true", "-m ruff", "ast-grep scan", 'typos "'])

    @staticmethod
    @pytest.mark.parametrize("selection", ["", "../outside.py", 'literal";false;.py'])
    def test_public_make_file_gate_preserves_missing_runtime_failure(
        tmp_path: Path,
        selection: str,
    ) -> None:
        """The public Make verb never turns an unavailable checker into success."""
        root, _ = u.Tests.render_make_environment(
            tmp_path,
            c.Infra.MakeProfile.STANDALONE,
        )
        tm.ok(u.Tests.create_python_environment(root))
        process = tm.ok(
            u.Cli.run_raw(
                [
                    c.Infra.MAKE,
                    "--no-print-directory",
                    "file-gate",
                    f"FILE={selection}",
                ],
                cwd=root,
                options=m.Cli.ProcessOptions(
                    remove_env_keys=c.Tests.MAKE_ISOLATION_ENV_KEYS,
                ),
            ),
        )
        tm.that(process.outcome.raw_return_code, ne=0)
        tm.that(process.stderr, has="No module named flext_infra")

    def test_setup_lifecycle_never_wires_a_reconcile_call(
        self,
        tmp_path: Path,
    ) -> None:
        """Setup never invokes the removed lock-rebuilding bootstrap route."""
        rendered = self._render_root_makefile(
            tmp_path,
            role=c.Infra.MakeProfile.WORKSPACE,
        )
        lifecycle = rendered.split("_setup_lifecycle:", 1)[1].split(
            ".PHONY: _setup_activated",
            1,
        )[0]
        tm.that(
            lifecycle,
            lacks=[
                'bootstrap reconcile "$(PROJECT_ROOT)"',
                "SETUP_MISE_LOCK_DRIFT",
                "could not rebuild mise.lock; setup continues",
            ],
        )

    def test_standalone_render_omits_the_reconcile_step(
        self,
        tmp_path: Path,
    ) -> None:
        """Standalone setup keeps its no-lock-write law: no reconcile call."""
        rendered = self._render_root_makefile(
            tmp_path,
            role=c.Infra.MakeProfile.STANDALONE,
        )
        tm.that("_builtin-file-gate: _builtin_file_gate_all" in rendered, eq=True)
        # Scope to the setup lifecycle: the bootstrap recipe legitimately
        # exports the drift signal for its own probe, so only the lifecycle
        # section proves the reconcile step is workspace-only.
        lifecycle = rendered.split("_setup_lifecycle:", 1)[1].split(
            ".PHONY: _setup_activated",
            1,
        )[0]
        tm.that(
            lifecycle,
            lacks=[
                'bootstrap reconcile "$(PROJECT_ROOT)"',
                "SETUP_MISE_LOCK_DRIFT",
            ],
        )
