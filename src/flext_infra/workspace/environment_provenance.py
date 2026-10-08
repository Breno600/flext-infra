"""Fail-closed validation of local editables and locked CI build provenance.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

import re
from json import dumps
from pathlib import Path
from sys import prefix
from typing import TYPE_CHECKING
from urllib.parse import unquote, urlparse
from urllib.request import url2pathname

from flext_infra import c, config, m, r, u
from flext_infra.workspace.detector import FlextInfraWorkspaceDetector

if TYPE_CHECKING:
    from importlib.metadata import Distribution

    from flext_infra import p, t


class FlextInfraWorkspaceEnvironmentProvenance:
    """Bind installed packages to live local or immutable CI workspace sources."""

    @classmethod
    def execute_request(
        cls,
        request: p.Infra.WorkspaceEnvironmentRequest,
    ) -> p.Result[int]:
        """Validate one CLI request without mutating the environment.

        Returns:
            The resulting ``p.Result[int]``.

        """
        return cls.validate(request.repository_root)

    @classmethod
    def validate(
        cls,
        repository_root: Path,
        *,
        metadata_paths: t.StrSequence | None = None,
    ) -> p.Result[int]:
        """Validate PEP 610 and editable path metadata for active members.

        Returns:
            The resulting ``p.Result[int]``.

        """
        resolved_root = repository_root.resolve()
        ci = config.Infra.codegen.make.ci
        if u.Infra.env_value(ci.variable).strip() == ci.value:
            return cls.validate_locked(resolved_root, metadata_paths=metadata_paths)
        workspace_result = FlextInfraWorkspaceDetector.load_workspace_spec(
            resolved_root,
        )
        if workspace_result.failure:
            return r[int].from_failure(workspace_result)
        repositories = tuple(
            repository
            for repository in workspace_result.value.subprojects
            if repository.package and repository.editable
        )
        validated = 0
        for repository in repositories:
            provenance = cls._validate_editable_provenance(
                repository,
                resolved_root,
                metadata_paths=metadata_paths,
            )
            if provenance.failure:
                return r[int].from_failure(provenance)
            validated += int(provenance.value)
        return r[int].ok(validated)

    @classmethod
    def _validate_editable_provenance(
        cls,
        repository: m.Infra.RepositoryRef,
        resolved_root: Path,
        *,
        metadata_paths: t.StrSequence | None,
    ) -> p.Result[bool]:
        """Prove one editable member's PEP 610 and path metadata provenance.

        Returns:
            The resulting ``p.Result[bool]``.

        """
        matches = u.installed_distributions(
            name=repository.distribution,
            path=metadata_paths,
        )
        if len(matches) != 1:
            return r[bool].fail(
                "editable provenance distribution count mismatch: "
                f"distribution={repository.distribution} expected=1 "
                f"actual={len(matches)}",
            )
        distribution = matches[0]
        expected_root = (resolved_root / repository.path).resolve()
        direct_url_result = cls._validate_direct_url(
            repository.distribution,
            distribution.read_text(c.Infra.DISTRIBUTION_DIRECT_URL_FILE),
            expected_root,
        )
        if direct_url_result.failure:
            return r[bool].from_failure(direct_url_result)
        files = distribution.files
        if files is None:
            return r[bool].fail(
                "editable provenance has no installed file inventory: "
                f"distribution={repository.distribution}",
            )
        pth_files = tuple(
            Path(str(distribution.locate_file(file)))
            for file in files
            if str(file).endswith(".pth")
        )
        if len(pth_files) != 1:
            return r[bool].fail(
                "editable provenance pth count mismatch: "
                f"distribution={repository.distribution} expected=1 "
                f"actual={len(pth_files)}",
            )
        pth_result = cls._validate_pth(
            repository.distribution,
            pth_files[0],
            expected_root,
        )
        if pth_result.failure:
            return r[bool].from_failure(pth_result)
        return r[bool].ok(value=True)

    @classmethod
    def validate_locked(
        cls,
        repository_root: Path,
        *,
        metadata_paths: t.StrSequence | None = None,
    ) -> p.Result[int]:
        """Prove locked artifacts and declared local members match their origins.

        Returns:
            The resulting ``p.Result[int]``.
        """
        repository_root = repository_root.resolve()
        document = u.Cli.toml_read_json(repository_root / "uv.lock")
        if document.failure:
            return r[int].from_failure(document)
        # TOML arrays are wire arrays; JSON mode preserves the strict tuple contract.
        locked = m.Infra.LockedEnvironment.model_validate_json(dumps(document.value))
        manifests = u.Infra.load_workspace_manifest(repository_root)
        if manifests.failure:
            return r[int].from_failure(manifests)
        if len(manifests.value) != 1:
            return r[int].fail(
                "locked provenance needs one declared workspace manifest",
            )
        manifest = manifests.value[0]
        workspace = m.Infra.WorkspaceSpec(
            name=manifest.name,
            repository=manifest.repository,
            subprojects=(
                manifest.members
                if manifest.repository.role is c.Infra.MakeProfile.WORKSPACE
                else ()
            ),
        )
        members = {
            repository.distribution: repository
            for repository in workspace.subprojects
            if repository.package
        }
        if workspace.repository.package:
            members[workspace.repository.distribution] = (
                workspace.repository.model_copy(
                    update={"path": Path()},
                )
            )
        # Local sources outside the declared member set must fail, not disappear.
        required = set(members)
        required.update(
            item.name
            for item in locked.package
            if item.source.git is not None
            or item.source.editable is not None
            or item.source.directory is not None
        )
        validated = 0
        for name in sorted(required):
            provenance = cls._validate_locked_provenance(
                name,
                locked,
                repository_root,
                repository=members.get(name),
                metadata_paths=metadata_paths,
            )
            if provenance.failure:
                return r[int].from_failure(provenance)
            validated += int(provenance.value)
        return r[int].ok(validated)

    @classmethod
    def _validate_locked_provenance(
        cls,
        name: str,
        locked: m.Infra.LockedEnvironment,
        repository_root: Path,
        *,
        repository: m.Infra.RepositoryRef | None,
        metadata_paths: t.StrSequence | None,
    ) -> p.Result[bool]:
        """Prove one locked dependency's installed origin and path containment.

        Returns:
            The resulting ``p.Result[bool]``.

        """
        distributions = u.installed_distributions(name=name, path=metadata_paths)
        if len(distributions) != 1:
            return r[bool].fail(
                f"locked provenance needs one installed distribution: {name}",
            )
        distribution = distributions[0]
        location = Path(str(distribution.locate_file(""))).resolve()
        if not location.is_relative_to(Path(prefix).resolve()):
            return r[bool].fail(
                f"locked dependency is outside the owned environment: {name}",
            )
        matches = tuple(
            item
            for item in locked.package
            if item.name == name and item.version == distribution.version
        )
        if len(matches) != 1:
            return r[bool].fail(
                f"installed version differs from committed lock: {name}",
            )
        item = matches[0]
        if repository is not None and (
            item.source.editable is not None or item.source.directory is not None
        ):
            return cls._validate_workspace_build(
                item,
                repository,
                repository_root,
                distribution,
            )
        origin = cls._locked_origin_verdict(
            name,
            matches[0],
            distribution.read_text(c.Infra.DISTRIBUTION_DIRECT_URL_FILE),
        )
        if origin.failure:
            return r[bool].from_failure(origin)
        return cls._locked_pth_verdict(name, distribution)

    @classmethod
    def _validate_workspace_build(
        cls,
        item: m.Infra.LockedPackage,
        repository: m.Infra.RepositoryRef,
        repository_root: Path,
        distribution: Distribution,
    ) -> p.Result[bool]:
        """Authenticate a workspace checkout before accepting its installed build.

        Returns:
            The resulting ``p.Result[bool]``.

        """
        checkout = cls._workspace_checkout_verdict(item, repository, repository_root)
        if checkout.failure:
            return r[bool].from_failure(checkout)
        origin = cls._workspace_origin_verdict(
            item.name,
            distribution.read_text(c.Infra.DISTRIBUTION_DIRECT_URL_FILE),
            (repository_root / repository.path).resolve(),
        )
        if origin.failure:
            return r[bool].from_failure(origin)
        return cls._locked_pth_verdict(item.name, distribution)

    @classmethod
    def _workspace_checkout_verdict(
        cls,
        item: m.Infra.LockedPackage,
        repository: m.Infra.RepositoryRef,
        repository_root: Path,
    ) -> p.Result[bool]:
        """Bind the declared local lock source to a clean, committed checkout.

        Returns:
            The resulting ``p.Result[bool]``.

        """
        expected_root = (repository_root / repository.path).resolve()
        local_source = (
            item.source.editable
            if item.source.editable is not None
            else item.source.directory
        )
        source_kinds = sum(
            source is not None
            for source in (
                item.source.editable,
                item.source.directory,
                item.source.git,
                item.source.registry,
            )
        )
        if (
            source_kinds != 1
            or local_source is None
            or repository.editable != (item.source.editable is not None)
            or not expected_root.is_relative_to(repository_root)
        ):
            return r[bool].fail(
                f"locked workspace source differs from declaration: {item.name}",
            )
        if (
            Path(local_source) != repository.path
            or (repository_root / local_source).resolve() != expected_root
        ):
            return r[bool].fail(
                f"locked workspace source differs from declaration: {item.name}",
            )
        identity = u.Infra.git_identity(
            m.Infra.GitRepoRequest(repo_root=expected_root),
        )
        if identity.failure:
            return r[bool].from_failure(identity)
        if (
            identity.value.repo_root.resolve() != expected_root
            or identity.value.dirty
            or identity.value.origin_remote is None
            or u.Infra.git_remote_identity(identity.value.origin_remote)
            != u.Infra.git_remote_identity(repository.url)
        ):
            return r[bool].fail(
                f"workspace checkout identity differs from declaration: {item.name}",
            )
        if expected_root == repository_root:
            return r[bool].ok(value=True)
        return cls._workspace_gitlink_verdict(
            repository,
            repository_root,
            identity.value.head_oid,
        )

    @staticmethod
    def _workspace_gitlink_verdict(
        repository: m.Infra.RepositoryRef,
        repository_root: Path,
        head_oid: str,
    ) -> p.Result[bool]:
        """Require the member HEAD, index and committed gitlink to be identical.

        Returns:
            The resulting ``p.Result[bool]``.

        """
        if repository.checkout != c.Infra.CheckoutKind.SUBMODULE:
            return r[bool].fail(
                "workspace member has no declared gitlink checkout: "
                f"{repository.distribution}",
            )
        gitlink = u.Infra.git_staged_gitlink_oid(
            m.Infra.GitRefRequest(
                repo_root=repository_root,
                reference=repository.path.as_posix(),
            ),
        )
        if gitlink.failure:
            return r[bool].from_failure(gitlink)
        committed = u.Infra.git_rev_parse(
            m.Infra.GitCommitishRequest(
                repo_root=repository_root,
                commitish=f"{c.Infra.GIT_HEAD}:{repository.path.as_posix()}",
            ),
        )
        if committed.failure:
            return r[bool].from_failure(committed)
        if head_oid != gitlink.value.oid or gitlink.value.oid != committed.value.oid:
            return r[bool].fail(
                "workspace checkout differs from locked gitlink: "
                f"{repository.distribution}",
            )
        return r[bool].ok(value=True)

    @staticmethod
    def _workspace_origin_verdict(
        name: str,
        raw: str | None,
        expected_root: Path,
    ) -> p.Result[bool]:
        """Prove the noneditable build's native local-directory receipt.

        Returns:
            The resulting ``p.Result[bool]``.

        """
        if raw is None:
            return r[bool].fail(
                f"locked workspace build lacks PEP 610 provenance: {name}",
            )
        receipt = m.Infra.DirectUrlReceipt.model_validate_json(raw)
        if receipt.dir_info is not None and receipt.dir_info.editable:
            return r[bool].fail(f"CI dependency is editable: {name}")
        parsed = urlparse(receipt.url)
        local_url = (
            parsed.scheme == "file"
            and parsed.netloc in {"", "localhost"}
            and not parsed.query
            and not parsed.fragment
        )
        actual_root = Path(url2pathname(unquote(parsed.path)))
        if (
            receipt.dir_info is None
            or receipt.vcs_info is not None
            or not local_url
            or not actual_root.is_absolute()
            or actual_root.resolve() != expected_root
        ):
            return r[bool].fail(
                f"locked workspace build direct_url mismatch: {name} "
                f"expected={expected_root} actual={receipt.url}",
            )
        return r[bool].ok(value=True)

    @classmethod
    def _locked_origin_verdict(
        cls,
        name: str,
        item: m.Infra.LockedPackage,
        raw: str | None,
    ) -> p.Result[bool]:
        """Prove one locked dependency's PEP 610 origin against the lock entry.

        Declared local members are authenticated by ``_validate_workspace_build``
        before this artifact-only boundary. Undeclared local lock sources cannot
        bypass checkout, gitlink, and noneditable receipt authentication.

        Returns:
            The resulting ``p.Result[bool]``.

        """
        if raw is None and item.source.git is not None:
            return r[bool].fail(
                f"locked dependency lacks PEP 610 provenance: {name}",
            )
        receipt = (
            m.Infra.DirectUrlReceipt.model_validate_json(raw)
            if raw is not None
            else None
        )
        if (
            receipt is not None
            and receipt.dir_info is not None
            and receipt.dir_info.editable
        ):
            return r[bool].fail(f"CI dependency is editable: {name}")
        if item.source.git is None and item.source.registry is None:
            return r[bool].fail(f"CI member needs a locked artifact source: {name}")
        if item.source.git is not None:
            expected = urlparse(item.source.git.removeprefix("git+"))
            if (
                receipt is None
                or receipt.vcs_info is None
                or receipt.vcs_info.vcs != "git"
                or receipt.vcs_info.commit_id != expected.fragment
                or u.Infra.git_remote_identity(receipt.url)
                != u.Infra.git_remote_identity(expected.geturl())
            ):
                return r[bool].fail(
                    f"installed dependency origin differs from committed lock: {name}",
                )
        return r[bool].ok(value=True)

    @staticmethod
    def _locked_pth_verdict(
        name: str,
        distribution: Distribution,
    ) -> p.Result[bool]:
        """Prove one installed artifact's path inventory stays environment-owned.

        Returns:
            The resulting ``p.Result[bool]``.

        """
        files = distribution.files
        if files is None:
            return r[bool].fail(f"installed artifact has no file inventory: {name}")
        for file in files:
            if str(file).endswith(".pth"):
                path = Path(str(distribution.locate_file(file)))
                for line in path.read_text(encoding="utf-8").splitlines():
                    if Path(line).is_absolute() and not Path(
                        line,
                    ).resolve().is_relative_to(
                        Path(prefix).resolve(),
                    ):
                        return r[bool].fail(
                            f"CI artifact exposes an external source path: {name}",
                        )
        return r[bool].ok(value=True)

    @classmethod
    def _validate_direct_url(
        cls,
        distribution: str,
        raw_payload: str | None,
        expected_root: Path,
    ) -> p.Result[int]:
        """Validate one PEP 610 payload against the declared member root.

        Returns:
            The resulting ``p.Result[int]``.

        """
        if raw_payload is None:
            return r[int].fail(
                "editable provenance missing direct_url.json: "
                f"distribution={distribution} expected={expected_root}",
            )
        try:
            payload = m.Infra.EditableDirectUrl.model_validate_json(
                raw_payload,
                strict=True,
            )
        except ValueError as exc:
            return r[int].fail_op(
                f"editable provenance direct_url validation ({distribution})",
                exc,
            )
        parsed = urlparse(payload.url)
        if parsed.scheme != "file" or not payload.dir_info.editable:
            return r[int].fail(
                "editable provenance is not an editable file URL: "
                f"distribution={distribution} url={payload.url}",
            )
        actual_root = Path(url2pathname(unquote(parsed.path))).resolve()
        if actual_root != expected_root:
            return r[int].fail(
                "editable provenance direct_url mismatch: "
                f"distribution={distribution} expected={expected_root} "
                f"actual={actual_root}",
            )
        return r[int].ok(1)

    @classmethod
    def _validate_pth(
        cls,
        distribution: str,
        pth_file: Path,
        expected_root: Path,
    ) -> p.Result[int]:
        """Validate the distribution-owned editable path file.

        Returns:
            The resulting ``p.Result[int]``.

        """
        read_result = u.Cli.files_read_text(pth_file)
        if read_result.failure:
            return r[int].from_failure(read_result)
        entries = tuple(
            line.strip()
            for line in read_result.value.splitlines()
            if line.strip() and not line.lstrip().startswith("#")
        )
        if not entries:
            return r[int].fail(
                "editable provenance pth is empty: "
                f"distribution={distribution} path={pth_file}",
            )
        for entry in entries:
            if re.match(r"^import\s", entry) or not Path(entry).is_absolute():
                return r[int].fail(
                    "editable provenance pth entry is not an absolute source path: "
                    f"distribution={distribution} entry={entry}",
                )
            actual_source = Path(entry).resolve()
            if not actual_source.is_relative_to(expected_root):
                return r[int].fail(
                    "editable provenance pth mismatch: "
                    f"distribution={distribution} expected_root={expected_root} "
                    f"actual={actual_source}",
                )
        return r[int].ok(1)


__all__: list[str] = ["FlextInfraWorkspaceEnvironmentProvenance"]
