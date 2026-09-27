"""Tests for core validation behavior in namespace validator."""

from __future__ import annotations

from pathlib import Path

from flext_tests import tm

from flext_infra import config
from tests import m, u


class TestsFlextInfraCoreValidationBehavior:
    """Test suite for core validation behavior."""

    def test_public_project_layout_uses_flext_for_core_exception(
        self, tmp_path: Path
    ) -> None:
        project_root = tmp_path / "flext-core"
        package_dir = project_root / "src" / "flext_core"
        package_dir.mkdir(parents=True)
        _ = (package_dir / "__init__.py").write_text("", encoding="utf-8")
        layout = u.Infra.layout(project_root)
        layout = tm.not_none(layout)
        tm.that(layout.class_stem, eq="Flext")

    def test_validate_tracked_git_files(self, tmp_path: Path) -> None:
        project_root = tmp_path / "project"
        package_dir = project_root / "src" / "flext_test"
        package_dir.mkdir(parents=True)
        _ = (package_dir / "__init__.py").write_text("", encoding="utf-8")
        u.Tests.write_canonical_package_layout(package_dir)
        tracked_module = package_dir / "models.py"
        tracked_module.write_text(
            u.Tests.namespace_fixture("rule0_valid.py"), encoding="utf-8"
        )

        init_result = u.Cli.run_raw(["git", "init"], cwd=project_root)
        tm.ok(init_result)
        tm.that(u.Cli.process_succeeded(init_result.value.outcome), eq=True)
        email_result = u.Cli.run_raw(
            ["git", "config", "user.email", "test@example.com"], cwd=project_root
        )
        tm.ok(email_result)
        tm.that(u.Cli.process_succeeded(email_result.value.outcome), eq=True)
        name_result = u.Cli.run_raw(
            ["git", "config", "user.name", "Test User"], cwd=project_root
        )
        tm.ok(name_result)
        tm.that(u.Cli.process_succeeded(name_result.value.outcome), eq=True)
        add_result = u.Cli.run_raw(
            ["git", "add", "src/flext_test/models.py", "src/flext_test/__init__.py"],
            cwd=project_root,
        )
        tm.ok(add_result)
        tm.that(u.Cli.process_succeeded(add_result.value.outcome), eq=True)

        result = u.Tests.namespace_validator().validate_project(project_root)

        tm.ok(result)
        tm.that(result.value.passed, eq=True)
        tm.that(result.value.violations, empty=True)

    def test_logical_loc_ceiling_reads_config_ssot(self, tmp_path: Path) -> None:
        """The per-module ceiling is the loc_cap SSOT, never a constant.

        The fixture size derives from the configured value, so this test
        tracks the SSOT instead of pinning either the old 200 or the current
        1000 number.
        """
        cap = config.Infra.codegen.loc_cap.max_lines
        assignments = "\n".join(
            f"        attr_{index} = {index}" for index in range(cap + 1)
        )
        module_source = u.Tests.namespace_fixture("rule0_valid.py").replace(
            "        pass\n", f"        pass\n{assignments}\n"
        )
        root = u.Tests.namespace_project(
            tmp_path, module_source=module_source, module_name="models.py"
        )

        result = u.Tests.namespace_validator().validate_project(root)

        tm.ok(result)
        locator = f"exceed the {cap} limit"
        tm.that(
            any(locator in violation for violation in result.value.violations), eq=True
        )

    def test_initializer_and_version_roles_are_scanned(self, tmp_path: Path) -> None:
        """Role-specific validation must not pass because discovery is empty."""
        project_root = tmp_path / "project"
        package_dir = project_root / "src" / "flext_test"
        package_dir.mkdir(parents=True)
        _ = (package_dir / "__init__.py").write_text(
            u.Tests.namespace_fixture("rule0_no_class.py"), encoding="utf-8"
        )
        _ = (package_dir / "__version__.py").write_text(
            u.Tests.namespace_fixture("rule0_no_class.py"), encoding="utf-8"
        )
        u.Tests.write_canonical_package_layout(package_dir)
        u.Tests.initialize_git_repo(project_root)
        files = tm.ok(
            u.Infra.iter_python_files(
                m.Infra.SourceScanRequest(project_roots=(project_root,))
            )
        )
        tm.that(files, has=package_dir / "__init__.py")
        tm.that(files, has=package_dir / "__version__.py")
        result = u.Tests.namespace_validator().validate_project(project_root)
        tm.that(result.success, eq=True)
        tm.that(result.value.passed, eq=True)
        tm.that(result.value.violations, empty=True)
        tm.that(result.value.summary, has="files checked")

    def test_validate_returns_report(self, tmp_path: Path) -> None:
        root = u.Tests.namespace_project(
            tmp_path,
            module_source=u.Tests.namespace_fixture("rule0_valid.py"),
            module_name="constants.py",
        )
        result = u.Tests.namespace_validator().validate_project(root)
        tm.that(result.success, eq=True)
        tm.that(result.value, is_=m.Infra.ValidationReport)
        tm.that(result.value.summary, has="files checked")

    def test_violation_message_format(self, tmp_path: Path) -> None:
        root = u.Tests.namespace_project(
            tmp_path,
            module_source=u.Tests.namespace_fixture("rule0_no_class.py"),
            module_name="models.py",
        )
        result = u.Tests.namespace_validator().validate_project(root)
        tm.that(result.success, eq=True)
        tm.that(len(result.value.violations), gt=0)
        first = result.value.violations[0]
        tm.that(first, has="[NS-STRUCT-")
        tm.that(first, has="] src/flext_test/models.py:1 — ")
