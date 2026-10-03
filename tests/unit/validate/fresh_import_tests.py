"""Tests for FlextInfraValidateFreshImport.

Guard 7: fresh-process import smoke test — imports each advertised package
in a subprocess and fails when any raises ImportError. Catches cycles
lazy-loading would mask.

Copyright (c) 2025 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from flext_tests import tm

from flext_infra.validate.fresh_import import FlextInfraValidateFreshImport
from tests import c, m, u

if TYPE_CHECKING:
    from pathlib import Path


class TestsFlextInfraFreshImport:
    """Fresh-process import smoke test suite."""

    @staticmethod
    @pytest.fixture
    def v() -> FlextInfraValidateFreshImport:
        """Shared validator instance.

        Returns:
            The resulting ``FlextInfraValidateFreshImport``.

        """
        return FlextInfraValidateFreshImport()

    @staticmethod
    def test_probes_run_in_the_declared_target_environment(
        tmp_path: Path,
    ) -> None:
        """The declared target interpreter runs the probes, not the tool's.

        The tool's environment imports flext_core; the declared target's fresh
        stdlib environment does not, so the probe must fail there.
        """
        # The target is a real checkout: its own Git root owns the runtime.
        u.Tests.initialize_git_repo(tmp_path)
        u.Tests.provision_runtime_environment(tmp_path)
        validator = FlextInfraValidateFreshImport(
            repository_root=tmp_path,
            runtime_root=tmp_path,
        )
        report = tm.ok(validator.build_report(packages=("flext_core",)))
        tm.that(report.passed, eq=False)
        tm.that(report.violations[0], has="No module named 'flext_core'")

    @staticmethod
    def test_declared_target_without_interpreter_fails_loudly(
        tmp_path: Path,
    ) -> None:
        """A declared target lacking its interpreter fails, never falls back."""
        validator = FlextInfraValidateFreshImport(
            repository_root=tmp_path,
            runtime_root=tmp_path,
        )
        result = validator.build_report(packages=("sys",))
        tm.fail(result, has="fresh-import target interpreter is missing")

    @staticmethod
    def test_empty_package_list_passes(v: FlextInfraValidateFreshImport) -> None:
        """Test empty package list passes."""
        report: m.Infra.ValidationReport = tm.ok(v.build_report(packages=()))
        tm.that(report, is_=m.Infra.ValidationReport)
        tm.that(report.passed, eq=True)
        tm.that(report.violations, length=0)

    @staticmethod
    def test_stdlib_package_passes(v: FlextInfraValidateFreshImport) -> None:
        """Test stdlib package passes."""
        report: m.Infra.ValidationReport = tm.ok(v.build_report(packages=("sys",)))
        tm.that(report.passed, eq=True)
        tm.that(report.violations, length=0)

    @staticmethod
    def test_nonexistent_package_fails(v: FlextInfraValidateFreshImport) -> None:
        """Test nonexistent package fails."""
        report: m.Infra.ValidationReport = tm.ok(
            v.build_report(packages=("nonexistent_pkg_xyz_abc_123",)),
        )
        tm.that(report.passed, eq=False)
        tm.that(report.violations, length=1)
        tm.that(report.violations[0], has="nonexistent_pkg_xyz_abc_123")

    @staticmethod
    def test_mixed_good_and_bad_reports_only_bad(
        v: FlextInfraValidateFreshImport,
    ) -> None:
        """Test mixed good and bad reports only bad."""
        report: m.Infra.ValidationReport = tm.ok(
            v.build_report(packages=("sys", "nonexistent_xyz_qqq", "os")),
        )
        tm.that(report.passed, eq=False)
        tm.that(report.violations, length=1)
        tm.that(report.violations[0], has="nonexistent_xyz_qqq")

    @staticmethod
    def test_stops_at_first_causal_failure(
        v: FlextInfraValidateFreshImport,
    ) -> None:
        """Test stops at first causal failure."""
        report: m.Infra.ValidationReport = tm.ok(
            v.build_report(packages=("nonexistent_a_qqq", "nonexistent_b_qqq")),
        )
        tm.that(report.violations, length=1)
        tm.that(report.violations[0], has="nonexistent_a_qqq")
        tm.that(report.violations[0], lacks="nonexistent_b_qqq")
        tm.that(report.summary, has="failed")

    @staticmethod
    def test_passing_summary_is_human_readable(
        v: FlextInfraValidateFreshImport,
    ) -> None:
        """Test passing summary is human readable."""
        report: m.Infra.ValidationReport = tm.ok(v.build_report(packages=("sys", "os")))
        tm.that(report.summary, has="import")

    @staticmethod
    def test_workspace_src_package_passes(tmp_path: Path) -> None:
        """Test workspace src package passes."""
        package_root = tmp_path / "src" / "demo_external"
        package_root.mkdir(parents=True)
        package_root.joinpath("__init__.py").write_text("VALUE = 1\n", encoding="utf-8")
        validator = FlextInfraValidateFreshImport(repository_root=tmp_path)
        report: m.Infra.ValidationReport = tm.ok(
            validator.build_report(packages=("demo_external",)),
        )
        tm.that(report.passed, eq=True, msg=str(report.violations))

    @staticmethod
    @pytest.mark.parametrize("missing_export", [False, True])
    def test_preserved_initializer_uses_real_publication_contract(
        tmp_path: Path,
        *,
        missing_export: bool,
    ) -> None:
        """A preserved package is imported and its live exports must resolve."""
        repository_root, package = u.Tests.create_lazy_init_workspace(tmp_path)
        initializer = package / c.Infra.INIT_PY
        content = "__all__ = ('missing_export',)\n" if missing_export else ""
        initializer.write_text(content, encoding=c.Cli.ENCODING_DEFAULT)
        analysis = tm.ok(u.Tests.plan_lazy_init(repository_root))
        publication = next(
            plan for plan in analysis.publications if plan.context.pkg_dir == package
        )
        tm.that(publication.action, eq=c.Infra.LazyInitAction.SKIP)

        report = tm.ok(
            FlextInfraValidateFreshImport(repository_root=repository_root).build_report(
                publications=analysis.publications,
                repository_roots=(repository_root,),
            ),
        )

        tm.that(report.passed, eq=not missing_export, msg=str(report.violations))
        tm.that(initializer.read_text(encoding=c.Cli.ENCODING_DEFAULT), eq=content)
        if missing_export:
            tm.that(report.violations[0], has="missing_export")
            tm.that(report.violations[0], has="Traceback")
        else:
            tm.that(report.violations, length=0)

    @staticmethod
    def test_removed_initializer_is_not_a_publication_contract(
        tmp_path: Path,
    ) -> None:
        """A planned removal cannot certify the package's public exports."""
        repository_root, package = u.Tests.create_lazy_init_workspace(tmp_path)
        initializer = package / c.Infra.INIT_PY
        initializer.write_text(
            f"{c.Infra.AUTOGEN_HEADER}\n",
            encoding=c.Cli.ENCODING_DEFAULT,
        )
        analysis = tm.ok(u.Tests.plan_lazy_init(repository_root))
        publication = next(
            plan for plan in analysis.publications if plan.context.pkg_dir == package
        )
        tm.that(publication.action, eq=c.Infra.LazyInitAction.REMOVE)

        result = FlextInfraValidateFreshImport(
            repository_root=repository_root,
        ).build_report(
            publications=analysis.publications,
            repository_roots=(repository_root,),
        )

        tm.fail(result, has=f"missing public export contract for {package.name}")

    @staticmethod
    def test_layout_without_a_plan_verifies_its_on_disk_contract(
        tmp_path: Path,
    ) -> None:
        """A layout no publication claims is verified from its live exports.

        A workspace-root generation transaction indexes only its own packages,
        so a declared member repository arrives with no lazy-init plan. The
        verifier must import that checkout and resolve its declared ``__all__``
        instead of rejecting it for the missing plan.
        """
        repository_root, package = u.Tests.create_lazy_init_workspace(tmp_path)
        (package / c.Infra.INIT_PY).write_text(
            "value = 17\n__all__ = ('value',)\n",
            encoding=c.Cli.ENCODING_DEFAULT,
        )

        report = tm.ok(
            FlextInfraValidateFreshImport(repository_root=repository_root).build_report(
                publications=(),
                repository_roots=(repository_root,),
            ),
        )

        tm.that(report.passed, eq=True, msg=str(report.violations))

    @staticmethod
    def test_layout_without_a_plan_still_fails_on_a_broken_disk_contract(
        tmp_path: Path,
    ) -> None:
        """A live package whose declared export cannot resolve still fails."""
        repository_root, package = u.Tests.create_lazy_init_workspace(tmp_path)
        (package / c.Infra.INIT_PY).write_text(
            "__all__ = ('missing_export',)\n",
            encoding=c.Cli.ENCODING_DEFAULT,
        )

        report = tm.ok(
            FlextInfraValidateFreshImport(repository_root=repository_root).build_report(
                publications=(),
                repository_roots=(repository_root,),
            ),
        )

        tm.that(report.passed, eq=False)
        tm.that(report.violations[0], has="missing_export")
        tm.that(report.violations[0], has="Traceback")

    @staticmethod
    @pytest.mark.parametrize("script_group", ["scripts", "gui-scripts"])
    @pytest.mark.parametrize("target_exists", [False, True])
    def test_declared_script_failure_blocks_publication(
        tmp_path: Path,
        script_group: str,
        *,
        target_exists: bool,
    ) -> None:
        """A missing declared module or callable fails with its original traceback."""
        package = tmp_path / c.Infra.DEFAULT_SRC_DIR / "flext_probe_script"
        package.mkdir(parents=True)
        initializer = package / c.Infra.INIT_PY
        initializer.write_text("__all__ = ()\n", encoding=c.Cli.ENCODING_DEFAULT)
        if target_exists:
            (package / "cli.py").write_text(
                "VALUE = 1\n",
                encoding=c.Cli.ENCODING_DEFAULT,
            )
        (tmp_path / c.PYPROJECT_FILENAME).write_text(
            '[project]\nname = "flext-probe-script"\nversion = "1.0"\n\n'
            f'[project.{script_group}]\nprobe = "{package.name}.cli:main"\n',
            encoding="utf-8",
        )
        publication = m.Infra.LazyInitPlan(
            context=m.Infra.LazyInitPackageContext(
                pkg_dir=package,
                init_path=initializer,
                current_pkg=package.name,
                surface=package.name,
                importable=True,
                generated_init=True,
            ),
            action=c.Infra.LazyInitAction.WRITE,
            lazy_map={},
            eager_dunders={},
            inline_constants={},
        )
        report = tm.ok(
            FlextInfraValidateFreshImport(repository_root=tmp_path).build_report(
                publications=(publication,),
                repository_roots=(tmp_path,),
            ),
        )
        tm.that(report.passed, eq=False)
        tm.that(report.violations, length=1)
        tm.that(report.violations[0], has="scripts/probe=")
        tm.that(report.violations[0], has="Traceback")
        tm.that(
            report.violations[0],
            has="has no attribute 'main'" if target_exists else "ModuleNotFoundError",
        )

    @staticmethod
    def test_declared_script_contract_violation_stays_blocking(
        tmp_path: Path,
    ) -> None:
        """A missing export surfacing through a loadable script fails the report."""
        package = tmp_path / c.Infra.DEFAULT_SRC_DIR / "flext_probe_script"
        package.mkdir(parents=True)
        initializer = package / c.Infra.INIT_PY
        initializer.write_text("__all__ = ()\n", encoding=c.Cli.ENCODING_DEFAULT)
        (package / "cli.py").write_text(
            "from flext_probe_script import gone\n",
            encoding=c.Cli.ENCODING_DEFAULT,
        )
        (tmp_path / c.PYPROJECT_FILENAME).write_text(
            '[project]\nname = "flext-probe-script"\nversion = "1.0"\n\n'
            f'[project.scripts]\nprobe = "{package.name}.cli:main"\n',
            encoding="utf-8",
        )
        publication = m.Infra.LazyInitPlan(
            context=m.Infra.LazyInitPackageContext(
                pkg_dir=package,
                init_path=initializer,
                current_pkg=package.name,
                surface=package.name,
                importable=True,
                generated_init=True,
            ),
            action=c.Infra.LazyInitAction.WRITE,
            lazy_map={},
            eager_dunders={},
            inline_constants={},
        )
        report = tm.ok(
            FlextInfraValidateFreshImport(repository_root=tmp_path).build_report(
                publications=(publication,),
                repository_roots=(tmp_path,),
            ),
        )
        tm.that(report.passed, eq=False)
        tm.that(report.violations[0], has="ImportError")

    @staticmethod
    def test_advertised_lazy_export_must_resolve(tmp_path: Path) -> None:
        """Test advertised lazy export must resolve."""
        package = tmp_path / c.Infra.DEFAULT_SRC_DIR / "flext_import_probe"
        package.mkdir(parents=True)
        (package / c.Infra.INIT_PY).write_text(
            "__all__ = ('missing_export',)\n",
            encoding=c.Cli.ENCODING_DEFAULT,
        )
        report = tm.ok(
            FlextInfraValidateFreshImport(repository_root=tmp_path).build_report(
                packages=(package.name,),
            ),
        )
        tm.that(report.passed, eq=False)
        tm.that(report.violations[0], has="missing_export")
        tm.that(report.violations[0], has="Traceback")

    @staticmethod
    @pytest.mark.parametrize("dependency_present", [False, True])
    def test_declared_consumer_catches_exports_omitted_from_plan(
        tmp_path: Path,
        *,
        dependency_present: bool,
    ) -> None:
        """Test declared consumer catches exports omitted from plan."""
        package = tmp_path / c.Infra.DEFAULT_SRC_DIR / "flext_import_probe"
        package.mkdir(parents=True)
        initializer = package / c.Infra.INIT_PY
        initializer.write_text(
            "__all__ = ()\n" + ("required = 17\n" if dependency_present else ""),
            encoding=c.Cli.ENCODING_DEFAULT,
        )
        (package / "consumer.py").write_text(
            f"from {package.name} import required\n"
            "def main():\n    raise RuntimeError('entrypoint must not execute')\n",
            encoding=c.Cli.ENCODING_DEFAULT,
        )
        (tmp_path / c.PYPROJECT_FILENAME).write_text(
            '[project]\nname = "flext-import-probe"\nversion = "1.0"\n'
            f'[project.scripts]\nprobe = "{package.name}.consumer:main"\n',
            encoding=c.Cli.ENCODING_DEFAULT,
        )
        publication = m.Infra.LazyInitPlan(
            context=m.Infra.LazyInitPackageContext(
                pkg_dir=package,
                init_path=initializer,
                current_pkg=package.name,
                surface=package.name,
                importable=True,
                generated_init=True,
            ),
            action=c.Infra.LazyInitAction.WRITE,
            lazy_map={},
            eager_dunders={},
            inline_constants={},
        )
        report = tm.ok(
            FlextInfraValidateFreshImport(repository_root=tmp_path).build_report(
                publications=(publication,),
                repository_roots=(tmp_path,),
            ),
        )
        tm.that(report.passed, eq=dependency_present, msg=str(report.violations))
        if not dependency_present:
            tm.that(report.violations[0], has="required")
            tm.that(report.violations[0], has="consumer.py")
            tm.that(report.violations[0], has="Traceback")

    @staticmethod
    def test_probe_larger_than_one_process_argument_still_runs(
        tmp_path: Path,
    ) -> None:
        """Test probe larger than one process argument still runs."""
        package = tmp_path / c.Infra.DEFAULT_SRC_DIR / "flext_import_probe"
        package.mkdir(parents=True)
        exports = tuple(f"export_{index:05d}_published_name" for index in range(6000))
        initializer = package / c.Infra.INIT_PY
        initializer.write_text(
            "".join(f"{name} = {index}\n" for index, name in enumerate(exports))
            + f"__all__ = {exports!r}\n",
            encoding=c.Cli.ENCODING_DEFAULT,
        )
        (tmp_path / c.PYPROJECT_FILENAME).write_text(
            '[project]\nname = "flext-import-probe"\nversion = "1.0"\n',
            encoding=c.Cli.ENCODING_DEFAULT,
        )
        publication = m.Infra.LazyInitPlan(
            context=m.Infra.LazyInitPackageContext(
                pkg_dir=package,
                init_path=initializer,
                current_pkg=package.name,
                surface=package.name,
                importable=True,
                generated_init=True,
            ),
            action=c.Infra.LazyInitAction.WRITE,
            exports=exports,
            lazy_map={},
            eager_dunders={},
            inline_constants={},
        )
        report = tm.ok(
            FlextInfraValidateFreshImport(repository_root=tmp_path).build_report(
                publications=(publication,),
                repository_roots=(tmp_path,),
            ),
        )
        tm.that(report.passed, eq=True, msg=str(report.violations))

    @staticmethod
    def test_rejects_owned_module_imported_from_another_directory(
        tmp_path: Path,
    ) -> None:
        """Test rejects owned module imported from another directory."""
        package = tmp_path / c.Infra.DEFAULT_SRC_DIR / "flext_import_probe"
        package.mkdir(parents=True)
        foreign = tmp_path / "foreign"
        foreign.mkdir()
        (foreign / "dependency.py").write_text(
            "value = 17\n",
            encoding=c.Cli.ENCODING_DEFAULT,
        )
        initializer = package / c.Infra.INIT_PY
        initializer.write_text(
            f"__path__ = [{str(foreign)!r}]\n"
            "from .dependency import value\n__all__ = ('value',)\n",
            encoding=c.Cli.ENCODING_DEFAULT,
        )
        (tmp_path / c.PYPROJECT_FILENAME).write_text(
            '[project]\nname = "flext-import-probe"\nversion = "1.0"\n',
            encoding=c.Cli.ENCODING_DEFAULT,
        )
        publication = m.Infra.LazyInitPlan(
            context=m.Infra.LazyInitPackageContext(
                pkg_dir=package,
                init_path=initializer,
                current_pkg=package.name,
                surface=package.name,
                importable=True,
                generated_init=True,
            ),
            action=c.Infra.LazyInitAction.WRITE,
            exports=("value",),
            lazy_map={},
            eager_dunders={},
            inline_constants={},
        )
        report = tm.ok(
            FlextInfraValidateFreshImport(repository_root=tmp_path).build_report(
                publications=(publication,),
                repository_roots=(tmp_path,),
            ),
        )
        tm.that(report.passed, eq=False)
        tm.that(report.violations[0], has="is outside")
        tm.that(report.violations[0], has=str(foreign))

    @staticmethod
    def test_foreign_origin_is_reported_before_phantom_export(
        tmp_path: Path,
    ) -> None:
        """A module loaded from outside this checkout names the origin first.

        The origin gate runs between the import and the name resolution, so
        stale-checkout contamination fails with the foreign path instead of a
        phantom-attribute error raised while resolving an unserved name.
        """
        package = tmp_path / c.Infra.DEFAULT_SRC_DIR / "flext_import_probe"
        package.mkdir(parents=True)
        foreign = tmp_path / "foreign"
        foreign.mkdir()
        (foreign / "dependency.py").write_text(
            "value = 17\n",
            encoding=c.Cli.ENCODING_DEFAULT,
        )
        initializer = package / c.Infra.INIT_PY
        initializer.write_text(
            f"__path__ = [{str(foreign)!r}]\n"
            "from .dependency import value\n"
            "__all__ = ('value', 'phantom_export')\n",
            encoding=c.Cli.ENCODING_DEFAULT,
        )
        (tmp_path / c.PYPROJECT_FILENAME).write_text(
            '[project]\nname = "flext-import-probe"\nversion = "1.0"\n',
            encoding=c.Cli.ENCODING_DEFAULT,
        )
        publication = m.Infra.LazyInitPlan(
            context=m.Infra.LazyInitPackageContext(
                pkg_dir=package,
                init_path=initializer,
                current_pkg=package.name,
                surface=package.name,
                importable=True,
                generated_init=True,
            ),
            action=c.Infra.LazyInitAction.WRITE,
            exports=("value",),
            lazy_map={},
            eager_dunders={},
            inline_constants={},
        )
        report = tm.ok(
            FlextInfraValidateFreshImport(repository_root=tmp_path).build_report(
                packages=(package.name,),
                publications=(publication,),
                repository_roots=(tmp_path,),
            ),
        )
        tm.that(report.passed, eq=False)
        tm.that(report.violations[0], has="is outside")
        tm.that(report.violations[0], has=str(foreign))
        tm.that(report.violations[0], lacks="has no attribute")

    @staticmethod
    def test_origin_gate_keeps_the_probed_module_for_export_resolution(
        tmp_path: Path,
    ) -> None:
        """Exports resolve against the published package, not the last loaded module.

        The subpackage plan runs first, so the root package is already cached
        when its own plan imports it and ``sys.modules`` ends with the
        subpackage. The origin gate walks every loaded module between import
        and resolution; it must never rebind the probed package.
        """
        package = tmp_path / c.Infra.DEFAULT_SRC_DIR / "flext_import_probe"
        subpackage = package / "sub"
        subpackage.mkdir(parents=True)
        (package / c.Infra.INIT_PY).write_text(
            "value = 17\n__all__ = ('value',)\n",
            encoding=c.Cli.ENCODING_DEFAULT,
        )
        (subpackage / c.Infra.INIT_PY).write_text(
            "leaf = 1\n__all__ = ('leaf',)\n",
            encoding=c.Cli.ENCODING_DEFAULT,
        )
        (tmp_path / c.PYPROJECT_FILENAME).write_text(
            '[project]\nname = "flext-import-probe"\nversion = "1.0"\n',
            encoding=c.Cli.ENCODING_DEFAULT,
        )
        publications = tuple(
            m.Infra.LazyInitPlan(
                context=m.Infra.LazyInitPackageContext(
                    pkg_dir=pkg_dir,
                    init_path=pkg_dir / c.Infra.INIT_PY,
                    current_pkg=current_pkg,
                    surface=package.name,
                    importable=True,
                    generated_init=True,
                ),
                action=c.Infra.LazyInitAction.WRITE,
                exports=exports,
                lazy_map={},
                eager_dunders={},
                inline_constants={},
            )
            for pkg_dir, current_pkg, exports in (
                (subpackage, f"{package.name}.sub", ("leaf",)),
                (package, package.name, ("value",)),
            )
        )
        report = tm.ok(
            FlextInfraValidateFreshImport(repository_root=tmp_path).build_report(
                publications=publications,
                repository_roots=(tmp_path,),
            ),
        )
        tm.that(report.passed, eq=True, msg=str(report.violations))

    @staticmethod
    def test_flext_core_imports_cleanly(v: FlextInfraValidateFreshImport) -> None:
        """Test flext core imports cleanly."""
        report: m.Infra.ValidationReport = tm.ok(
            v.build_report(packages=("flext_core",)),
        )
        tm.that(report.passed, eq=True, msg=report.summary)

    @staticmethod
    def test_flext_infra_imports_cleanly(
        v: FlextInfraValidateFreshImport,
    ) -> None:
        """Test flext infra imports cleanly."""
        report: m.Infra.ValidationReport = tm.ok(
            v.build_report(packages=("flext_infra",)),
        )
        tm.that(report.passed, eq=True, msg=report.summary)
