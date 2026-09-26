"""Release registry metadata: pinned requirements and the sdist boundary."""

from __future__ import annotations

from pathlib import PurePosixPath

from packaging.requirements import InvalidRequirement, Requirement
from packaging.utils import canonicalize_name

from flext_core import r
from flext_infra import c, p, t, u

from ._release_source import FlextInfraReleaseSourceMixin


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
        """
        raw = u.Cli.toml_value(container, key)
        if raw is None:
            return r[bool].ok(True)
        items: p.Result[t.StrSequence] = u.validate_value(
            t.Infra.STR_SEQ_ADAPTER, u.Cli.json_as_sequence(raw), strict=True
        )
        if items.failure:
            return r[bool].fail_op(
                f"validate release dependency group {key}", items.error
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
                    f"internal dependency version unknown to this release: {name}"
                )
            pin = cls._release_specifier(versions[name])
            if pin.failure:
                return r[bool].from_failure(pin)
            extras = f"[{','.join(sorted(parsed.extras))}]" if parsed.extras else ""
            marker = f"; {parsed.marker}" if parsed.marker is not None else ""
            rendered.append(f"{parsed.name}{extras}{pin.value}{marker}")
        u.Cli.toml_sync_string_list(container, key, rendered)
        return r[bool].ok(True)

    @classmethod
    def _release_pyproject(
        cls, source: str, version: str, versions: t.StrMapping
    ) -> p.Result[str]:
        """Render a pyproject a public registry accepts: pinned, sourceless, bounded."""
        document = u.Cli.toml_parse_text(source)
        project = (
            u.Cli.toml_table_child(document, c.Infra.PROJECT)
            if document is not None
            else None
        )
        if document is None or project is None:
            return r[str].fail(
                "release pyproject must be valid TOML defining [project]"
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
    def _sdist_boundary(cls, hatch: t.Cli.TomlTable) -> p.Result[bool]:
        """Derive the sdist's ``only-include`` boundary from the wheel declaration."""
        build = u.Cli.toml_table_child(hatch, "build")
        targets = (
            u.Cli.toml_table_child(build, "targets") if build is not None else None
        )
        wheel = (
            u.Cli.toml_table_child(targets, "wheel") if targets is not None else None
        )
        if targets is None or wheel is None:
            return r[bool].fail("release pyproject must define a Hatch wheel target")
        packages: p.Result[t.StrSequence] = u.validate_value(
            t.Infra.STR_SEQ_ADAPTER,
            u.Cli.json_as_sequence(u.Cli.toml_value(wheel, "packages")),
            strict=True,
        )
        if packages.failure:
            return r[bool].fail_op("validate Hatch wheel packages", packages.error)
        if not packages.value:
            return r[bool].fail("Hatch wheel target must declare packages")
        forced = u.Cli.toml_table_child(wheel, "force-include")
        sources = tuple(
            dict.fromkeys((*packages.value, *(str(k) for k in forced or ())))
        )
        for source in sources:
            path = PurePosixPath(source)
            if (
                path.is_absolute()
                or ".." in path.parts
                or not cls._sdist_member_allowed(("release-root", *path.parts))
            ):
                return r[bool].fail(
                    f"Hatch source path is outside the release boundary: {source}"
                )
        sdist = u.Cli.toml_ensure_table(targets, "sdist")
        for key in ("exclude", "include", "packages"):
            u.Cli.toml_remove_key_if_present(sdist, key)
        u.Cli.toml_sync_string_list(sdist, "only-include", sources)
        return r[bool].ok(True)


__all__: list[str] = ["FlextInfraReleaseMetadataMixin"]
