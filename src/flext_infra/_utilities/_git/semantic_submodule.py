"""Canonical Git responsibility mixin for ``u.Infra``.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from collections.abc import MutableMapping
from configparser import Error as ConfigParserError
from pathlib import Path
from typing import TYPE_CHECKING

from git import GitCommandError, GitConfigParser

from flext_infra import c, m, r, t
from flext_infra._utilities._git.semantic_identity import (
    FlextInfraUtilitiesGitSemanticIdentityMixin,
)

if TYPE_CHECKING:
    from flext_infra import p


class FlextInfraUtilitiesGitSemanticSubmoduleMixin(
    FlextInfraUtilitiesGitSemanticIdentityMixin,
):
    """Own semantic submodule operations."""

    @classmethod
    def git_submodule_init(
        cls,
        request: m.Infra.GitRefRequest,
    ) -> p.Result[m.Infra.GitBoolReport]:
        """Initialize one declared submodule at its recorded gitlink.

        Returns:
            The resulting ``p.Result[m.Infra.GitBoolReport]``.

        """
        try:
            repo = cls._repo(request.repo_root)
            repo.git.submodule("update", "--init", "--", request.reference)
        except (GitCommandError, OSError, ValueError) as exc:
            return r[m.Infra.GitBoolReport].fail(
                f"could not initialize the governed gitlink {request.reference}: {exc}",
                exception=exc,
            )
        return r[m.Infra.GitBoolReport].ok(m.Infra.GitBoolReport(value=True))

    @classmethod
    def git_submodule_config_value(
        cls,
        request: m.Infra.GitSubmoduleConfigRequest,
    ) -> p.Result[m.Infra.GitTextReport]:
        """Read one ``.gitmodules`` value, returning empty text when unset.

        Returns:
            The resulting ``p.Result[m.Infra.GitTextReport]``.

        """
        gitmodules = request.repo_root / c.Infra.GITMODULES
        try:
            with GitConfigParser(file_or_files=gitmodules, read_only=True) as parser:
                value = (
                    str(parser.get_value(request.section, request.key))
                    if parser.has_option(request.section, request.key)
                    else ""
                )
        except (ConfigParserError, OSError, TypeError, ValueError) as exc:
            return r[m.Infra.GitTextReport].fail(
                f"failed to read {request.section}.{request.key}: {exc}",
                exception=exc,
            )
        return r[m.Infra.GitTextReport].ok(m.Infra.GitTextReport(text=value.strip()))

    @classmethod
    def git_submodule_sections(
        cls,
        request: m.Infra.GitRepoRequest,
    ) -> p.Result[t.StrMapping]:
        """Map every declared submodule path to its ``.gitmodules`` section.

        A duplicated path is a declaration defect rather than a state defect, so
        it fails here instead of silently resolving to the last writer.

        Returns:
            The resulting ``p.Result[t.StrMapping]``.

        """
        gitmodules = request.repo_root / c.Infra.GITMODULES
        if not gitmodules.is_file():
            return r[t.StrMapping].ok({})
        try:
            with GitConfigParser(file_or_files=gitmodules, read_only=True) as parser:
                declarations = tuple(
                    (str(parser.get_value(section, "path")).strip(), section)
                    for section in parser.sections()
                    if section.startswith("submodule ")
                    and parser.has_option(section, "path")
                )
        except (ConfigParserError, OSError, TypeError, ValueError) as exc:
            return r[t.StrMapping].fail(
                f"failed to read submodule declarations: {exc}",
                exception=exc,
            )
        sections: MutableMapping[str, str] = {}
        for declared, section in declarations:
            if not declared:
                continue
            if declared in sections:
                return r[t.StrMapping].fail(
                    f"governed gitlink path is duplicated: {declared}",
                )
            sections[declared] = section
        return r[t.StrMapping].ok(sections)

    @classmethod
    def git_unmanaged_submodule_paths(
        cls,
        request: m.Infra.GitRepoRequest,
    ) -> p.Result[t.SequenceOf[Path]]:
        """Return declared submodule paths that opt out of workspace governance.

        An absent ``flext-managed`` key keeps the member governed. Any explicit
        value other than ``true`` declares a vendored or non-Python checkout
        that no governed stage may treat as a workspace project.

        Returns:
            Declared submodule paths that opt out of workspace governance.

        """
        sections = cls.git_submodule_sections(request)
        if sections.failure:
            return r[t.SequenceOf[Path]].from_failure(sections)
        unmanaged: t.MutableSequenceOf[Path] = []
        for declared, section in sections.value.items():
            flag = cls.git_submodule_config_value(
                m.Infra.GitSubmoduleConfigRequest(
                    repo_root=request.repo_root,
                    section=section,
                    key=c.Infra.GITMODULE_MANAGED_KEY,
                ),
            )
            if flag.failure:
                return r[t.SequenceOf[Path]].from_failure(flag)
            if flag.value.text and flag.value.text.lower() != "true":
                unmanaged.append(Path(declared))
        return r[t.SequenceOf[Path]].ok(tuple(unmanaged))


__all__: list[str] = ["FlextInfraUtilitiesGitSemanticSubmoduleMixin"]
