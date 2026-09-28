"""Test detection classify behavior."""

from __future__ import annotations

from typing import TYPE_CHECKING

from flext_tests import tm

from flext_infra.deps.detection import FlextInfraDependencyDetectionService

if TYPE_CHECKING:
    from tests import t


class TestsFlextInfraDepsDetectionClassify:
    """Test flext infra deps detection classify behavior."""

    def test_classify_dep001(self) -> None:
        """Verify classify dep001."""
        service = FlextInfraDependencyDetectionService()
        issues: t.SequenceOf[t.JsonMapping] = [
            {"error": {"code": "DEP001"}, "module": "foo"}
        ]
        tm.that(len(service.classify_issues(issues).dep001), eq=1)

    def test_classify_dep002(self) -> None:
        """Verify classify dep002."""
        service = FlextInfraDependencyDetectionService()
        issues: t.SequenceOf[t.JsonMapping] = [
            {"error": {"code": "DEP002"}, "module": "bar"}
        ]
        tm.that(len(service.classify_issues(issues).dep002), eq=1)

    def test_classify_dep003(self) -> None:
        """Verify classify dep003."""
        service = FlextInfraDependencyDetectionService()
        issues: t.SequenceOf[t.JsonMapping] = [
            {"error": {"code": "DEP003"}, "module": "baz"}
        ]
        tm.that(len(service.classify_issues(issues).dep003), eq=1)

    def test_classify_dep004(self) -> None:
        """Verify classify dep004."""
        service = FlextInfraDependencyDetectionService()
        issues: t.SequenceOf[t.JsonMapping] = [
            {"error": {"code": "DEP004"}, "module": "qux"}
        ]
        tm.that(len(service.classify_issues(issues).dep004), eq=1)

    def test_non_dict_error_skipped(self) -> None:
        """Verify non dict error skipped."""
        service = FlextInfraDependencyDetectionService()
        issues: t.SequenceOf[t.JsonMapping] = [{"error": "not-a-dict", "module": "foo"}]
        tm.that(len(service.classify_issues(issues).dep001), eq=0)

    def test_missing_code_skipped(self) -> None:
        """Verify missing code skipped."""
        service = FlextInfraDependencyDetectionService()
        issues: t.SequenceOf[t.JsonMapping] = [
            {"error": {"other": "data"}, "module": "foo"}
        ]
        tm.that(len(service.classify_issues(issues).dep001), eq=0)

    def test_unknown_code_skipped(self) -> None:
        """Verify unknown code skipped."""
        service = FlextInfraDependencyDetectionService()
        issues: t.SequenceOf[t.JsonMapping] = [
            {"error": {"code": "DEP999"}, "module": "foo"}
        ]
        groups = service.classify_issues(issues)
        tm.that(groups.dep001, eq=[])
        tm.that(groups.dep002, eq=[])
        tm.that(groups.dep003, eq=[])
        tm.that(groups.dep004, eq=[])

    def test_multiple_issues(self) -> None:
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

    def test_classify_issues_with_missing_error_field(self) -> None:
        """Verify classify issues with missing error field."""
        service = FlextInfraDependencyDetectionService()
        issues: t.SequenceOf[t.JsonMapping] = [{"module": "foo"}]
        tm.that(len(service.classify_issues(issues).dep001), eq=0)

    def test_builds_report(self) -> None:
        """Verify builds report."""
        service = FlextInfraDependencyDetectionService()
        issues: t.SequenceOf[t.JsonMapping] = [
            {"error": {"code": "DEP001"}, "module": "foo"},
            {"error": {"code": "DEP002"}, "module": "bar"},
        ]
        report = service.build_project_report("test-project", issues)
        tm.that(report.project, eq="test-project")
        tm.that(report.deptry.raw_count, eq=2)

    def test_module_to_types_package_with_custom_limits(self) -> None:
        """Verify module to types package with custom limits."""
        service = FlextInfraDependencyDetectionService()
        inner = FlextInfraDependencyDetectionService.to_infra_value({
            "custom_module": "types-custom"
        })
        tm.that(inner, none=False)
        limits: t.MappingKV[str, t.JsonValue] = {
            "typing_libraries": {"module_to_package": inner}
        }
        tm.that(
            service.module_to_types_package("custom_module", limits), eq="types-custom"
        )
