"""Test detection classify behavior."""

from __future__ import annotations

from typing import TYPE_CHECKING

from flext_tests import tm

from flext_infra.deps.detection import FlextInfraDependencyDetectionService

if TYPE_CHECKING:
    from tests import t


class TestsFlextInfraDepsDetectionClassify:
    """Test flext infra deps detection classify behavior."""

    @staticmethod
    def test_classify_dep001() -> None:
        """Verify classify dep001."""
        service = FlextInfraDependencyDetectionService()
        issues: t.SequenceOf[t.JsonMapping] = [
            {"error": {"code": "DEP001"}, "module": "foo"},
        ]
        tm.that(len(service.classify_issues(issues).dep001), eq=1)

    @staticmethod
    def test_classify_dep002() -> None:
        """Verify classify dep002."""
        service = FlextInfraDependencyDetectionService()
        issues: t.SequenceOf[t.JsonMapping] = [
            {"error": {"code": "DEP002"}, "module": "bar"},
        ]
        tm.that(len(service.classify_issues(issues).dep002), eq=1)

    @staticmethod
    def test_classify_dep003() -> None:
        """Verify classify dep003."""
        service = FlextInfraDependencyDetectionService()
        issues: t.SequenceOf[t.JsonMapping] = [
            {"error": {"code": "DEP003"}, "module": "baz"},
        ]
        tm.that(len(service.classify_issues(issues).dep003), eq=1)

    @staticmethod
    def test_classify_dep004() -> None:
        """Verify classify dep004."""
        service = FlextInfraDependencyDetectionService()
        issues: t.SequenceOf[t.JsonMapping] = [
            {"error": {"code": "DEP004"}, "module": "qux"},
        ]
        tm.that(len(service.classify_issues(issues).dep004), eq=1)

    @staticmethod
    def test_non_dict_error_skipped() -> None:
        """Verify non dict error skipped."""
        service = FlextInfraDependencyDetectionService()
        issues: t.SequenceOf[t.JsonMapping] = [{"error": "not-a-dict", "module": "foo"}]
        tm.that(len(service.classify_issues(issues).dep001), eq=0)

    @staticmethod
    def test_missing_code_skipped() -> None:
        """Verify missing code skipped."""
        service = FlextInfraDependencyDetectionService()
        issues: t.SequenceOf[t.JsonMapping] = [
            {"error": {"other": "data"}, "module": "foo"},
        ]
        tm.that(len(service.classify_issues(issues).dep001), eq=0)

    @staticmethod
    def test_unknown_code_skipped() -> None:
        """Verify unknown code skipped."""
        service = FlextInfraDependencyDetectionService()
        issues: t.SequenceOf[t.JsonMapping] = [
            {"error": {"code": "DEP999"}, "module": "foo"},
        ]
        groups = service.classify_issues(issues)
        tm.that(groups.dep001, eq=[])
        tm.that(groups.dep002, eq=[])
        tm.that(groups.dep003, eq=[])
        tm.that(groups.dep004, eq=[])

    @staticmethod
    def test_multiple_issues() -> None:
        """Verify multiple issues."""
        service = FlextInfraDependencyDetectionService()
        issues: t.SequenceOf[t.JsonMapping] = [
            {"error": {"code": "DEP001"}, "module": "a"},
            {"error": {"code": "DEP002"}, "module": "b"},
            {"error": {"code": "DEP001"}, "module": "c"},
        ]
        groups = service.classify_issues(issues)
        tm.that(len(groups.dep001), eq=2)
        tm.that(len(groups.dep002), eq=1)

    @staticmethod
    def test_classify_issues_with_missing_error_field() -> None:
        """Verify classify issues with missing error field."""
        service = FlextInfraDependencyDetectionService()
        issues: t.SequenceOf[t.JsonMapping] = [{"module": "foo"}]
        tm.that(len(service.classify_issues(issues).dep001), eq=0)

    @staticmethod
    def test_builds_report() -> None:
        """Verify builds report."""
        service = FlextInfraDependencyDetectionService()
        issues: t.SequenceOf[t.JsonMapping] = [
            {"error": {"code": "DEP001"}, "module": "foo"},
            {"error": {"code": "DEP002"}, "module": "bar"},
        ]
        report = service.build_project_report("test-project", issues)
        tm.that(report.project, eq="test-project")
        tm.that(report.deptry.raw_count, eq=2)

    @staticmethod
    def test_module_to_types_package_with_custom_limits() -> None:
        """Verify module to types package with custom limits."""
        service = FlextInfraDependencyDetectionService()
        inner = FlextInfraDependencyDetectionService.to_infra_value({
            "custom_module": "types-custom",
        })
        tm.that(inner, none=False)
        limits: t.MappingKV[str, t.JsonValue] = {
            "typing_libraries": {"module_to_package": inner},
        }
        tm.that(
            service.module_to_types_package("custom_module", limits),
            eq="types-custom",
        )
