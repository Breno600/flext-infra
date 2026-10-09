"""Release registry metadata: pinned requirements and the sdist boundary.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from pathlib import PurePosixPath

from packaging.requirements import InvalidRequirement, Requirement
from packaging.utils import canonicalize_name

from flext_infra import c, p, r, t, u
from flext_infra.release._release_source import FlextInfraReleaseSourceMixin


class FlextInfraReleaseMetadataMixin(FlextInfraReleaseSourceMixin):
    """Render the pyproject a public registry accepts from the committed one.

    ``versions`` maps every internal distribution the build can see to the
    version its own repository declares; internal requirements are pinned to
    those versions, never to this project's version.
    """

    @classmethod
    def _release_requirements(
        cls,
        container: t.Cli.TomlDocument | t.Cli.TomlTable,
        key: str,
        versions: t.StrMapping,
    ) -> p.Result[bool]:
        """Pin every internal requirement of one TOML array; others pass verbatim.

        A dependency this build cannot see is not publishable: a guessed
        range would be a silent contract.

        Returns:
            The resulting ``p.Result[bool]``.

        """
        raw = u.Cli.toml_value(container, key)
        if raw is None:
            return r[bool].ok(value=True)
        items: p.Result[t.StrSequence] = u.validate_value(
            t.Infra.STR_SEQ_ADAPTER,
            u.Cli.json_as_sequence(raw),
            strict=True,
        )
        if items.failure:
            return r[bool].fail_op(
                f"validate release dependency group {key}",
                items.error,
            )
        rendered: t.MutableSequenceOf[str] = []
        for requirement in items.value:
            try:
                parsed = Requirement(requirement)
            except InvalidRequirement as exc:
                return r[bool].fail_op("parse release requirement", exc)
            name = canonicalize_name(parsed.name)
            if not name.startswith(c.Infra.PKG_PREFIX_HYPHEN):
                rendered.append(requirement.strip())
                continue
            if name not in versions:
                return r[bool].fail(
                    f"internal dependency version unknown to this release: {name}",
                )
            pin = cls._release_specifier(versions[name])
            if pin.failure:
                return r[bool].from_failure(pin)
            extras = f"[{','.join(sorted(parsed.extras))}]" if parsed.extras else ""
            marker = f"; {parsed.marker}" if parsed.marker is not None else ""
            rendered.append(f"{parsed.name}{extras}{pin.value}{marker}")
        u.Cli.toml_sync_string_list(container, key, rendered)
        return r[bool].ok(value=True)

    @classmethod
    def _release_pyproject(
        cls,
        source: str,
        version: str,
        versions: t.StrMapping,
    ) -> p.Result[str]:
        """Render a pyproject a public registry accepts: pinned, sourceless, bounded.

        Returns:
            The resulting ``p.Result[str]``.

        """
        document = u.Cli.toml_parse_text(source)
        project = (
            u.Cli.toml_table_child(document, c.Infra.PROJECT)
            if document is not None
            else None
        )
        if document is None or project is None:
            return r[str].fail(
                "release pyproject must be valid TOML defining [project]",
            )
        project[c.Infra.VERSION] = version
        fields = (
            (project, c.Infra.DEPENDENCIES),
            *u.Infra.requirement_group_fields(document, project),
        )
        for container, key in fields:
            pinned = cls._release_requirements(container, key, versions)
            if pinned.failure:
                return r[str].from_failure(pinned)
        tool = u.Cli.toml_table_child(document, c.Infra.TOOL)
        hatch = u.Cli.toml_table_child(tool, "hatch") if tool is not None else None
        if tool is None or hatch is None:
            return r[str].fail("release pyproject must define [tool.hatch]")
        u.Cli.toml_remove_key_if_present(tool, "uv")
        bounded = cls._sdist_boundary(hatch)
        if bounded.failure:
            return r[str].from_failure(bounded)
        metadata = u.Cli.toml_table_child(hatch, "metadata")
        if metadata is not None:
            # Direct references survive only when a rendered requirement still
            # carries one: the flag is deduced, never configured.
            if any(
                Requirement(str(item)).url is not None
                for container, key in fields
                for item in container.get(key) or ()
            ):
                metadata["allow-direct-references"] = True
            else:
                u.Cli.toml_remove_key_if_present(metadata, "allow-direct-references")
            if not metadata:
                u.Cli.toml_remove_key_if_present(hatch, "metadata")
        rendered = u.Cli.toml_dumps(document)
        if u.Cli.toml_parse_text(rendered) is None:
            return r[str].fail("release pyproject rendering produced invalid TOML")
        return r[str].ok(rendered)

    @classmethod
    def _sdist_boundary(cls, hatch: t.Cli.TomlTable) -> p.Result[t.StrSequence]:
        """Verify matching, bounded source selection for both archive targets.

        Returns:
            The resulting ``p.Result[t.StrSequence]``.

        """
        tables = cls._archive_targets(hatch)
        if tables.failure:
            return r[t.StrSequence].from_failure(tables)
        _build, wheel, sdist = tables.value
        includes = cls._matching_includes(wheel, sdist)
        if includes.failure:
            return r[t.StrSequence].from_failure(includes)
        sources = cls._forced_sources(wheel, sdist)
        if sources.failure:
            return r[t.StrSequence].from_failure(sources)
        policy = cls._target_policy_verdicts(
            wheel,
            sdist,
            includes.value,
            sources.value,
        )
        if policy.failure:
            return r[t.StrSequence].from_failure(policy)
        bounded = cls._bounded_sources(includes.value, sources.value)
        if bounded.failure:
            return r[t.StrSequence].from_failure(bounded)
        return r[t.StrSequence].ok(bounded.value)

    @staticmethod
    def _archive_targets(
        hatch: t.Cli.TomlTable,
    ) -> p.Result[t.Triple[t.Cli.TomlTable | None, t.Cli.TomlTable, t.Cli.TomlTable]]:
        """Navigate to the declared Hatch build targets.

        Returns:
            The resulting ``(build, wheel, sdist)`` archive target tables.

        """
        result_type = r[
            t.Triple[t.Cli.TomlTable | None, t.Cli.TomlTable, t.Cli.TomlTable]
        ]
        build = u.Cli.toml_table_child(hatch, "build")
        targets = (
            u.Cli.toml_table_child(build, "targets") if build is not None else None
        )
        wheel = (
            u.Cli.toml_table_child(targets, "wheel") if targets is not None else None
        )
        sdist = (
            u.Cli.toml_table_child(targets, "sdist") if targets is not None else None
        )
        if targets is None or wheel is None or sdist is None:
            return result_type.fail(
                "release pyproject must define Hatch wheel and sdist targets",
            )
        if build is not None and any(
            key in build for key in ("only-include", "packages", "exclude")
        ):
            return result_type.fail(
                "Hatch build must use target source patterns without exclusions",
            )
        return result_type.ok((build, wheel, sdist))

    @staticmethod
    def _matching_includes(
        wheel: t.Cli.TomlTable,
        sdist: t.Cli.TomlTable,
    ) -> p.Result[t.StrSequence]:
        """Validate and match the wheel and sdist source patterns.

        Returns:
            The resulting wheel source patterns.

        """
        wheel_includes: p.Result[t.StrSequence] = u.validate_value(
            t.Infra.STR_SEQ_ADAPTER,
            u.Cli.json_as_sequence(u.Cli.toml_value(wheel, "include")),
            strict=True,
        )
        if wheel_includes.failure:
            return r[t.StrSequence].fail_op(
                "validate Hatch wheel include",
                wheel_includes.error,
            )
        sdist_includes: p.Result[t.StrSequence] = u.validate_value(
            t.Infra.STR_SEQ_ADAPTER,
            u.Cli.json_as_sequence(u.Cli.toml_value(sdist, "include")),
            strict=True,
        )
        if sdist_includes.failure:
            return r[t.StrSequence].fail_op(
                "validate Hatch sdist include",
                sdist_includes.error,
            )
        if not wheel_includes.value or set(wheel_includes.value) != set(
            sdist_includes.value,
        ):
            return r[t.StrSequence].fail(
                "Hatch wheel and sdist source patterns must match",
            )
        return r[t.StrSequence].ok(wheel_includes.value)

    @staticmethod
    def _forced_sources(
        wheel: t.Cli.TomlTable,
        sdist: t.Cli.TomlTable,
    ) -> p.Result[t.StrSequence]:
        """Prove the sdist retains every forced wheel source.

        Returns:
            The resulting forced wheel source keys.

        """
        wheel_forced = u.Cli.toml_table_child(wheel, "force-include")
        sdist_forced = u.Cli.toml_table_child(sdist, "force-include")
        sources = (
            tuple(str(source) for source in wheel_forced)
            if wheel_forced is not None
            else ()
        )
        if (sdist_forced is None and sources) or (
            sdist_forced is not None
            and {str(source): str(target) for source, target in sdist_forced.items()}
            != {source: source for source in sources}
        ):
            return r[t.StrSequence].fail(
                "Hatch sdist must retain every forced wheel source",
            )
        return r[t.StrSequence].ok(sources)

    @classmethod
    def _target_policy_verdicts(
        cls,
        wheel: t.Cli.TomlTable,
        sdist: t.Cli.TomlTable,
        wheel_includes: t.StrSequence,
        sources: t.StrSequence,
    ) -> p.Result[bool]:
        """Enforce the bounded source patterns and exclusion policy of both targets.

        Returns:
            The resulting ``p.Result[bool]``.

        """
        for target in (wheel, sdist):
            if any(key in target for key in ("only-include", "packages")):
                return r[bool].fail(
                    "Hatch targets must use bounded source patterns",
                )
        for pattern in wheel_includes:
            if not pattern.startswith("/") or not pattern.endswith("/**"):
                return r[bool].fail(
                    f"Hatch source pattern is not a directory: {pattern}",
                )
        for source in sources:
            if PurePosixPath(source).is_absolute():
                return r[bool].fail(
                    f"Hatch source path is outside the release boundary: {source}",
                )
        wheel_excludes = u.Cli.json_as_sequence(u.Cli.toml_value(wheel, "exclude"))
        sdist_excludes = u.Cli.json_as_sequence(u.Cli.toml_value(sdist, "exclude"))
        if wheel_excludes != sdist_excludes:
            return r[bool].fail("Hatch wheel and sdist exclusions must match")
        for excluded in wheel_excludes:
            error = cls._excluded_error(excluded, wheel_includes)
            if error:
                return r[bool].fail(error)
        return r[bool].ok(value=True)

    @classmethod
    def _excluded_error(
        cls,
        excluded: t.JsonValue,
        wheel_includes: t.StrSequence,
    ) -> str:
        """Return why one exclusion leaves the declared data, or an empty string.

        Returns:
            Why one exclusion leaves the declared data, or an empty string.

        """
        if not isinstance(excluded, str) or not excluded.startswith("/"):
            return f"invalid Hatch exclusion: {excluded}"
        path = PurePosixPath(excluded.removeprefix("/"))
        if (
            ".." in path.parts
            or path.as_posix() != excluded.removeprefix("/")
            or len(path.parts) <= 1
            or path.parts[0] == c.Infra.DEFAULT_SRC_DIR
            or not any(
                excluded.startswith(pattern.removesuffix("**"))
                for pattern in wheel_includes
            )
        ):
            return f"Hatch exclusion is outside declared data: {excluded}"
        return ""

    @classmethod
    def _bounded_sources(
        cls,
        wheel_includes: t.StrSequence,
        sources: t.StrSequence,
    ) -> p.Result[t.StrSequence]:
        """Prove every declared source stays inside the release boundary.

        Returns:
            The resulting sorted release source roots.

        """
        roots = tuple(
            sorted({
                PurePosixPath(
                    pattern.removeprefix("/").removesuffix("/**"),
                ).parts[0]
                for pattern in wheel_includes
                if pattern.startswith("/") and pattern.endswith("/**")
            }),
        )
        for source in (*wheel_includes, *sources):
            error = cls._bounded_source_error(source, wheel_includes, roots)
            if error:
                return r[t.StrSequence].fail(error)
        return r[t.StrSequence].ok(roots)

    @classmethod
    def _bounded_source_error(
        cls,
        source: str,
        wheel_includes: t.StrSequence,
        roots: t.StrSequence,
    ) -> str:
        """Return why one source leaves the release boundary, or an empty string.

        Returns:
            Why one source leaves the release boundary, or an empty string.

        """
        relative = (
            source.removeprefix("/").removesuffix("/**")
            if source in wheel_includes
            else source
        )
        path = PurePosixPath(relative)
        safe_path = (
            bool(relative)
            and not path.is_absolute()
            and ".." not in path.parts
            and path.as_posix() == relative
        )
        if not safe_path or (
            cls._path_error(relative, "release source", root_index=0)
            or not cls._sdist_member_allowed(("release-root", *path.parts), roots)
        ):
            return f"Hatch source path is outside the release boundary: {source}"
        return ""


__all__: list[str] = ["FlextInfraReleaseMetadataMixin"]
