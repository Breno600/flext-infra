"""Tests for Rule 4: Annotation rules."""

from __future__ import annotations

from pathlib import Path

from flext_tests import tm

from tests import u


class TestsFlextInfraRule4Annotations:
    """Test suite for namespace validator Rule 4 (annotations)."""

    def test_rule4_annotated_field_factory_not_flagged_as_banned(
        self, tmp_path: Path
    ) -> None:
        """D1-precision: Annotated metadata factory values are not annotations.

        The canonical Flext<X>Settings pattern embeds the Pydantic field factory
        in the annotation metadata:
        ``Annotated[t.MappingKV[str, str], m.Field(default_factory=dict)]``.
        The ``dict`` there is a runtime factory value, not a type declaration,
        so NS-CONTRACT must not flag it.
        """
        module_source = (
            "from __future__ import annotations\n\n"
            "import typing\n\n"
            "from flext_test import m, t\n\n"
            "class FlextTestSettings:\n"
            "    default_headers: typing.Annotated["
            "t.MappingKV[str, str], m.Field(default_factory=dict)] = None\n"
        )
        root = u.Tests.namespace_project(
            tmp_path, module_source=module_source, module_name="_settings.py"
        )

        result = u.Tests.namespace_validator().validate_project(root)

        tm.ok(result)
        tm.that(
            [v for v in result.value.violations if "NS-CONTRACT" in v],
            eq=[],
            msg=str(result.value),
        )

    def test_rule4_banned_annotation_still_flagged(self, tmp_path: Path) -> None:
        """D1-precision non-regression: genuine banned annotations are flagged."""
        module_source = (
            "from __future__ import annotations\n\n"
            "class FlextTestServices:\n"
            "    def transform(self, data: dict) -> object:\n"
            "        return data\n"
        )
        root = u.Tests.namespace_project(
            tmp_path, module_source=module_source, module_name="services.py"
        )

        result = u.Tests.namespace_validator().validate_project(root)

        tm.ok(result)
        u.Tests.assert_namespace_violation_contains(root, "banned annotation")

    def test_rule4_canonical_singleton_with_trailing_docstring_allowed(
        self, tmp_path: Path
    ) -> None:
        """D1-precision: canonical `api: Class = Class.fetch_global()` allows a trailing docstring.

        Mirrors the generated api.py.j2:20 singleton plus a hand-placed docstring
        (the flext-api api.py / _settings.py shape). A trailing module-alias
        declaration is still forbidden; only a docstring or ``__all__`` may follow.
        """
        module_source = (
            "from __future__ import annotations\n\n"
            "class FlextTest:\n"
            "    pass\n\n"
            "api: FlextTest = FlextTest.fetch_global()\n"
            '"""Global FlextTest facade instance."""\n'
            '__all__: list[str] = ["FlextTest", "api"]\n'
        )
        root = u.Tests.namespace_project(
            tmp_path, module_source=module_source, module_name="api.py"
        )

        result = u.Tests.namespace_validator().validate_project(root)

        tm.ok(result)
        u.Tests.assert_namespace_no_violation_contains(
            root, "module alias/data declaration"
        )

    def test_rule4_bare_module_annotation_is_not_import_time_wiring(
        self, tmp_path: Path
    ) -> None:
        """A module-level annotation without a value constructs nothing.

        Mirrors the documented re-export idiom in flext-meltano
        ``services/singer_sdk.py`` (``Tap: type[Tap]`` followed by a
        docstring): the composition-root contract reads the assigned value, so
        an ``AnnAssign`` with no value is neither a crash nor a wiring finding.
        """
        module_source = (
            "from __future__ import annotations\n\n"
            "class FlextTestServices:\n"
            "    pass\n\n"
            "Declared: type[FlextTestServices]\n"
            '"""Documented re-export slot."""\n'
        )
        root = u.Tests.namespace_project(
            tmp_path, module_source=module_source, module_name="services.py"
        )

        result = u.Tests.namespace_validator().validate_project(root)

        tm.ok(result)
        u.Tests.assert_namespace_no_violation_contains(root, "import-time wiring")

    def test_rule4_module_level_construction_still_flagged(
        self, tmp_path: Path
    ) -> None:
        """Non-regression: an assigned module-level call stays import-time wiring."""
        module_source = (
            "from __future__ import annotations\n\n"
            "class FlextTestServices:\n"
            "    pass\n\n"
            "wired: FlextTestServices = FlextTestServices()\n"
        )
        root = u.Tests.namespace_project(
            tmp_path, module_source=module_source, module_name="services.py"
        )

        result = u.Tests.namespace_validator().validate_project(root)

        tm.ok(result)
        u.Tests.assert_namespace_violation_contains(root, "import-time wiring")
