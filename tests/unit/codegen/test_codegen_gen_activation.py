"""Real Make generation repairs activation before consuming its own output."""

from __future__ import annotations

from pathlib import Path

import pytest
from flext_tests import tm

from flext_infra import config
from tests import c, t, u

# Each scenario's candidate checkout is set up from its committed locks before
# any item starts. Make test-full owns the native installer and conform boundary.
pytestmark = [pytest.mark.slow, pytest.mark.remote]


class TestsFlextInfraCodegenGenActivation:
    """Exercise the generated dispatcher with its real producer and activation."""

    def test_gen_without_environment_fails_before_effects(self, tmp_path: Path) -> None:
        """A checkout that setup never provisioned stops before any hook."""
        root = u.Tests.infra_source_checkout(tmp_path)
        envrc = root / c.Infra.ENVRC_FILENAME
        broken_activation = envrc.read_text(encoding="utf-8") + "\nreturn 73\n"
        envrc.write_text(broken_activation, encoding="utf-8")

        process = tm.ok(
            u.Tests.run_isolated_make(["--no-print-directory", "gen"], cwd=root)
        )

        tm.that(u.Cli.process_succeeded(process.outcome), eq=False)
        tm.that(process.stderr, has="missing environment interpreter")
        tm.that((root / "gen-lifecycle.log").exists(), eq=False)
        tm.that((root / ".venv").exists(), eq=False)
        tm.that(envrc.read_text(encoding="utf-8"), eq=broken_activation)

    def test_gen_recovers_activation_and_orders_hooks(
        self, provisioned_infra_checkout: t.Pair[str, Path]
    ) -> None:
        """Native failures stop post hooks; a valid producer activates only once."""
        scenario, root = provisioned_infra_checkout
        receipt = root / "gen-lifecycle.log"
        envrc = root / c.Infra.ENVRC_FILENAME
        broken_activation = envrc.read_text(encoding="utf-8") + "\nreturn 73\n"
        envrc.write_text(broken_activation, encoding="utf-8")
        (root / c.Infra.ENVRC_LOCAL_RELPATH).write_text(
            "printf 'activated\\n' >> gen-lifecycle.log\n"
            'export MAKE_GEN_ACTIVATION_PROOF="$PROJECT_ROOT"\n'
            + ("return 43\n" if scenario == "activation-failure" else ""),
            encoding="utf-8",
        )
        (root / c.Infra.CUSTOM_MAKE_FILENAME).write_text(
            ".PHONY: pre-gen post-gen\n"
            "pre-gen:\n"
            '\t@test -x "$(RUNTIME_PYTHON)"\n'
            '\t@test -z "$$MAKE_GEN_ACTIVATION_PROOF"\n'
            "\t@printf 'pre\\n' >> gen-lifecycle.log\n"
            "post-gen:\n"
            '\t@test "$$MAKE_GEN_ACTIVATION_PROOF" = "$(PROJECT_ROOT)"\n'
            "\t@printf 'post\\n' >> gen-lifecycle.log\n"
            + (
                ".PHONY: _custom-gen\n"
                "_custom-gen:\n"
                "\t@printf 'custom\\n' >> gen-lifecycle.log\n"
                "\t+@$(SELF_MAKE) _builtin-gen\n"
                if scenario == "custom"
                else ""
            ),
            encoding="utf-8",
        )
        if scenario == "producer-failure":
            # Corrupt the real producer's package input. Python must preserve
            # its native SyntaxError before conform or activation can complete.
            initializer = (
                root
                / c.Infra.DEFAULT_SRC_DIR
                / config.Infra.name.replace("-", "_")
                / "__init__.py"
            )
            with initializer.open("a", encoding="utf-8") as stream:
                _ = stream.write("\ndef (\n")

        bootstrap = u.Infra.mise_bootstrap_environment()
        sidecars = root / ".mise" / "locks"
        locks = (
            root / c.Infra.UV_LOCK_FILENAME,
            root / bootstrap.version_pin_file,
            root / bootstrap.lock_file,
            *(path for path in sidecars.rglob("*") if path.is_file()),
        )
        before = {path: path.read_bytes() for path in locks}
        process = tm.ok(
            u.Tests.run_isolated_make(
                ["--no-print-directory", "gen"],
                cwd=root,
                env={"MAKE_GEN_ACTIVATION_PROOF": ""},
            )
        )

        tm.that({path: path.read_bytes() for path in locks}, eq=before)
        tm.that(
            {path for path in sidecars.rglob("*") if path.is_file()},
            eq={path for path in locks if path.is_relative_to(sidecars)},
        )
        succeeded = scenario in {"builtin", "custom"}
        tm.that(
            u.Cli.process_succeeded(process.outcome),
            eq=succeeded,
            msg=process.stdout + process.stderr,
        )
        if scenario == "producer-failure":
            tm.that(receipt.read_text().splitlines(), eq=["pre"])
            tm.that(process.stderr, has="SyntaxError")
            tm.that(envrc.read_text(encoding="utf-8"), eq=broken_activation)
            return
        tm.that(envrc.read_text(encoding="utf-8") == broken_activation, eq=False)
        expected = ["pre"]
        if scenario == "custom":
            expected.append("custom")
        expected.append("activated")
        if succeeded:
            expected.append("post")
            tm.that(process.stderr, lacks="mise WARN")
        else:
            tm.that(process.stderr, has="exit status 43")
        tm.that(receipt.read_text().splitlines(), eq=expected)
