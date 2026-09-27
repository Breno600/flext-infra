"""End-to-end tests for canonical package initializer generation."""

from __future__ import annotations

from pathlib import Path

from flext_tests import tm

from tests import c, u


class TestsFlextInfraLazyInitProcessing:
    """Validate recursive generation through the public service surface."""

    @staticmethod
    def _read(package_dir: Path) -> str:
        """Read one generated package initializer."""
        return package_dir.joinpath(c.Infra.INIT_PY).read_text(
            encoding=c.Cli.ENCODING_DEFAULT
        )

    def test_apply_generates_inline_lazy_public_root(self, tmp_path: Path) -> None:
        """Generate the sole PEP 562 initializer at the production root."""
        repository_root, package_root = u.Tests.create_lazy_init_workspace(tmp_path)
        u.Tests.write_lazy_init_namespace_module(
            package_root / "models.py",
            class_name="FlextTestsModels",
            alias="m",
            docstring="Models.",
        )

        result = u.Tests.run_lazy_init(repository_root)
        content = self._read(package_root)

        tm.that(result, eq=0)
        tm.that(content, contains="build_lazy_import_map(")
        tm.that(content, contains="install_lazy_exports(")
        tm.that(content, contains="__all__: tuple[str, ...]")
        tm.that(content, lacks="__unit__")
        compile(content, "__init__.py", "exec")

    def test_check_only_reports_drift_without_writing(self, tmp_path: Path) -> None:
        """Report initializer drift while preserving every source byte."""
        repository_root, package_root = u.Tests.create_lazy_init_workspace(tmp_path)
        u.Tests.write_lazy_init_namespace_module(
            package_root / "models.py", class_name="FlextTestsModels", alias="m"
        )
        init_path = package_root / c.Infra.INIT_PY
        original = init_path.read_bytes()
        service = u.Tests.create_lazy_init_service(repository_root)

        result = service.plan_files()

        tm.that(result.success, eq=True)
        tm.that(init_path.read_bytes(), eq=original)
        tm.that(str(init_path) in service.modified_files, eq=True)

    def test_every_nested_level_is_lazy_formatted_and_idempotent(
        self, tmp_path: Path
    ) -> None:
        """Generate lazy facades at every importable package level."""
        repository_root, package_root = u.Tests.create_lazy_init_workspace(tmp_path)
        level_two = package_root / "services"
        level_three = level_two / "_parts"
        level_four = level_three / "runtime"
        for package_dir in (level_two, level_three, level_four):
            package_dir.mkdir()
            package_dir.joinpath(c.Infra.INIT_PY).write_text(
                "", encoding=c.Cli.ENCODING_DEFAULT
            )
        u.Tests.write_lazy_init_namespace_module(
            level_four / "worker.py",
            class_name="FlextTestsWorker",
            alias="worker",
            docstring="Worker.",
        )
        apply_result = u.Tests.run_lazy_init(repository_root)
        generated_paths = tuple(
            package_dir / c.Infra.INIT_PY
            for package_dir in (level_two, level_three, level_four)
        )
        before = tuple(path.read_bytes() for path in generated_paths)
        level_two_content, level_three_content, level_four_content = (
            path.read_text(encoding=c.Cli.ENCODING_DEFAULT) for path in generated_paths
        )
        u.Cli.run_raw(
            [
                c.Infra.RUFF,
                c.Infra.FORMAT,
                "--check",
                *(str(path) for path in generated_paths),
            ],
            cwd=repository_root,
        ).unwrap()
        u.Cli.run_raw(
            [
                c.Infra.RUFF,
                c.Infra.CHECK,
                "--no-fix",
                *(str(path) for path in generated_paths),
            ],
            cwd=repository_root,
        ).unwrap()
        check_service = u.Tests.create_lazy_init_service(repository_root)
        check_result = u.Tests.run_lazy_init(repository_root, check_only=True)
        after = tuple(path.read_bytes() for path in generated_paths)

        tm.that(apply_result, eq=0)
        for content in (level_two_content, level_three_content, level_four_content):
            tm.that(content, contains="install_lazy_exports(")
            tm.that(content, contains="__all__: tuple[str, ...]")
        tm.that(level_four_content, contains="from .worker import FlextTestsWorker")
        tm.that(level_four_content, contains="FlextTestsWorker")
        tm.that(level_four_content, contains='"worker"')
        tm.that(level_two_content, contains="FlextTestsWorker")
        tm.that(level_three_content, contains="FlextTestsWorker")
        tm.that(check_result, eq=0)
        tm.that(check_service.modified_files, empty=True)
        tm.that(after, eq=before)

    def test_manual_private_initializer_exports_survive_adoption(
        self, tmp_path: Path
    ) -> None:
        """Adopt the private facade while retaining its declared public export."""
        repository_root, package_root = u.Tests.create_lazy_init_workspace(tmp_path)
        private_dir = package_root / "_facade"
        private_dir.mkdir()
        private_dir.joinpath("runtime.py").write_text(
            'class FlextTestsRuntime:\n    """Private runtime owner."""\n',
            encoding=c.Cli.ENCODING_DEFAULT,
        )
        init_path = private_dir / c.Infra.INIT_PY
        init_path.write_text(
            '"""Authored static private facade."""\n\n'
            "from .runtime import FlextTestsRuntime\n\n"
            '__all__ = ["FlextTestsRuntime"]\n',
            encoding=c.Cli.ENCODING_DEFAULT,
        )
        result = u.Tests.run_lazy_init(repository_root)

        tm.that(result, eq=0)
        generated = init_path.read_text(encoding=c.Cli.ENCODING_DEFAULT)
        tm.that(generated, has='__all__: tuple[str, ...] = ("FlextTestsRuntime",)')
        tm.that(generated, has="from .runtime import FlextTestsRuntime")
        tm.that(u.Tests.run_lazy_init(repository_root), eq=0)
        tm.that(init_path.read_text(encoding=c.Cli.ENCODING_DEFAULT), eq=generated)

    def test_apply_removes_obsolete_generated_sidecars(self, tmp_path: Path) -> None:
        """Remove retired generated manifests while writing the initializer."""
        repository_root, package_root = u.Tests.create_lazy_init_workspace(tmp_path)
        u.Tests.write_lazy_init_namespace_module(
            package_root / "models.py", class_name="FlextTestsModels", alias="m"
        )
        unit_path = package_root / "__unit__.py"
        unit_path.write_text(
            f"{c.Infra.AUTOGEN_HEADER}\n", encoding=c.Cli.ENCODING_DEFAULT
        )

        result = u.Tests.run_lazy_init(repository_root)

        tm.that(result, eq=0)
        tm.that(unit_path.exists(), eq=False)
