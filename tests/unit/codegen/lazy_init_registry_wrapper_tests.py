"""Public cleanup tests for superseded lazy-init sidecars."""

from __future__ import annotations

from pathlib import Path

from flext_tests import tm

from tests import c, t, u


# flext-i6nq.10: Cleanup is proven through the real generator, not private mixins.
class TestsFlextInfraLazyInitCleanup:
    """Validate stale generated sidecars are reported or removed truthfully."""

    @staticmethod
    def _workspace_with_sidecars(
        tmp_path: Path,
    ) -> t.Triple[Path, Path, t.VariadicTuple[Path]]:
        repository_root, package_root = u.Tests.create_lazy_init_workspace(tmp_path)
        u.Tests.write_lazy_init_namespace_module(
            package_root / "models.py", class_name="FlextTestsModels", alias="m"
        )
        stale_paths = (
            package_root / c.Infra.ROOT_EXPORTS_FILENAME,
            package_root / "_exports_lazy.py",
            package_root / "_exports_lazy_part_01.py",
        )
        for path in stale_paths:
            path.write_text(
                f"{c.Infra.AUTOGEN_HEADER}\n", encoding=c.Cli.ENCODING_DEFAULT
            )
        return repository_root, package_root, stale_paths

    def test_apply_removes_sidecars_and_keeps_initializer(self, tmp_path: Path) -> None:
        """Apply deletes superseded registries after producing the initializer."""
        repository_root, package_root, stale_paths = self._workspace_with_sidecars(
            tmp_path
        )

        result = u.Tests.run_lazy_init(repository_root)

        tm.that(result, eq=0)
        tm.that(all(not path.exists() for path in stale_paths), eq=True)
        tm.that((package_root / c.Infra.INIT_PY).is_file(), eq=True)

    def test_check_reports_sidecars_without_removing(self, tmp_path: Path) -> None:
        """Check-only records every stale sidecar and preserves all bytes."""
        repository_root, _package_root, stale_paths = self._workspace_with_sidecars(
            tmp_path
        )
        service = u.Tests.create_lazy_init_service(repository_root)

        result = service.plan_files()

        tm.that(result.success, eq=True)
        tm.that(all(path.exists() for path in stale_paths), eq=True)
        tm.that(
            set(map(str, stale_paths)).issubset(set(service.modified_files)), eq=True
        )

    def test_apply_removes_closed_obsolete_root_support(self, tmp_path: Path) -> None:
        """Apply removes every retired root support file."""
        repository_root, package_root = u.Tests.create_lazy_init_workspace(tmp_path)
        u.Tests.write_lazy_init_namespace_module(
            package_root / "models.py", class_name="FlextTestsModels", alias="m"
        )
        obsolete_module = package_root / "_root_typing.py"
        obsolete_module.write_text("ROOT = ()\n", encoding=c.Cli.ENCODING_DEFAULT)
        obsolete_package = package_root / "_root_typing_parts"
        obsolete_package.mkdir()
        obsolete_part = obsolete_package / "facades.py"
        obsolete_part.write_text("FACADES = ()\n", encoding=c.Cli.ENCODING_DEFAULT)

        result = u.Tests.run_lazy_init(repository_root)

        tm.that(result, eq=0)
        tm.that(obsolete_module.exists(), eq=False)
        tm.that(obsolete_part.exists(), eq=False)
        tm.that(tuple(obsolete_package.iterdir()), eq=())

    def test_check_reports_obsolete_root_support_without_removing(
        self, tmp_path: Path
    ) -> None:
        """Check-only records retired files and preserves their bytes."""
        repository_root, package_root = u.Tests.create_lazy_init_workspace(tmp_path)
        u.Tests.write_lazy_init_namespace_module(
            package_root / "models.py", class_name="FlextTestsModels", alias="m"
        )
        obsolete_module = package_root / "_root_exports.py"
        obsolete_module.write_text("ROOT = ()\n", encoding=c.Cli.ENCODING_DEFAULT)
        service = u.Tests.create_lazy_init_service(repository_root)

        result = service.plan_files()

        tm.that(result.success, eq=True)
        tm.that(obsolete_module.is_file(), eq=True)
        tm.that(str(obsolete_module) in service.modified_files, eq=True)

    def test_obsolete_root_support_cleanup_fails_closed(self, tmp_path: Path) -> None:
        """Reject unexpected content before deleting any retired registry."""
        repository_root, package_root = u.Tests.create_lazy_init_workspace(tmp_path)
        u.Tests.write_lazy_init_namespace_module(
            package_root / "models.py", class_name="FlextTestsModels", alias="m"
        )
        obsolete_module = package_root / "_root_typing.py"
        obsolete_module.write_text("ROOT = ()\n", encoding=c.Cli.ENCODING_DEFAULT)
        obsolete_package = package_root / "_root_typing_parts"
        obsolete_package.mkdir()
        unexpected = obsolete_package / "KEEP.txt"
        unexpected.write_text("operator data\n", encoding=c.Cli.ENCODING_DEFAULT)

        result = u.Tests.plan_lazy_init(repository_root)

        tm.that(result.failure, eq=True)
        tm.that(obsolete_module.is_file(), eq=True)
        tm.that(unexpected.is_file(), eq=True)
