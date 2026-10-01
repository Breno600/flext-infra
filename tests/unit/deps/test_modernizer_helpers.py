"""Test modernizer helpers behavior."""

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar

import pytest
from flext_tests import tm

from tests import c, u

if TYPE_CHECKING:
    from tests import t


class TestsFlextInfraDepsModernizerHelpers:
    """Behavior contract for test_modernizer_helpers."""

    _FULL_OPTIONAL_DEPS: ClassVar[t.MappingKV[str, t.StrSequence]] = {
        "dev": ["pytest"],
        "docs": ["sphinx"],
        "security": ["bandit"],
        "test": ["coverage"],
        "typings": ["mypy"],
    }

    @pytest.fixture
    def doc(self) -> t.Cli.TomlDocument:
        """Provide a mutable TOML document fixture."""
        return u.Cli.toml_document()

    @staticmethod
    def _toml_table_item() -> t.Cli.TomlItem:
        tbl = u.Cli.toml_table()
        tbl["key"] = "value"
        return tbl

    @staticmethod
    def _doc_with_optional_deps(
        optional_deps: t.MappingKV[str, t.StrSequence],
    ) -> t.Cli.TomlDocument:
        doc = u.Cli.toml_document()
        doc["project"] = {"optional-dependencies": optional_deps}
        return doc

    @pytest.mark.parametrize(
        ("raw", "expected"),
        [
            ("requests", "requests"),
            ("requests>=2.0", "requests"),
            ("requests @ git+https://github.com/psf/requests.git", "requests"),
            ("../flext-core", "flext-core"),
            ("my_package", "my-package"),
            ("  requests  ", "requests"),
            ("", None),
            ("Django>=3.0,<4.0", "django"),
        ],
    )
    def test_dep_name(self, raw: str, expected: str | None) -> None:
        """Verify dep name."""
        tm.that(u.Infra.dep_name(raw), eq=expected)

    @pytest.mark.parametrize(
        ("specs", "expected_length", "expected_names", "check_sorted"),
        [
            (["requests>=2.0", "django>=3.0"], 2, ["requests", "django"], False),
            (["requests>=2.0", "requests>=2.1", "django>=3.0"], 2, ["requests"], False),
            ([], 0, [], False),
            (["zebra>=1.0", "apple>=1.0"], 2, [], True),
            (["Requests>=2.0", "requests>=2.1"], 1, ["requests"], False),
        ],
    )
    def test_dedupe_specs(
        self,
        specs: t.StrSequence,
        expected_length: int,
        expected_names: t.StrSequence,
        *,
        check_sorted: bool,
    ) -> None:
        """Verify dedupe specs."""
        deduped = u.Infra.dedupe_specs(specs)
        tm.that(deduped, length=expected_length)
        names = [u.Infra.dep_name(spec) for spec in deduped]
        for expected_name in expected_names:
            tm.that(names, has=expected_name)
        if check_sorted and len(deduped) > 1:
            left = u.Infra.dep_name(deduped[0])
            right = u.Infra.dep_name(deduped[1])
            tm.that(left, none=False)
            tm.that(right, none=False)
            if left is None or right is None:
                pytest.fail("deduplicated dependency names must be present")
            tm.that(left < right, eq=True)

    @pytest.mark.parametrize(
        ("value", "expected"),
        [("test", "test"), (None, None), ({"key": "value"}, {"key": "value"})],
    )
    def test_unwrap_item(
        self, value: t.Cli.TomlMappingSource | None, expected: t.JsonValue
    ) -> None:
        """Verify unwrap item."""
        actual = None if value is None else u.Cli.toml_unwrap_item(value)
        tm.that(actual, eq=expected)

    def test_unwrap_item_toml_item(self, doc: t.Cli.TomlDocument) -> None:
        """Verify unwrap item toml item."""
        doc["key"] = "value"
        tm.that(u.Cli.toml_unwrap_item(doc["key"]), eq="value")

    @pytest.mark.parametrize(
        ("value", "expected"),
        [
            (u.Cli.toml_item_from_json_value(["a", "b", "c"]), ["a", "b", "c"]),
            (None, []),
            (u.Cli.toml_item_from_json_value("test"), []),
            (_toml_table_item(), []),
            (u.Cli.toml_item_from_json_value(42), []),
        ],
    )
    def test_as_string_list(
        self, value: t.Cli.TomlItem | None, expected: t.StrSequence
    ) -> None:
        """Verify as string list."""
        actual: t.StrSequence = (
            [] if value is None else u.Cli.toml_as_string_list(value)
        )
        tm.that(list(actual), eq=list(expected))

    def test_as_string_list_toml_item(self, doc: t.Cli.TomlDocument) -> None:
        """Verify as string list toml item."""
        doc["items"] = ["a", "b"]
        items_array = u.Cli.toml_item_from_json_value(["a", "b"])
        tm.that(u.Cli.toml_as_string_list(items_array), eq=["a", "b"])
        doc["value"] = 42
        int_val = u.Cli.toml_item_from_json_value(42)
        tm.that(u.Cli.toml_as_string_list(int_val), eq=[])

    @pytest.mark.parametrize(
        ("items", "expected"), [(["a", "b", "c"], 3), ([], 0), (["single"], 1)]
    )
    def test_array(self, items: t.StrSequence, expected: int) -> None:
        """Verify TOML array construction preserves item count."""
        tm.that(len(u.Cli.toml_array(items)), eq=expected)

    @pytest.mark.parametrize("mode", ["new", "existing", "replace-non-table"])
    def test_ensure_table(self, mode: str) -> None:
        """Verify ensure table."""
        parent = u.Cli.toml_table()
        if mode == "existing":
            existing = u.Cli.toml_table()
            parent["key"] = existing
            ensured = u.Cli.toml_ensure_table(parent, "key")
            tm.that(ensured is existing, eq=True)
            return
        if mode == "replace-non-table":
            parent["key"] = "string_value"
            _ = u.Cli.toml_ensure_table(parent, "key")
            tm.that(parent, has="key")
            return
        _ = u.Cli.toml_ensure_table(parent, "key")
        tm.that(parent, has="key")

    @pytest.mark.parametrize(
        ("optional_deps", "expected_dev", "expected_docs"),
        [
            (_FULL_OPTIONAL_DEPS, ["pytest"], ["sphinx"]),
            ({"dev": ["pytest"]}, ["pytest"], []),
            ({}, [], []),
        ],
    )
    def test_project_dev_groups(
        self,
        optional_deps: t.MappingKV[str, t.StrSequence],
        expected_dev: t.StrSequence,
        expected_docs: t.StrSequence,
    ) -> None:
        """Verify project dev groups."""
        groups = u.Infra.project_dev_groups(self._doc_with_optional_deps(optional_deps))
        tm.that(list(groups.get("dev", [])), eq=list(expected_dev))
        tm.that(list(groups.get("docs", [])), eq=list(expected_docs))

    def test_project_dev_groups_missing_sections(self, doc: t.Cli.TomlDocument) -> None:
        """Verify project dev groups missing sections."""
        tm.that(u.Infra.project_dev_groups(doc), eq={})
        doc["project"] = {"name": "test"}
        tm.that(u.Infra.project_dev_groups(doc), eq={})

    @pytest.mark.parametrize(
        ("optional_deps", "expected_length", "expect_pytest"),
        [
            (_FULL_OPTIONAL_DEPS, 5, True),
            ({}, 0, False),
            ({"dev": ["pytest>=7.0"], "test": ["pytest>=6.0"]}, 1, True),
        ],
    )
    def test_canonical_dev_dependencies(
        self,
        optional_deps: t.MappingKV[str, t.StrSequence],
        expected_length: int,
        *,
        expect_pytest: bool,
    ) -> None:
        """Verify canonical dev dependencies."""
        result = u.Infra.canonical_dev_dependencies(
            self._doc_with_optional_deps(optional_deps)
        )
        tm.that(result, length=expected_length)
        if expect_pytest:
            tm.that(any("pytest" in item for item in result), eq=True)

    def test_declared_dependency_names_collects_all_supported_groups(self) -> None:
        """Verify declared dependency names collects all supported groups."""
        doc = u.Cli.toml_document()
        doc["project"] = {
            "dependencies": ["requests>=2.0"],
            "optional-dependencies": {
                "dev": ["flext-infra", "pytest>=8.0"],
                "docs": ["mkdocs>=1.6"],
            },
        }
        doc["dependency-groups"] = {"test": ["flext-tests", "coverage>=7.0"]}
        doc["tool"] = {
            "poetry": {
                "dependencies": {"python": ">=3.13,<3.14", "flext-api": "^0.1.0"}
            }
        }

        result = u.Infra.declared_dependency_names(doc)

        tm.that(result, has="requests")
        tm.that(result, has="flext-infra")
        tm.that(result, has="flext-tests")

    def test_resolved_dependency_versions_excludes_editable_distribution(self) -> None:
        """Registry versions exclude editable source distributions."""
        versions = u.Infra.resolved_dependency_versions()
        tm.that(bool(versions), eq=True)
        tm.that("flext-infra" in versions, eq=False)

    def test_rewrite_requirement_constraint_preserves_extras_and_markers(self) -> None:
        """Verify rewrite requirement constraint preserves extras and markers."""
        locked_version = c.Tests.RELEASE_VERSION_TARGET
        tm.that(
            u.Infra.rewrite_requirement_constraint(
                "httpx[socks]>=0.1; python_version < '3.14'",
                resolved_versions={"httpx": locked_version},
            ),
            eq=f"httpx[socks]>={locked_version}; python_version < '3.14'",
        )
