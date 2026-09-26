"""Dependency typings analysis + container-value conversion helpers for detection."""

from __future__ import annotations

from collections.abc import Mapping, MutableMapping
from pathlib import Path
from typing import override

from flext_core import r
from flext_infra import c, config, m, p, t, u

from ._detection_runners import FlextInfraDependencyDetectionRunnersMixin


class FlextInfraDependencyDetectionAnalysis(FlextInfraDependencyDetectionRunnersMixin):
    """Typings analysis + conversion helpers composed with the tool-runner mixin."""

    @override
    def _to_toml_config(self, payload: t.MappingKV[str, t.JsonValue]) -> t.JsonMapping:
        """To toml config."""
        normalized: MutableMapping[str, t.JsonValue] = {}
        for key, value in payload.items():
            if value is None:
                normalized[key] = None
                continue
            converted = FlextInfraDependencyDetectionAnalysis.to_infra_value(value)
            if converted is None:
                continue
            normalized[key] = converted
        return normalized

    @staticmethod
    def to_infra_value(value: t.JsonValue | None) -> t.JsonValue | None:
        """Convert container value to namespaced infra value."""
        if value is None:
            return None
        if isinstance(value, t.PRIMITIVES_TYPES):
            primitive: t.JsonValue = value
            return primitive
        scalar_types = t.PRIMITIVES_TYPES
        if isinstance(value, list):
            sequence = t.Cli.JSON_LIST_ADAPTER.validate_python(value)
            converted: t.MutableSequenceOf[t.JsonValue] = []
            for item in sequence:
                if item is None:
                    converted.append(None)
                    continue
                conv = FlextInfraDependencyDetectionAnalysis.to_infra_value(item)
                if conv is None or not isinstance(conv, scalar_types):
                    return None
                converted.append(conv)
            return list(t.Cli.JSON_LIST_ADAPTER.validate_python(converted))
        mapping_value = t.Infra.INFRA_MAPPING_ADAPTER.validate_python(value)
        converted_map: MutableMapping[str, t.JsonValue] = {}
        for key, map_item in mapping_value.items():
            if map_item is None:
                converted_map[key] = None
                continue
            conv = FlextInfraDependencyDetectionAnalysis.to_infra_value(map_item)
            if conv is None or not isinstance(conv, scalar_types):
                return None
            converted_map[key] = conv
        mapping: t.JsonValue = t.json_dict_adapter().validate_python(converted_map)
        return mapping

    def get_current_typings_from_pyproject(
        self, project_path: Path, *, include_dev: bool = True
    ) -> t.StrSequence:
        """Read CUSTOM typing requirements and the canonical development group."""
        pyproject = project_path / c.PYPROJECT_FILENAME
        if not pyproject.is_file():
            return []
        read_result = self._read_plain(pyproject)
        if read_result.failure:
            msg = f"failed to read {pyproject}: {read_result.error}"
            raise RuntimeError(msg)
        data = read_result.value
        project = t.Infra.INFRA_MAPPING_ADAPTER.validate_python(
            data.get(c.Infra.PROJECT, {})
        )
        optional = t.Infra.INFRA_MAPPING_ADAPTER.validate_python(
            project.get(c.Infra.OPTIONAL_DEPENDENCIES, {})
        )
        requirements = list(
            t.Infra.STR_SEQ_ADAPTER.validate_python(optional.get(c.Infra.TYPINGS, []))
        )
        if include_dev:
            groups = t.Infra.INFRA_MAPPING_ADAPTER.validate_python(
                data.get(c.Infra.DEPENDENCY_GROUPS, {})
            )
            requirements.extend(
                t.Infra.STR_SEQ_ADAPTER.validate_python(groups.get(c.Infra.DEV, []))
            )
        names: set[str] = set()
        for spec in requirements:
            name = u.Infra.dep_name(spec)
            if name is None:
                msg = f"Dependency requirement must not be blank in {pyproject}"
                raise ValueError(msg)
            names.add(name)
        return sorted(names)

    def _project_table(
        self, project_path: Path
    ) -> p.Result[t.Pair[Path, t.JsonMapping]]:
        """Read one project's pyproject once, as a plain mapping, with its path."""
        pyproject = project_path / c.PYPROJECT_FILENAME
        read_result = self._read_plain(pyproject)
        if read_result.failure:
            return r[t.Pair[Path, t.JsonMapping]].fail_op(
                f"read {pyproject}", read_result.error
            )
        return r[t.Pair[Path, t.JsonMapping]].ok((pyproject, read_result.value))

    def governed_profile_dependencies(
        self, project_path: Path
    ) -> p.Result[t.StrSequence]:
        """Return the runtime requirement names a declared dependency profile injects.

        The profile is selected from the typed codegen config exactly as the
        pyproject projection selects it; a project no shared profile governs
        injects nothing.
        """
        table = self._project_table(project_path)
        if table.failure:
            return r[t.StrSequence].from_failure(table)
        pyproject, data = table.value
        project = t.Infra.INFRA_MAPPING_ADAPTER.validate_python(
            data.get(c.Infra.PROJECT, {})
        )
        name = project.get(c.Infra.NAME)
        distribution = u.Infra.dep_name(name) if isinstance(name, str) else None
        if distribution is None:
            return r[t.StrSequence].fail(
                f"[project].name must be declared: {pyproject}"
            )
        runtime_names = {
            dependency
            for item in t.Infra.STR_SEQ_ADAPTER.validate_python(
                project.get(c.Infra.DEPENDENCIES, [])
            )
            if (dependency := u.Infra.dep_name(item))
        }
        profiles = config.Infra.codegen.scaffold.project.dependency_profiles
        upstreams = u.Infra.dependency_profile_upstreams(
            profiles, distribution=distribution, runtime_names=runtime_names
        )
        if len(upstreams) > 1:
            return r[t.StrSequence].fail(
                "scaffold.project.dependency_profiles.upstream must match live "
                f"dependencies at most once at {pyproject}: {tuple(upstreams)}"
            )
        rows = (
            u.Infra.dependency_profile_rows(
                profiles, upstream=upstreams[0], distribution=distribution
            )
            if upstreams
            else ()
        )
        return r[t.StrSequence].ok(
            tuple(
                sorted({
                    dependency
                    for row in rows
                    for requirement in row.runtime
                    if (dependency := u.Infra.dep_name(requirement))
                })
            )
        )

    def govern_deptry_issues(
        self, project_path: Path, issues: t.SequenceOf[t.JsonMapping]
    ) -> p.Result[t.SequenceOf[t.JsonMapping]]:
        """Drop unused-dependency findings for profile-injected requirements.

        Conform renders the selected profile's runtime requirements into every
        governed consumer, so declaring them is policy, not a finding.
        """
        governed = self.governed_profile_dependencies(project_path)
        if governed.failure:
            return r[t.SequenceOf[t.JsonMapping]].from_failure(governed)
        names = frozenset(governed.value)
        return r[t.SequenceOf[t.JsonMapping]].ok(
            tuple(
                issue
                for issue in issues
                if not (
                    u.Cli.json_as_mapping(issue.get(c.Infra.ERROR)).get(c.Infra.CODE)
                    == c.Infra.DEPTRY_UNUSED_DEPENDENCY_CODE
                    and u.Infra.dep_name(str(issue.get(c.Infra.MODULE, ""))) in names
                )
            )
        )

    def untyped_imports_followed(self, project_path: Path) -> p.Result[bool]:
        """Return the governed mypy ``follow_untyped_imports`` policy for a project.

        The policy is read from the typed tooling config the pyproject
        projection renders. A project whose own mypy table declares otherwise
        is a policy conflict, never a second source of truth. An absent key
        carries mypy's own default on both sides.
        """
        key = c.Infra.MYPY_FOLLOW_UNTYPED_IMPORTS
        governed = config.Infra.tooling.tools.mypy.boolean_settings.get(
            key, c.Infra.MYPY_FOLLOW_UNTYPED_IMPORTS_DEFAULT
        )
        table = self._project_table(project_path)
        if table.failure:
            return r[bool].from_failure(table)
        pyproject, data = table.value
        tool = t.Infra.INFRA_MAPPING_ADAPTER.validate_python(data.get(c.Infra.TOOL, {}))
        mypy = t.Infra.INFRA_MAPPING_ADAPTER.validate_python(tool.get(c.Infra.MYPY, {}))
        declared = mypy.get(key, c.Infra.MYPY_FOLLOW_UNTYPED_IMPORTS_DEFAULT)
        if declared != governed:
            return r[bool].fail(
                f"mypy {key} policy conflict in {pyproject}: the project declares "
                f"{declared!r}, the governed tooling policy declares {governed!r}; "
                "regenerate the projection with make gen"
            )
        return r[bool].ok(governed)

    def get_required_typings(
        self, project_path: Path, limits_path: Path | None = None
    ) -> p.Result[m.Infra.TypingsReport]:
        """Analyze project and generate typing stubs requirements report.

        Under the governed policy that follows untyped imports, mypy analyzes
        untyped packages directly and reports no missing stub, so stub
        packages are neither required nor removable findings.
        """
        followed = self.untyped_imports_followed(project_path)
        if followed.failure:
            return r[m.Infra.TypingsReport].from_failure(followed)
        limits = self.load_dependency_limits(limits_path)
        exclude_set: t.Infra.StrSet = set()
        typing_libraries = limits.get(c.Infra.TYPING_LIBRARIES)
        if isinstance(typing_libraries, Mapping):
            excluded = typing_libraries.get(c.Infra.EXCLUDE)
            if isinstance(excluded, list):
                exclude_set = {str(e) for e in excluded}
        hinted: t.StrSequence = []
        missing_modules: t.StrSequence = []
        if not followed.value:
            hints_result = self.run_mypy_stub_hints(project_path)
            if hints_result.failure:
                return r[m.Infra.TypingsReport].from_failure(hints_result)
            typed_hints: t.Pair[t.StrSequence, t.StrSequence] = hints_result.value
            hinted, missing_modules = typed_hints
        required_set: t.Infra.StrSet = set(hinted)
        for module_name in missing_modules:
            package = self.module_to_types_package(module_name, limits)
            if package:
                required_set.add(package)
        required_set -= exclude_set
        current = self.get_current_typings_from_pyproject(project_path)
        current_set = set(current)
        python_cfg = limits.get(c.Infra.PYTHON)
        version_val = (
            python_cfg.get(c.Infra.VERSION) if isinstance(python_cfg, Mapping) else None
        )
        python_version = str(version_val) if version_val is not None else None
        report = m.Infra.TypingsReport(
            required_packages=sorted(required_set),
            hinted=hinted,
            missing_modules=missing_modules,
            current=current,
            to_add=sorted(required_set - current_set),
            to_remove=(
                []
                if followed.value
                else sorted(
                    set(
                        self.get_current_typings_from_pyproject(
                            project_path, include_dev=False
                        )
                    )
                    - required_set
                )
            ),
            limits_applied=bool(limits),
            python_version=python_version,
            untyped_imports_followed=followed.value,
        )
        return r[m.Infra.TypingsReport].ok(report)

    def load_dependency_limits(
        self, limits_path: Path | None = None
    ) -> t.MappingKV[str, t.JsonValue]:
        """Load dependency limits configuration from TOML file."""
        path = (
            limits_path
            or Path(__file__).resolve().parent / c.Infra.DEPENDENCY_LIMITS_FILENAME
        )
        result = self._read_plain(path)
        if result.failure:
            msg = f"failed to load dependency limits from {path}: {result.error}"
            raise RuntimeError(msg)
        return result.value

    def module_to_types_package(
        self, module_name: str, limits: t.MappingKV[str, t.JsonValue]
    ) -> str | None:
        """Map a module name to its corresponding types-* package."""
        root = module_name.split(".", 1)[0]
        if root.startswith(c.Infra.INTERNAL_PREFIXES):
            return None
        typing_libraries = limits.get(c.Infra.TYPING_LIBRARIES)
        if isinstance(typing_libraries, Mapping):
            module_to_package = typing_libraries.get(c.Infra.MODULE_TO_PACKAGE)
            if isinstance(module_to_package, Mapping) and root in module_to_package:
                value = module_to_package.get(root)
                return str(value) if value is not None else None
        # 5a7d1d710 removed the hardcoded module->types-* table: the declared
        # typing_libraries.module_to_package config is the only source, so an
        # undeclared module is unknown rather than a guessed types-* name.
        return None


__all__: list[str] = ["FlextInfraDependencyDetectionAnalysis"]
