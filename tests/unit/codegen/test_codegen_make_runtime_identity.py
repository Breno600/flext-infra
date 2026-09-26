"""Public Make runtime uses the same locked tool identity as frozen setup."""

from __future__ import annotations

from pathlib import Path

import pytest
from flext_tests import tm

from tests import c, u

pytestmark = pytest.mark.slow


class TestsFlextInfraCodegenMakeRuntimeIdentity:
    """Host Mise configuration cannot replace a project's resolved executable."""

    def test_status_uses_locked_uv_without_loading_host_configuration(
        self, tmp_path: Path
    ) -> None:
        root, _ = u.Tests.render_make_environment(
            tmp_path, c.Infra.MakeProfile.STANDALONE
        )
        tm.ok(u.Tests.create_python_environment(root))
        host_config = tmp_path / "host-mise.toml"
        host_config.write_text("invalid-host = [\n", encoding="utf-8")
        lock = root / c.Infra.MISE_LOCK_FILENAME
        lock_before = lock.read_bytes()
        locked_uv = u.Tests.toml_tables_at(
            lock.read_text(encoding="utf-8"), "tools", "uv"
        )
        tm.that(len(locked_uv), eq=1)
        version = locked_uv[0]["version"]
        tm.that(isinstance(version, str), eq=True)
        (root / "custom.mk").write_text(
            ".PHONY: post-status\n"
            'post-status:\n\t@test "$$APPLICATION_STATE" = "$(PROJECT_ROOT)"\n'
            "\t@printf 'application-environment-preserved\\n'\n",
            encoding="utf-8",
        )

        result = tm.ok(
            u.Tests.run_isolated_make(
                ["--no-print-directory", "status"],
                cwd=root,
                env={
                    "MISE_GLOBAL_CONFIG_FILE": str(host_config),
                    "APPLICATION_STATE": str(root),
                },
            )
        )

        tm.that(
            u.Cli.process_succeeded(result.outcome),
            eq=True,
            msg=result.stdout + result.stderr,
        )
        tm.that(result.stdout, has=f"uv {version} ")
        tm.that(result.stdout, has="application-environment-preserved")
        tm.that(result.stderr, lacks="invalid-host")
        tm.that(lock.read_bytes(), eq=lock_before)


__all__: list[str] = ["TestsFlextInfraCodegenMakeRuntimeIdentity"]
