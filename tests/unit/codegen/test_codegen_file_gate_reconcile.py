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

    @staticmethod
    def test_file_gate_verb_is_declared_fleet_wide() -> None:
        """The codegen SSOT declares file-gate once with no profile restriction."""
        verb = next(
            verb for verb in config.Infra.codegen.make.verbs if verb.name == "file-gate"
        )
        tm.that(
            "fast per-file gates" in verb.description,
            eq=True,
            msg=verb.description,
        )
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
            # The empty-FILE guard fails loud and mirrors the test-file guard.
            tm.that(body, has="file-gate requires FILE=<repository-relative path>")
            tm.that(
                body,
                has=['case "$(FILE)" in /*|*..*)'],
            )
            # Ruff lint and format are the hard gates: no `|| true` on them.
            tm.that(body.count('-m ruff check "$$file"'), eq=1)
            tm.that(body.count('-m ruff format --check "$$file"'), eq=1)
            tm.that(body, has="printf 'ERROR: file-gate requires FILE=")
            # The advisory scanners stay reportable, never blocking.
            tm.that(
                body,
                has=[
                    '-m pyrefly check "$$file" || true',
                    '-m pyright "$$file" || true',
                    'ast-grep scan "$$file" || true',
                    'typos "$$file" || true',
                ],
            )
            tm.that(body, has="$(RUNTIME_PYTHON)")

    def test_setup_lifecycle_never_wires_a_reconcile_call(
        self,
        tmp_path: Path,
    ) -> None:
        """The workspace setup lifecycle repairs drift through the reconcile owner."""
        rendered = self._render_root_makefile(
            tmp_path,
            role=c.Infra.MakeProfile.WORKSPACE,
        )
        lifecycle = rendered.split("_setup_lifecycle:", 1)[1].split(
            ".PHONY: _setup_activated",
            1,
        )[0]
        # The step is gated on the drift signal the bootstrap recipe exports.
        tm.that(lifecycle, has='[ "$${SETUP_MISE_LOCK_DRIFT:-}" = "1" ]')
        tm.that(
            lifecycle,
            has='bootstrap reconcile "$(PROJECT_ROOT)" "$$mise_pin"',
        )
        # Reconcile may never fail the setup that carries it.
        tm.that(lifecycle, has="could not rebuild mise.lock; setup continues")
        # The pin leaves the declared pin file through the one declared reader.
        tm.that(lifecycle, has="mise_pin=$$(awk '")

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
