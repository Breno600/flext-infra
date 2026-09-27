"""Generated public verbs enforce the committed Mise runtime pin."""

from __future__ import annotations

from pathlib import Path

import pytest
from flext_tests import tm

from flext_core import r
from flext_infra import config
from tests import c, m, u

pytestmark = pytest.mark.slow


class TestsFlextInfraCodegenMakeLockContract:
    """A frozen operation fails before activation or any launcher execution."""

    def test_conform_publication_preserves_committed_lock_graph(
        self, tmp_path: Path
    ) -> None:
        root, _ = u.Tests.render_make_environment(
            tmp_path, c.Infra.MakeProfile.STANDALONE
        )
        lock = root / c.Infra.UV_LOCK_FILENAME
        lock.write_bytes((Path(__file__).resolve().parents[3] / lock.name).read_bytes())
        paths = (
            lock,
            root / c.Infra.MISE_LOCK_FILENAME,
            root / c.Infra.MISE_VERSION_PIN_FILENAME,
            *(path for path in (root / ".mise" / "locks").rglob("*") if path.is_file()),
        )
        before = {path: path.read_bytes() for path in paths}
        repository = u.Tests.repository_ref(
            root.name, role=c.Infra.MakeProfile.STANDALONE
        )
        workspace = u.Tests.workspace_spec(
            repository, project=u.Tests.project_spec(repository.name)
        )
        plan = u.Tests.conform_plan(root, workspace)
        tm.ok(
            u.Tests.materialize_codegen_plans(
                r[tuple[m.Infra.CodegenFilePlan, ...]].ok(tuple(plan.files))
            )
        )

        tm.that({path: path.read_bytes() for path in paths}, eq=before)

    def test_direnv_isolates_nested_checkout_from_parent_mise_config(
        self, tmp_path: Path
    ) -> None:
        """The real Mise reader cannot observe an unrelated ancestor config."""
        root, _ = u.Tests.render_make_environment(
            tmp_path, c.Infra.MakeProfile.STANDALONE
        )
        (root.parent / c.Infra.MISE_TOML_FILENAME).write_text(
            "invalid-parent = [\n", encoding="utf-8"
        )
        pin = (root / c.Infra.MISE_VERSION_PIN_FILENAME).read_text().strip()

        process = tm.ok(
            u.Cli.run_raw(
                [
                    "direnv",
                    "exec",
                    str(root),
                    str(root / "bin" / "mise"),
                    "ls",
                    "--json",
                ],
                cwd=root,
                env={"MISE_VERSION": pin},
                remove_env_keys=(
                    *c.Tests.MAKE_ISOLATION_ENV_KEYS,
                    "GIT_CEILING_DIRECTORIES",
                    "MISE_CEILING_PATHS",
                ),
            )
        )

        tm.that(
            u.Cli.process_succeeded(process.outcome),
            eq=True,
            msg=process.stdout + process.stderr,
        )
        tm.that(process.stderr, lacks="mise WARN")
        tm.that(process.stderr, lacks="invalid-parent")

    @pytest.mark.parametrize(
        ("verb", "pin_content"),
        [
            *(
                (verb.name, None)
                for verb in config.Infra.codegen.make.verbs
                if verb.name not in {"help", "clean", "upg"}
            ),
            ("status", ""),
            ("status", " \n"),
            ("status", "latest\n"),
        ],
    )
    def test_frozen_verbs_reject_an_unresolved_pin_before_effects(
        self, tmp_path: Path, verb: str, pin_content: str | None
    ) -> None:
        project_root, _ = u.Tests.render_make_environment(
            tmp_path, c.Infra.MakeProfile.STANDALONE
        )
        pin = project_root / c.Infra.MISE_VERSION_PIN_FILENAME
        if pin_content is None:
            pin.unlink()
        else:
            pin.write_text(pin_content, encoding="utf-8")
        (project_root / "bin" / "mise").unlink()
        activation = project_root / "activation-effect"
        (project_root / ".envrc.local").write_text(
            f'touch "{activation}"\n', encoding="utf-8"
        )

        process = tm.ok(
            u.Tests.run_isolated_make(["--no-print-directory", verb], cwd=project_root)
        )

        tm.that(process.outcome.raw_return_code, ne=0)
        tm.that(process.stderr, has=str(pin))
        tm.that(process.stderr, lacks="missing generated mise launcher")
        tm.that(activation.exists(), eq=False)
        tm.that((project_root / ".venv").exists(), eq=False)

    @pytest.mark.parametrize("verb", ["help", "clean", "upg"])
    def test_bootstrap_and_shell_verbs_do_not_require_the_pin(
        self, tmp_path: Path, verb: str
    ) -> None:
        project_root, _ = u.Tests.render_make_environment(
            tmp_path, c.Infra.MakeProfile.STANDALONE
        )
        pin = project_root / c.Infra.MISE_VERSION_PIN_FILENAME
        pin.unlink()
        (project_root / "bin" / "mise").unlink()

        process = tm.ok(
            u.Tests.run_isolated_make(["--no-print-directory", verb], cwd=project_root)
        )

        tm.that(process.stderr, lacks=str(pin))
        if verb == "upg":
            tm.that(process.outcome.raw_return_code, ne=0)
            tm.that(process.stderr, has="missing generated mise launcher")
        else:
            tm.that(u.Cli.process_succeeded(process.outcome), eq=True)
        tm.that(pin.exists(), eq=False)
