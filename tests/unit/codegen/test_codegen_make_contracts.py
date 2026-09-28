"""Public functional contract for new and existing project conformance.

Copyright (c) 2025 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from pathlib import Path

import pytest
from flext_tests import tm

from flext_infra import config
from flext_infra.codegen import FlextInfraCodegenConform
from tests import c, m, u

from .conform_support import TestsFlextInfraConformSupport

pytestmark = [pytest.mark.slow]


class TestsFlextInfraCodegenMakeContracts:
    """Generated Make behavior and custom dispatch contracts."""

    def test_invalid_public_custom_make_fails_without_side_effects(
        self, infra_git_repo: Path
    ) -> None:
        root = infra_git_repo
        custom = root / "custom.mk"
        content = ".PHONY: public-handler\npublic-handler:\n\t@true\n"
        tm.ok(u.Cli.atomic_write_text_file(custom, content))
        policy: m.Infra.CustomHandlerPolicy = (
            config.Infra.codegen.make.custom_handler_policies[
                c.Infra.MakeProfile.STANDALONE
            ]
        )
        result = FlextInfraCodegenConform.validate_custom_make(
            tm.ok(u.Cli.files_read_text(custom)), policy
        )
        tm.fail(result)
        rejection = Path(f"{custom}.rej")
        tm.that(
            result.error or "", has="custom.mk line 1 is not a private custom handler"
        )
        tm.that(rejection.exists(), eq=False)
        tm.that(custom.read_text(encoding="utf-8"), eq=content)

    @pytest.mark.slow
    def test_valid_private_custom_make_has_no_rejection(
        self, infra_git_repo: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        root = infra_git_repo
        workspace = TestsFlextInfraConformSupport.standalone_workspace(root)
        custom = root / "custom.mk"
        tm.ok(
            u.Cli.atomic_write_text_file(
                custom,
                (
                    ".PHONY: \\\n"
                    "\t_custom_check_demo \\\n"
                    "\t_custom_run_demo\n"
                    "_custom_check_demo:\n\t@true\n"
                    "_custom_run_demo:\n\t@true\n"
                ),
            )
        )
        result = FlextInfraCodegenConform.execute_request(
            u.Tests.conform_request(
                root,
                what=c.Infra.CodegenConformSurface.MAKEFILE,
                scope=c.Infra.CodegenConformScope.SELF,
                mode=c.Infra.CodegenConformMode.APPLY,
            ),
            initial_workspace=workspace,
        )
        tm.ok(result)
        tm.that("WARN:" in capsys.readouterr().out, eq=False)
        tm.that(Path(f"{custom}.rej").exists(), eq=False)

    def test_custom_make_rejects_unterminated_phony_continuation(self) -> None:
        """Fail closed when a multiline private-handler declaration is truncated."""
        policy: m.Infra.CustomHandlerPolicy = (
            config.Infra.codegen.make.custom_handler_policies[
                c.Infra.MakeProfile.STANDALONE
            ]
        )

        result = FlextInfraCodegenConform.validate_custom_make(
            ".PHONY: \\\n\t_custom_check_demo \\", policy
        )

        tm.fail(result, has="unterminated .PHONY continuation")

    @pytest.mark.slow
    def test_scaffold_make_help_documents_and_lists_custom_hooks(
        self, infra_git_repo: Path
    ) -> None:
        """Scaffold help lists the selector-free interface; hooks stay lifecycle-only."""
        root = infra_git_repo
        workspace = TestsFlextInfraConformSupport.standalone_workspace(root)
        TestsFlextInfraConformSupport.apply_conform_surface(
            root, workspace, c.Infra.CodegenConformSurface.MAKEFILE
        )
        tm.ok(
            u.Cli.atomic_write_text_file(
                root / "custom.mk",
                ".PHONY: pre-check post-test-all _custom-check-myscan\n"
                "pre-check:\n\t@true\n"
                "post-test-all:\n\t@true\n"
                "_custom-check-myscan:\n\t@true\n",
            )
        )
        outcome = u.Cli.run_raw(
            ["make", "-C", str(root), "help"], remove_env_keys=("MAKEFLAGS",)
        )
        output = tm.ok(outcome)
        tm.that(output.stderr, eq="")
        tm.that(u.Cli.process_succeeded(output.outcome), eq=True)
        tm.that(output.stdout, has=["help", "setup", "check", "test", "fmt", "docs"])
        tm.that(output.stdout, lacks="Custom hooks (custom.mk):")
        tm.that(output.stdout, lacks="WHAT")

    @pytest.mark.slow
    def test_scaffold_make_runs_pre_and_post_verb_hooks_in_order(
        self, infra_git_repo: Path
    ) -> None:
        """Generated dispatch runs pre-<verb>, custom handler, post-<verb> in order."""
        root = infra_git_repo
        workspace = TestsFlextInfraConformSupport.standalone_workspace(root)
        TestsFlextInfraConformSupport.apply_conform_surface(
            root, workspace, c.Infra.CodegenConformSurface.MAKEFILE
        )
        tm.ok(
            u.Cli.atomic_write_text_file(
                root / "custom.mk",
                ".PHONY: pre-check post-check _custom-check\n"
                "pre-check:\n\t@echo HOOK_PRE\n"
                "_custom-check:\n\t@echo HANDLER_BODY\n"
                "post-check:\n\t@echo HOOK_POST\n",
            )
        )
        # `check` requires a provisioned interpreter, which `make setup` would
        # build. Stub it so this test stays about hook ordering.
        u.Tests.write_executable(
            root / ".venv" / "bin" / "python", "#!/bin/sh\nexit 0\n"
        )
        # `check` also requires the Mise pin (db516968e).
        u.Tests.copy_tracked_mise_seeds(root)
        outcome = u.Cli.run_raw(["make", "-C", str(root), "check", ""])
        output = tm.ok(outcome)
        tm.that(
            u.Cli.process_succeeded(output.outcome),
            eq=True,
            msg=output.stdout + output.stderr,
        )
        combined = output.stdout + output.stderr
        pre_at = combined.find("HOOK_PRE")
        body_at = combined.find("HANDLER_BODY")
        post_at = combined.find("HOOK_POST")
        tm.that(pre_at >= 0 and body_at >= 0 and post_at >= 0, eq=True)
        tm.that(pre_at < body_at, eq=True)
        tm.that(body_at < post_at, eq=True)

    def test_custom_make_accepts_pre_post_verb_hooks(
        self, infra_git_repo: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """custom.mk may append pre/post verb hooks (verb-wide and WHAT-scoped)."""
        root = infra_git_repo
        workspace = TestsFlextInfraConformSupport.standalone_workspace(root)
        custom = root / "custom.mk"
        tm.ok(
            u.Cli.atomic_write_text_file(
                custom,
                ".PHONY: pre-check post-check pre-test-all post-test-all\n"
                "pre-check:\n\t@true\n"
                "post-check:\n\t@true\n"
                "pre-test-all:\n\t@true\n"
                "post-test-all:\n\t@true\n",
            )
        )
        result = FlextInfraCodegenConform.execute_request(
            u.Tests.conform_request(
                root,
                what=c.Infra.CodegenConformSurface.MAKEFILE,
                scope=c.Infra.CodegenConformScope.SELF,
                mode=c.Infra.CodegenConformMode.APPLY,
            ),
            initial_workspace=workspace,
        )
        tm.ok(result)
        tm.that("WARN:" in capsys.readouterr().out, eq=False)
        tm.that(Path(f"{custom}.rej").exists(), eq=False)

    @pytest.mark.slow
    def test_non_regular_custom_make_remains_fatal(self, infra_git_repo: Path) -> None:
        root = infra_git_repo
        workspace = TestsFlextInfraConformSupport.standalone_workspace(root)
        TestsFlextInfraConformSupport.apply_conform_surface(
            root, workspace, c.Infra.CodegenConformSurface.MAKEFILE
        )
        tm.ok(u.Cli.files_delete(root / "custom.mk"))
        (root / "custom.mk").mkdir()
        result = FlextInfraCodegenConform.execute_request(
            u.Tests.conform_request(
                root,
                scope=c.Infra.CodegenConformScope.SELF,
                mode=c.Infra.CodegenConformMode.CHECK,
            ),
            initial_workspace=workspace,
        )
        tm.fail(result)
        tm.that(result.error, has="not a regular file")
        tm.that(result.error, has=str(root / "custom.mk"))
