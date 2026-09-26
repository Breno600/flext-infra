"""Tests for the refactor main CLI entry point."""

from __future__ import annotations

import sys
from pathlib import Path
from types import CodeType
from typing import TYPE_CHECKING

import pytest
from flext_tests import tm

from flext_core import r
from flext_infra import main as infra_main
from flext_infra.refactor.census import FlextInfraRefactorCensus
from tests import t, u

if TYPE_CHECKING:
    from flext_infra import p


class TestsFlextInfraRefactorMainCli:
    """Tests for the refactor main CLI."""

    _FUTURE_INIT = "from __future__ import annotations\n"

    # The letter is declared in __all__ but never bound: the fix binds it to
    # the declared facade class. An undeclared letter is never inferred.
    _MISSING_RUNTIME_ALIAS_MODULE = (
        "from __future__ import annotations\n\n"
        '__all__: list[str] = ["FlextDemoModels", "m"]\n\n'
        "class FlextDemoModels:\n"
        "    pass\n"
    )

    _UNDECLARED_RUNTIME_ALIAS_MODULE = (
        "from __future__ import annotations\n\n"
        '__all__: list[str] = ["FlextDemoModels"]\n\n'
        "class FlextDemoModels:\n"
        "    pass\n"
    )

    _DUPLICATE_RUNTIME_ALIAS_MODULE = (
        "from __future__ import annotations\n\n"
        '__all__: list[str] = ["FlextDemoModels", "m"]\n\n'
        "class FlextDemoModels:\n"
        "    pass\n\n"
        "m = FlextDemoModels\n"
        "m = FlextDemoModels\n"
    )

    _FACADE_MEMBER_MODULE = (
        "from __future__ import annotations\n\n"
        '__all__: list[str] = ["FlextDemoModels", "m"]\n\n'
        "class FlextDemoModels:\n"
        "    pass\n\n"
        "m = FlextDemoModels\n"
    )

    _COMPATIBILITY_ALIAS_MODULE = (
        "from __future__ import annotations\n\n"
        '__all__: list[str] = ["NewThing"]\n\n'
        "class NewThing:\n"
        "    pass\n\n"
        "LegacyThing = NewThing\n"
    )

    _BASIC_INIT = (
        "from __future__ import annotations\n\n"
        "from sample_pkg.service import consume\n\n"
        '__all__: list[str] = ["consume"]\n'
    )

    _BASIC_SERVICE = (
        "from __future__ import annotations\n"
        "from typing import TypeAlias\n\n"
        "from flext_core import t\n\n"
        '__all__: list[str] = ["consume"]\n\n'
        "PayloadMap: TypeAlias = t.StrMapping\n"
        "def consume(payload: PayloadMap) -> PayloadMap:\n"
        "    return payload\n"
    )

    _TEST_ONLY_FUNCTION_SERVICE = (
        "from __future__ import annotations\n\n"
        '__all__: list[str] = ["only_for_tests"]\n\n'
        "def only_for_tests(value: int) -> int:\n"
        "    return value + 1\n"
    )

    _TEST_ONLY_FUNCTION_TEST = (
        "from __future__ import annotations\n\n"
        "from sample_pkg.service import only_for_tests\n\n"
        "def test_only_for_tests_returns_incremented_value() -> None:\n"
        "    assert only_for_tests(1) == 2\n"
    )

    _SEQUENCE_TEST_ONLY_SERVICE = (
        "from __future__ import annotations\n"
        "from collections.abc import Sequence\n\n"
        '__all__: list[str] = ["only_for_tests"]\n\n'
        "def only_for_tests(values: t.SequenceOf[int]) -> int:\n"
        "    return len(values)\n"
    )

    _SEQUENCE_TEST_ONLY_TEST = (
        "from __future__ import annotations\n\n"
        "from sample_pkg.service import only_for_tests\n\n"
        "def test_only_for_tests_uses_sequence_signature() -> None:\n"
        "    assert only_for_tests([1, 2]) == 2\n"
    )

    _TEST_ONLY_METHOD_SERVICE = (
        "from __future__ import annotations\n\n"
        '__all__: list[str] = ["Service"]\n\n'
        "class Service:\n"
        "    def only_for_tests(self, value: int) -> int:\n"
        "        return value + 1\n"
    )

    _TEST_ONLY_METHOD_TEST = (
        "from __future__ import annotations\n\n"
        "from sample_pkg.service import Service\n\n"
        "def test_only_for_tests_method_returns_incremented_value() -> None:\n"
        "    assert Service().only_for_tests(1) == 2\n"
    )

    _UNUSED_NESTED_FUNCTION_SERVICE = (
        "from __future__ import annotations\n\n"
        '__all__: list[str] = ["outer"]\n\n'
        "def outer(value: int) -> int:\n"
        "    def only_for_cleanup(inner: int) -> int:\n"
        "        return inner + 1\n\n"
        "    return value\n\n"
        "OBSERVED_VALUE = outer(1)\n"
    )

    _UNUSED_NESTED_FUNCTION_TEST = (
        "from __future__ import annotations\n\n"
        "from sample_pkg.service import outer\n\n"
        "OBSERVED_VALUE = outer(1)\n"
        "assert OBSERVED_VALUE == 1\n"
    )

    _UNUSED_TOP_LEVEL_SERVICE = (
        "from __future__ import annotations\n"
        "from collections.abc import Sequence\n\n"
        '__all__: list[str] = ["only_for_cleanup"]\n\n'
        "def only_for_cleanup(values: t.SequenceOf[int]) -> int:\n"
        "    return len(values)\n"
    )

    _UNUSED_LOCAL_SERVICE = (
        "from __future__ import annotations\n\n"
        "def outer(value: int) -> int:\n"
        "    only_for_cleanup = value + 1\n"
        "    return value\n"
    )

    _UNUSED_LOCAL_TEST = (
        "from __future__ import annotations\n\n"
        "from sample_pkg.service import outer\n\n"
        "assert outer(1) == 1\n"
    )

    _DECORATED_UNUSED_SERVICE = (
        "from __future__ import annotations\n\n"
        "import functools\n\n"
        '__all__: list[str] = ["only_for_tests"]\n\n'
        "def log_entry(fn):\n"
        "    @functools.wraps(fn)\n"
        "    def wrapper(*args, **kwargs):\n"
        "        return fn(*args, **kwargs)\n"
        "    return wrapper\n\n"
        "@log_entry\n"
        "def only_for_tests(value: int) -> int:\n"
        "    return value + 1\n"
    )

    _DECORATED_UNUSED_TEST = (
        "from __future__ import annotations\n\n"
        "from sample_pkg.service import only_for_tests\n\n"
        "def test_decorated_only_for_tests() -> None:\n"
        "    assert only_for_tests(1) == 2\n"
    )

    _LAZY_CASCADE_INIT = (
        "# AUTO-GENERATED FILE — Regenerate with: make gen\n"
        '"""Sample package."""\n\n'
        "from __future__ import annotations\n\n"
        "import typing as _t\n\n"
        "from flext_core.lazy import build_lazy_import_map, install_lazy_exports\n\n"
        "if _t.TYPE_CHECKING:\n"
        "    from sample_pkg.operations import helper_used, only_for_tests\n"
        "_LAZY_IMPORTS = build_lazy_import_map(\n"
        "    {\n"
        '        ".operations": ("helper_used", "only_for_tests"),\n'
        "    },\n"
        ")\n\n"
        "install_lazy_exports(__name__, globals(), _LAZY_IMPORTS)\n\n"
        "__all__: list[str] = [\n"
        '    "helper_used",\n'
        '    "only_for_tests",\n'
        "]\n"
    )

    _LAZY_CASCADE_OPERATIONS = (
        "from __future__ import annotations\n\n"
        '__all__: list[str] = ["helper_used", "only_for_tests"]\n\n'
        "def helper_used(value: int) -> int:\n"
        "    return value * 2\n\n"
        "def only_for_tests(value: int) -> int:\n"
        "    return value + 1\n\n"
        "OBSERVED = helper_used(2)\n"
    )

    _LAZY_CASCADE_TEST = (
        "from __future__ import annotations\n\n"
        "from sample_pkg.operations import only_for_tests\n\n"
        "def test_only_for_tests_returns_incremented_value() -> None:\n"
        "    assert only_for_tests(1) == 2\n"
    )

    @staticmethod
    def _parse_source_ast(source: str) -> p.Result[CodeType]:
        try:
            return r[CodeType].ok(compile(source, "<refactor-test-source>", "exec"))
        except SyntaxError as exc:
            return r[CodeType].fail(f"source failed to compile: {exc}", exception=exc)

    @staticmethod
    def _strings(value: t.JsonValue) -> t.StrSequence:
        result: t.StrSequence = t.Infra.STR_SEQ_ADAPTER.validate_python(value)
        return result

    @staticmethod
    def _refactor_main(*args: str) -> int:
        return infra_main(["refactor", *args])

    @staticmethod
    def _write(path: Path, content: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")

    @staticmethod
    def _write_workspace_pyproject(workspace: Path) -> None:
        TestsFlextInfraRefactorMainCli._write(
            workspace / "pyproject.toml",
            "[project]\n"
            'name = "sample-pkg"\n'
            'version = "0.1.0"\n\n'
            "[tool.pyrefly]\n"
            "disable-project-excludes-heuristics = true\n"
            "project-excludes = []\n"
            'search-path = [".", "src"]\n\n' + u.Tests.ruff_per_file_ignores_toml(),
        )

    @classmethod
    def _apply_census(
        cls, workspace: Path, *, rules: str, kinds: str | None = None
    ) -> None:
        """Run one applying census through the CLI, asserting a clean exit."""
        args = [
            "census",
            "--repository-root",
            str(workspace),
            "--apply",
            "--rules",
            rules,
        ]
        if kinds is not None:
            args = [*args, "--kinds", kinds]
        tm.that(cls._refactor_main(*args), eq=0)

    @staticmethod
    def _impact_map_entries(impact_map_path: Path) -> list[t.JsonMapping]:
        """Read the written impact map and return its typed file entries."""
        payload_result = u.Cli.json_read(impact_map_path)
        tm.ok(payload_result)
        payload = u.Tests.toml_mapping(payload_result.unwrap())
        files = t.Cli.JSON_LIST_ADAPTER.validate_python(payload["files"])
        return [u.Tests.toml_mapping(item) for item in files]

    @staticmethod
    def _assert_no_unused_functions(workspace: Path) -> None:
        """Assert the workspace reports no unused function after a cutover."""
        report = u.Tests.census_report(
            workspace, kinds=("function",), rules=("unused",)
        )
        tm.that(report.unused_count, eq=0)
        tm.that(report.removal_candidate_count, eq=0)

    @staticmethod
    def _build_module_workspace(
        tmp_path: Path, module_source: str
    ) -> t.Pair[Path, Path]:
        """Build a lazy-init demo package holding one authored ``models.py``."""
        workspace, package_root = u.Tests.create_lazy_init_workspace(
            tmp_path, project_name="flext-demo", package_name="flext_demo"
        )
        module_path = package_root / "models.py"
        module_path.write_text(module_source, encoding="utf-8")
        return workspace, module_path

    @classmethod
    def _build_service_workspace(
        cls,
        tmp_path: Path,
        *,
        service_source: str,
        test_source: str | None = None,
        init_source: str = _FUTURE_INIT,
    ) -> t.Pair[Path, Path]:
        """Build the ``sample_pkg`` workspace around one service module."""
        workspace = tmp_path / "workspace"
        cls._write_workspace_pyproject(workspace)
        cls._write(workspace / "src" / "sample_pkg" / "__init__.py", init_source)
        service_file = workspace / "src" / "sample_pkg" / "service.py"
        cls._write(service_file, service_source)
        if test_source is not None:
            cls._write(workspace / "tests" / "test_service.py", test_source)
        return workspace, service_file

    @classmethod
    def _build_basic_workspace(cls, tmp_path: Path) -> t.Pair[Path, Path]:
        return cls._build_service_workspace(
            tmp_path, service_source=cls._BASIC_SERVICE, init_source=cls._BASIC_INIT
        )

    @classmethod
    def _build_runtime_alias_duplicate_workspace(
        cls, tmp_path: Path
    ) -> t.Pair[Path, Path]:
        return cls._build_module_workspace(
            tmp_path, cls._DUPLICATE_RUNTIME_ALIAS_MODULE
        )

    @classmethod
    def _build_facade_member_workspace(cls, tmp_path: Path) -> t.Pair[Path, Path]:
        return cls._build_module_workspace(tmp_path, cls._FACADE_MEMBER_MODULE)

    @classmethod
    def _build_compatibility_alias_workspace(cls, tmp_path: Path) -> t.Pair[Path, Path]:
        return cls._build_module_workspace(tmp_path, cls._COMPATIBILITY_ALIAS_MODULE)

    @classmethod
    def _build_test_only_workspace(cls, tmp_path: Path) -> Path:
        return cls._build_service_workspace(
            tmp_path,
            service_source=cls._TEST_ONLY_FUNCTION_SERVICE,
            test_source=cls._TEST_ONLY_FUNCTION_TEST,
        )[0]

    @classmethod
    def _build_test_only_workspace_with_source_import(
        cls, tmp_path: Path
    ) -> t.Pair[Path, Path]:
        return cls._build_service_workspace(
            tmp_path,
            service_source=cls._SEQUENCE_TEST_ONLY_SERVICE,
            test_source=cls._SEQUENCE_TEST_ONLY_TEST,
        )

    @classmethod
    def _build_test_only_method_workspace(cls, tmp_path: Path) -> Path:
        return cls._build_service_workspace(
            tmp_path,
            service_source=cls._TEST_ONLY_METHOD_SERVICE,
            test_source=cls._TEST_ONLY_METHOD_TEST,
        )[0]

    @classmethod
    def _build_unused_nested_function_workspace(cls, tmp_path: Path) -> Path:
        return cls._build_service_workspace(
            tmp_path,
            service_source=cls._UNUSED_NESTED_FUNCTION_SERVICE,
            test_source=cls._UNUSED_NESTED_FUNCTION_TEST,
        )[0]

    @classmethod
    def _build_unused_top_level_workspace_with_source_import(
        cls, tmp_path: Path
    ) -> t.Pair[Path, Path]:
        return cls._build_service_workspace(
            tmp_path, service_source=cls._UNUSED_TOP_LEVEL_SERVICE
        )

    @classmethod
    def _build_unused_local_workspace(cls, tmp_path: Path) -> Path:
        return cls._build_service_workspace(
            tmp_path,
            service_source=cls._UNUSED_LOCAL_SERVICE,
            test_source=cls._UNUSED_LOCAL_TEST,
        )[0]

    @classmethod
    def _build_lazy_init_cascade_workspace(
        cls, tmp_path: Path
    ) -> t.Triple[Path, Path, Path]:
        workspace = tmp_path / "workspace"
        cls._write_workspace_pyproject(workspace)
        init_path = workspace / "src" / "sample_pkg" / "__init__.py"
        cls._write(init_path, cls._LAZY_CASCADE_INIT)
        service_file = workspace / "src" / "sample_pkg" / "operations.py"
        cls._write(service_file, cls._LAZY_CASCADE_OPERATIONS)
        cls._write(workspace / "tests" / "test_operations.py", cls._LAZY_CASCADE_TEST)
        return workspace, service_file, init_path

    def test_refactor_census_accepts_the_repository_root_option(
        self, tmp_path: Path
    ) -> None:
        """The root is a subcommand option, not a group flag ahead of the verb."""
        workspace = tmp_path / "workspace"
        self._write_workspace_pyproject(workspace)
        result = self._refactor_main("census", "--repository-root", str(workspace))
        tm.that(result, eq=0)

    def test_refactor_census_does_not_infer_runtime_alias_from_filename(
        self, tmp_path: Path
    ) -> None:
        """A module that declares no letter never acquires one from its name."""
        workspace, module_path = self._build_module_workspace(
            tmp_path, self._UNDECLARED_RUNTIME_ALIAS_MODULE
        )

        self._apply_census(workspace, rules="runtime_alias")

        source = module_path.read_text(encoding="utf-8")
        tm.that(source, lacks='"m"')
        tm.that(source, lacks="m = FlextDemoModels")

    def test_refactor_census_binds_declared_runtime_alias(self, tmp_path: Path) -> None:
        """A letter declared in ``__all__`` receives its derived facade binding."""
        workspace, module_path = self._build_module_workspace(
            tmp_path, self._MISSING_RUNTIME_ALIAS_MODULE
        )

        self._apply_census(workspace, rules="runtime_alias")

        source = module_path.read_text(encoding="utf-8")
        tm.that(source, has="m = FlextDemoModels")

    def test_refactor_census_reports_duplicate_runtime_alias(
        self, tmp_path: Path
    ) -> None:
        workspace, _ = self._build_runtime_alias_duplicate_workspace(tmp_path)

        report = u.Tests.census_report(
            workspace, kinds=("class",), rules=("runtime_alias",)
        )
        violations = u.Tests.census_violations(report)

        tm.that(len(violations), eq=1)
        tm.that(report.fixes_total, eq=1)
        tm.that(violations[0].kind, eq="runtime_alias")
        tm.that(violations[0].object_name, eq="FlextDemoModels")
        tm.that(violations[0].description, has="Found 2 'm = ...' assignments")

    def test_refactor_census_reports_manual_typing_alias(self, tmp_path: Path) -> None:
        workspace, _ = self._build_basic_workspace(tmp_path)

        report = u.Tests.census_report(
            workspace, kinds=("assignment",), rules=("manual_typing_alias",)
        )
        violations = u.Tests.census_violations(report)

        tm.that(len(violations), eq=1)
        tm.that(report.fixes_total, eq=1)
        tm.that(violations[0].kind, eq="manual_typing_alias")
        tm.that(violations[0].object_name, eq="PayloadMap")
        tm.that(violations[0].object_kind, eq="assignment")
        tm.that(violations[0].description, has="typings scope")

    def test_refactor_census_reports_compatibility_alias(self, tmp_path: Path) -> None:
        workspace, _ = self._build_compatibility_alias_workspace(tmp_path)

        report = u.Tests.census_report(
            workspace, kinds=("class",), rules=("compatibility_alias",)
        )
        violations = u.Tests.census_violations(report)

        tm.that(len(violations), eq=1)
        tm.that(report.fixes_total, eq=1)
        tm.that(violations[0].kind, eq="compatibility_alias")
        tm.that(violations[0].object_name, eq="LegacyThing")
        tm.that(violations[0].object_kind, eq="class")
        tm.that(violations[0].description, has="should use 'NewThing' directly")

    @pytest.mark.parametrize(
        ("builder_name", "kinds", "rules", "expected_kind"),
        [
            (
                "_build_runtime_alias_duplicate_workspace",
                ("class",),
                ("runtime_alias",),
                "runtime_alias",
            ),
            (
                "_build_basic_workspace",
                ("assignment",),
                ("manual_typing_alias",),
                "manual_typing_alias",
            ),
            (
                "_build_compatibility_alias_workspace",
                ("class",),
                ("compatibility_alias",),
                "compatibility_alias",
            ),
        ],
    )
    def test_refactor_census_detector_rules_report_public_violations(
        self,
        tmp_path: Path,
        builder_name: str,
        kinds: t.StrSequence,
        rules: t.StrSequence,
        expected_kind: str,
    ) -> None:
        builder = getattr(self, builder_name)
        built_workspace = builder(tmp_path)
        workspace = (
            built_workspace[0]
            if isinstance(built_workspace, tuple)
            else built_workspace
        )

        report = u.Tests.census_report(workspace, kinds=kinds, rules=rules)
        violations = u.Tests.census_violations(report)

        tm.that(violations, empty=False)
        tm.that(
            all(violation.kind == expected_kind for violation in violations), eq=True
        )

    def test_refactor_census_apply_rewrites_manual_typing_alias(
        self, tmp_path: Path
    ) -> None:
        workspace, service_file = self._build_basic_workspace(tmp_path)
        typings_file = service_file.parent / "typings.py"

        self._apply_census(workspace, rules="manual_typing_alias")

        service_source = service_file.read_text(encoding="utf-8")
        typings_source = typings_file.read_text(encoding="utf-8")
        tm.that(service_source, lacks="PayloadMap: TypeAlias = t.StrMapping")
        tm.that(service_source, has="from sample_pkg.typings import PayloadMap")
        tm.that(typings_source, has="type PayloadMap = t.StrMapping")
        tm.that(typings_source, has="from flext_core import t")

    def test_refactor_census_apply_rewrites_compatibility_alias(
        self, tmp_path: Path
    ) -> None:
        workspace, module_path = self._build_compatibility_alias_workspace(tmp_path)

        self._apply_census(workspace, rules="compatibility_alias")

        source = module_path.read_text(encoding="utf-8")
        tm.that(source, lacks="LegacyThing = NewThing")
        tm.that(source, has="class NewThing:")

    def test_refactor_census_flags_unused_when_only_tests_reference_source(
        self, tmp_path: Path
    ) -> None:
        workspace = self._build_test_only_workspace(tmp_path)

        report = u.Tests.census_report(
            workspace, kinds=("function",), rules=("unused",)
        )
        violations = u.Tests.census_violations(report)

        tm.that(report.unused_count, eq=1)
        tm.that(report.removal_candidate_count, eq=1)
        tm.that(len(report.removal_candidates), eq=1)
        tm.that(len(violations), eq=1)
        tm.that(violations[0].kind, eq="unused")
        tm.that(violations[0].object_name, eq="only_for_tests")
        candidate = report.removal_candidates[0]
        tm.that(candidate.reason, eq="unused")
        tm.that(candidate.suggested_action, eq="delete_object_definition")
        tm.that(candidate.runtime_reference_sites, eq=())

        rendered = FlextInfraRefactorCensus.render_text(report)
        tm.that(rendered, has="Unused: 1")
        tm.that(rendered, has="Removal candidates:")
        tm.that(rendered, has="Candidate preview:")

    def test_refactor_census_keeps_facade_members_out_of_removal_candidates(
        self, tmp_path: Path
    ) -> None:
        workspace, _module_path = self._build_facade_member_workspace(tmp_path)

        report = u.Tests.census_report(
            workspace, kinds=("class", "assignment"), rules=("unused",)
        )

        tm.that(report.unused_count, eq=0)
        tm.that(report.removal_candidate_count, eq=0)
        tm.that(report.removal_candidates, eq=())

    def test_refactor_census_apply_removes_unused_source_without_touching_tests(
        self, tmp_path: Path
    ) -> None:
        workspace = self._build_test_only_workspace(tmp_path)
        service_file = workspace / "src" / "sample_pkg" / "service.py"
        test_file = workspace / "tests" / "test_service.py"

        self._apply_census(workspace, rules="unused", kinds="function")

        service_source = service_file.read_text(encoding="utf-8")
        test_source = test_file.read_text(encoding="utf-8")
        tm.that(service_source, lacks="only_for_tests")
        tm.that(test_source, has="only_for_tests")
        tm.ok(self._parse_source_ast(service_source))
        tm.ok(self._parse_source_ast(test_source))

        self._assert_no_unused_functions(workspace)

    def test_refactor_census_preserves_published_lazy_exports(
        self, tmp_path: Path
    ) -> None:
        workspace, helpers_file, init_path = self._build_lazy_init_cascade_workspace(
            tmp_path
        )
        test_file = workspace / "tests" / "test_operations.py"

        self._assert_no_unused_functions(workspace)
        self._apply_census(workspace, rules="unused", kinds="function")

        init_source = init_path.read_text(encoding="utf-8")
        helpers_source = helpers_file.read_text(encoding="utf-8")
        test_source = test_file.read_text(encoding="utf-8")

        tm.that(init_source, has="only_for_tests")
        tm.that(helpers_source, has="only_for_tests")
        tm.that(test_source, has="only_for_tests")
        # A symbol exported through the package facade is a live public contract,
        # including when its observed consumer is a test. Census must not delete
        # it or rewrite the generator-owned facade behind the consumer's back.
        tm.that(init_source, has="install_lazy_exports(")
        tm.that(init_source, has="build_lazy_import_map(")
        tm.that(init_source, has="helper_used")
        tm.that(helpers_source, has="helper_used")
        tm.ok(self._parse_source_ast(init_source))
        tm.ok(self._parse_source_ast(helpers_source))
        tm.ok(self._parse_source_ast(test_source))

        self._assert_no_unused_functions(workspace)

        probe = tm.ok(
            u.Cli.run(
                [
                    sys.executable,
                    "-c",
                    (
                        "import sample_pkg; "
                        "print(sample_pkg.only_for_tests(1)); "
                        "print(sample_pkg.helper_used(2))"
                    ),
                ],
                cwd=workspace / "src",
            )
        )
        tm.that(probe.stdout.splitlines(), eq=["2", "4"])

    def test_refactor_census_apply_removes_decorated_unused_function(
        self, tmp_path: Path
    ) -> None:
        workspace, service_file = self._build_service_workspace(
            tmp_path,
            service_source=self._DECORATED_UNUSED_SERVICE,
            test_source=self._DECORATED_UNUSED_TEST,
        )

        self._apply_census(workspace, rules="unused", kinds="function")

        service_source = service_file.read_text(encoding="utf-8")
        tm.that(service_source, lacks="only_for_tests")
        tm.that(service_source, lacks="@log_entry")
        tm.that(service_source, has="def log_entry")
        tm.ok(self._parse_source_ast(service_source))

    def test_refactor_census_strip_module_all_entry_multi_line(self) -> None:
        source = (
            "from __future__ import annotations\n\n"
            "__all__: list[str] = [\n"
            '    "alpha",\n'
            '    "beta",\n'
            '    "gamma",\n'
            "]\n"
        )
        stripped = u.Infra.strip_module_all_entry(source, "beta")
        tm.that(stripped, lacks='"beta"')
        tm.that(stripped, has='"alpha"')
        tm.that(stripped, has='"gamma"')

    def test_refactor_census_apply_against_cloned_flext_layout(
        self, tmp_path: Path
    ) -> None:
        origin, origin_helpers, origin_init = self._build_lazy_init_cascade_workspace(
            tmp_path
        )
        clone = u.Infra.clone_project_for_validation(
            origin, tmp_path / "clone_root" / "workspace"
        )
        clone_helpers = clone / origin_helpers.relative_to(origin)
        clone_init = clone / origin_init.relative_to(origin)
        clone_test = clone / "tests" / "test_operations.py"

        self._apply_census(clone, rules="unused", kinds="function")

        tm.that(origin_helpers.read_text(encoding="utf-8"), has="only_for_tests")
        tm.that(origin_init.read_text(encoding="utf-8"), has="only_for_tests")
        tm.that(clone_helpers.read_text(encoding="utf-8"), has="only_for_tests")
        tm.that(clone_init.read_text(encoding="utf-8"), has="only_for_tests")
        tm.that(clone_test.read_text(encoding="utf-8"), has="only_for_tests")
        # Why: e75d5aa6f retired the named `_LAZY_IMPORTS` variable for
        # generated inits in favor of an inlined build_lazy_import_map(...)
        # argument — align to the proven runtime (see the sibling assertion
        # above in test_refactor_census_apply_cascades_through_init_lazy_map_and_all).
        clone_init_source = clone_init.read_text(encoding="utf-8")
        tm.that(clone_init_source, has="install_lazy_exports(")
        tm.that(clone_init_source, has="build_lazy_import_map(")

        report = u.Tests.census_report(clone, kinds=("function",), rules=("unused",))
        tm.that(report.unused_count, eq=0)

    def test_refactor_census_apply_removes_unused_top_level_and_cleans_imports(
        self, tmp_path: Path
    ) -> None:
        workspace, service_file = (
            self._build_unused_top_level_workspace_with_source_import(tmp_path)
        )

        self._apply_census(workspace, rules="unused", kinds="function")

        service_source = service_file.read_text(encoding="utf-8")
        tm.that(service_source, lacks="def only_for_cleanup")
        tm.that(service_source, lacks="from collections.abc import Sequence")
        tm.ok(self._parse_source_ast(service_source))

        self._assert_no_unused_functions(workspace)

    def test_refactor_census_dry_run_validates_candidate_after_import_cleanup(
        self, tmp_path: Path
    ) -> None:
        workspace, service_file = self._build_test_only_workspace_with_source_import(
            tmp_path
        )

        report = u.Tests.census_report(
            workspace, kinds=("function",), rules=("unused",)
        )

        tm.that(report.unused_count, eq=1)
        tm.that(report.removal_candidate_count, eq=1)
        tm.that(report.removal_candidates[0].object_name, eq="only_for_tests")
        service_source = service_file.read_text(encoding="utf-8")
        tm.that(service_source, has="from collections.abc import Sequence")
        tm.that(service_source, has="def only_for_tests")

    def test_refactor_census_apply_dry_run_does_not_mutate_files(
        self, tmp_path: Path
    ) -> None:
        workspace = self._build_test_only_workspace(tmp_path)
        service_file = workspace / "src" / "sample_pkg" / "service.py"
        test_file = workspace / "tests" / "test_service.py"

        report = u.Tests.census_report(
            workspace,
            kinds=("function",),
            rules=("unused",),
            apply_changes=True,
            dry_run=True,
        )

        tm.that(report.unused_count, eq=1)
        tm.that(report.removal_candidate_count, eq=1)
        tm.that(service_file.read_text(encoding="utf-8"), has="only_for_tests")
        tm.that(test_file.read_text(encoding="utf-8"), has="only_for_tests")

    def _assert_dry_run_one_violation_no_candidate(
        self,
        workspace: Path,
        *,
        impact_map_path: Path,
        kind: str,
        rule: str,
        count_attr: str,
        expected_object_name: str,
    ) -> None:
        """Assert one violation detected with no removal candidate.

        Bundle: ``kind``/``rule`` violation detected, no removal candidate
        produced, empty impact-map ``files``.
        """
        report = u.Tests.census_report(
            workspace,
            kinds=(kind,),
            rules=(rule,),
            include_local_scopes=True,
            impact_map_output=str(impact_map_path),
        )
        violations = u.Tests.census_violations(report)
        tm.that(getattr(report, count_attr), eq=1)
        tm.that(report.removal_candidate_count, eq=0)
        tm.that(len(report.removal_candidates), eq=0)
        tm.that(len(violations), eq=1)
        tm.that(violations[0].kind, eq=rule)
        tm.that(violations[0].object_kind, eq=kind)
        tm.that(violations[0].object_name, eq=expected_object_name)
        tm.that(len(self._impact_map_entries(impact_map_path)), eq=0)

    def test_refactor_census_dry_run_excludes_unsupported_method_candidate(
        self, tmp_path: Path
    ) -> None:
        self._assert_dry_run_one_violation_no_candidate(
            self._build_test_only_method_workspace(tmp_path),
            impact_map_path=tmp_path / "method-impact-map.json",
            kind="method",
            rule="unused",
            count_attr="unused_count",
            expected_object_name="only_for_tests",
        )

    def test_refactor_census_dry_run_excludes_unsupported_nested_unused_function(
        self, tmp_path: Path
    ) -> None:
        self._assert_dry_run_one_violation_no_candidate(
            self._build_unused_nested_function_workspace(tmp_path),
            impact_map_path=tmp_path / "nested-unused-impact-map.json",
            kind="function",
            rule="unused",
            count_attr="unused_count",
            expected_object_name="only_for_cleanup",
        )

    def test_refactor_census_dry_run_validates_unused_candidate_after_import_cleanup(
        self, tmp_path: Path
    ) -> None:
        workspace, service_file = (
            self._build_unused_top_level_workspace_with_source_import(tmp_path)
        )
        impact_map_path = tmp_path / "unused-impact-map.json"

        report = u.Tests.census_report(
            workspace,
            kinds=("function",),
            rules=("unused",),
            impact_map_output=str(impact_map_path),
        )

        tm.that(report.unused_count, eq=1)
        tm.that(report.removal_candidate_count, eq=1)
        candidate = report.removal_candidates[0]
        tm.that(candidate.object_name, eq="only_for_cleanup")
        tm.that(candidate.reason, eq="unused")
        tm.that(candidate.suggested_action, eq="delete_object_definition")
        service_source = service_file.read_text(encoding="utf-8")
        tm.that(service_source, has="from collections.abc import Sequence")
        tm.that(service_source, has="def only_for_cleanup")

        entries = self._impact_map_entries(impact_map_path)

        tm.that(len(entries), eq=1)
        service_entry = entries[0]
        tm.that(service_entry["modified"], eq=True)
        tm.that(service_entry["success"], eq=True)
        tm.that(
            list(self._strings(service_entry["changes"])),
            eq=["delete_object_definition: only_for_cleanup (unused)"],
        )

    def test_refactor_census_dry_run_excludes_unsupported_local_unused_object(
        self, tmp_path: Path
    ) -> None:
        self._assert_dry_run_one_violation_no_candidate(
            self._build_unused_local_workspace(tmp_path),
            impact_map_path=tmp_path / "local-unused-impact-map.json",
            kind="local",
            rule="unused",
            count_attr="unused_count",
            expected_object_name="only_for_cleanup",
        )

    def test_refactor_census_writes_impact_map_for_removal_candidates(
        self, tmp_path: Path
    ) -> None:
        workspace = self._build_test_only_workspace(tmp_path)
        impact_map_path = tmp_path / "impact-map.json"

        u.Tests.census_report(
            workspace,
            kinds=("function",),
            rules=("unused",),
            impact_map_output=str(impact_map_path),
        )
        entries = self._impact_map_entries(impact_map_path)

        tm.that(len(entries), eq=1)
        service_path = str((workspace / "src" / "sample_pkg" / "service.py").resolve())
        service_entry = next(item for item in entries if item["path"] == service_path)

        tm.that(service_entry["modified"], eq=True)
        tm.that(service_entry["success"], eq=True)
        tm.that(
            list(self._strings(service_entry["changes"])),
            eq=["delete_object_definition: only_for_tests (unused)"],
        )

    def test_refactor_census_cli_writes_impact_map_for_removal_candidates(
        self, tmp_path: Path
    ) -> None:
        workspace = self._build_test_only_workspace(tmp_path)
        impact_map_path = tmp_path / "cli-impact-map.json"

        result = self._refactor_main(
            "census",
            "--repository-root",
            str(workspace),
            "--rules",
            "unused",
            "--kinds",
            "function",
            "--impact-map-output",
            str(impact_map_path),
        )

        tm.that(result, eq=0)
        tm.that(len(self._impact_map_entries(impact_map_path)), eq=1)

    def test_refactor_census_apply_preserves_impact_map_plan(
        self, tmp_path: Path
    ) -> None:
        workspace = self._build_test_only_workspace(tmp_path)
        impact_map_path = tmp_path / "apply-impact-map.json"

        report = u.Tests.census_report(
            workspace,
            kinds=("function",),
            rules=("unused",),
            apply_changes=True,
            impact_map_output=str(impact_map_path),
        )

        tm.that(report.unused_count, eq=0)
        tm.that(report.removal_candidate_count, eq=0)

        tm.that(len(self._impact_map_entries(impact_map_path)), eq=1)
