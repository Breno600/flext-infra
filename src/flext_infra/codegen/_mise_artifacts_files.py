"""Exact filesystem-state primitives for Mise artifact transactions."""

from __future__ import annotations

import stat
from pathlib import Path
from typing import TYPE_CHECKING

from flext_core import r
from flext_infra import c, m, t, u

if TYPE_CHECKING:
    from flext_infra import p


class FlextInfraMiseArtifactsFiles:
    """Exact filesystem-state primitives for Mise artifact transactions."""

    @classmethod
    def transaction_participants(
        cls, layout: m.Infra.MiseToolchainWorkspaceLayout
    ) -> t.VariadicTuple[
        m.Infra.MiseToolchainProjectLayout | m.Infra.CodegenFileParticipant
    ]:
        """Return only explicitly registered publication owners."""
        return (*layout.projects, *layout.file_participants)

    @classmethod
    def transaction_relative(
        cls, layout: m.Infra.MiseToolchainWorkspaceLayout, path: Path
    ) -> p.Result[str]:
        """Encode a file capability path without weakening workspace containment."""
        participants = sorted(
            layout.file_participants, key=lambda item: -len(item.root.parts)
        )
        for participant in participants:
            if path.is_relative_to(participant.root):
                relative = cls.workspace_relative(participant.root, path)
                if relative.failure:
                    return relative
                return r[str].ok(f"{participant.selector}/{relative.value}")
        relative = cls.workspace_relative(layout.scope_root, path)
        if relative.success and relative.value.startswith("@"):
            return r[str].fail(f"reserved file capability path: {path}")
        return relative

    @classmethod
    def resolve_transaction(
        cls,
        layout: m.Infra.MiseToolchainWorkspaceLayout,
        selector: str,
        *,
        purpose: str,
    ) -> p.Result[Path]:
        """Resolve one journal path against its exact registered physical root."""
        if not selector.startswith("@"):
            return cls.resolve_relative(layout.scope_root, selector, purpose=purpose)
        identity, separator, relative = selector.partition("/")
        participant = next(
            (item for item in layout.file_participants if item.selector == identity),
            None,
        )
        if not separator or participant is None:
            return r[Path].fail(f"unknown file publication capability: {selector}")
        physical = cls.physical_directory_identity(participant.root)
        if physical.failure:
            return r[Path].from_failure(physical)
        if physical.value != (participant.device, participant.inode):
            return r[Path].fail(
                f"file publication root identity changed: {participant.root}"
            )
        return cls.resolve_relative(participant.root, relative, purpose=purpose)

    @classmethod
    def digest(cls, content: bytes) -> str:
        """Return the exact lowercase SHA-256 identity for raw bytes."""
        return u.Cli.sha256_bytes(content)

    @classmethod
    def packaged_launchers(cls) -> p.Result[t.VariadicTuple[bytes]]:
        """Load the packaged unlocked bootstrap launcher pair for fresh seeding.

        Package resources are immutable data: the installer may hard-link them
        to its cache (uv does), so they are read as resources, never as
        uniquely owned atomic state. Staging owns the destination's atomic
        publication and executable-output permissions.
        """
        seed_directory = (
            Path(__file__).resolve().parents[1] / c.Infra.MISE_BOOTSTRAP_SEED_DIRECTORY
        )
        contents: list[bytes] = []
        for name in c.Infra.ARTIFACT_NAMES:
            path = seed_directory / Path(name).name
            loaded = u.Cli.files_read_binary(path)
            if loaded.failure:
                return r[t.VariadicTuple[bytes]].from_failure(loaded)
            if not loaded.value:
                return r[t.VariadicTuple[bytes]].fail(
                    f"packaged Mise launcher seed is empty: {path}"
                )
            contents.append(loaded.value)
        return r[t.VariadicTuple[bytes]].ok(tuple(contents))

    @classmethod
    def read_state(
        cls, path: Path, *, required: bool
    ) -> p.Result[m.Cli.AtomicFileState]:
        """Read exact state through the canonical descriptor-authenticated owner."""
        return u.Cli.atomic_read_binary_file_state(path, required=required)

    @classmethod
    def physical_directory_identity(cls, path: Path) -> p.Result[t.Pair[int, int]]:
        """Return the device/inode identity of one physical directory."""
        try:
            observed = path.lstat()
        except OSError as exc:
            return r[tuple[int, int]].fail_op("inspect generation directory", exc)
        reparse = getattr(observed, "st_file_attributes", 0) & getattr(
            stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0
        )
        if not stat.S_ISDIR(observed.st_mode) or reparse:
            return r[tuple[int, int]].fail(
                f"generation directory is not physical: {path}"
            )
        return r[tuple[int, int]].ok((observed.st_dev, observed.st_ino))

    @classmethod
    def write_publication(
        cls, publication: m.Infra.CodegenStagedFile
    ) -> p.Result[bool]:
        """Consume one staged create/replace/mode/delete through the CLI owner.

        Publication is a guarded atomic replace; the zero-residue law
        prohibits leaving backup copies beside managed destinations.
        """
        before = publication.before
        replacement = publication.replacement
        if replacement is None:
            return cls.delete_state(before)
        if replacement.content is None or replacement.mode is None:
            return r[bool].fail(
                f"codegen staged replacement is absent: {replacement.path}"
            )
        published = u.Cli.atomic_publish_staged_binary_file_guarded(before, replacement)
        if published.failure:
            return r[bool].from_failure(published)
        observed = published.value
        observed_identity = (
            observed.path,
            observed.parent_device,
            observed.parent_inode,
            observed.content,
            observed.mode,
            observed.device,
            observed.inode,
            observed.link_count,
            observed.file_attributes,
            observed.reparse_tag,
        )
        replacement_identity = (
            before.path,
            before.parent_device,
            before.parent_inode,
            replacement.content,
            replacement.mode,
            replacement.device,
            replacement.inode,
            replacement.link_count,
            replacement.file_attributes,
            replacement.reparse_tag,
        )
        if observed_identity != replacement_identity:
            return r[bool].fail(
                f"published codegen file differs from staged identity: {before.path}"
            )
        return r[bool].ok(True)

    @classmethod
    def delete_state(cls, state: m.Cli.AtomicFileState) -> p.Result[bool]:
        """Delete one exact existing state through the CLI owner."""
        if (
            state.content is None
            or state.mode is None
            or state.device is None
            or state.inode is None
        ):
            return r[bool].fail(
                f"cannot delete absent codegen file state: {state.path}"
            )
        return u.Cli.atomic_delete_binary_file_guarded(state)

    @classmethod
    def workspace_relative(cls, root: Path, path: Path) -> p.Result[str]:
        """Return a canonical lexical workspace-relative path selector."""
        absolute_root = root.absolute()
        try:
            relative = path.absolute().relative_to(absolute_root)
        except ValueError as exc:
            return r[str].fail_op(f"resolve workspace artifact {path}", exc)
        selector = relative.as_posix()
        if not selector or selector == "." or ".." in relative.parts:
            return r[str].fail(f"invalid workspace artifact path: {path}")
        return r[str].ok(selector)

    @classmethod
    def resolve_relative(
        cls, root: Path, selector: str, *, purpose: str
    ) -> p.Result[Path]:
        """Resolve a lexical relative selector without dereferencing its leaf."""
        relative = Path(selector)
        if (
            relative.is_absolute()
            or relative.as_posix() != selector
            or not relative.parts
            or ".." in relative.parts
        ):
            return r[Path].fail(f"unsafe {purpose} path: {selector}")
        absolute_root = root.absolute()
        candidate = (absolute_root / relative).absolute()
        if not candidate.is_relative_to(absolute_root):
            return r[Path].fail(f"{purpose} path escapes its root: {selector}")
        return r[Path].ok(candidate)


__all__: list[str] = ["FlextInfraMiseArtifactsFiles"]
