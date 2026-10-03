"""Physical destination leases for recoverable file publication.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from collections.abc import Generator, MutableMapping
from contextlib import ExitStack, contextmanager
from pathlib import Path

from flext_infra import c, m, t, u
from flext_infra.codegen._mise_artifacts_files import (
    FlextInfraMiseArtifactsFiles as files,
)


class FlextInfraCodegenFileLeases:
    """Hold destination identities for the lifetime of one transaction."""

    @staticmethod
    @contextmanager
    def mutation_lease(root: Path) -> Generator[None]:
        """Serialize one nontransactional writer with its canonical scope owner.

        Raises:
            ValueError: If mutation root changed before lease acquisition; or if
                mutation Git ownership changed before lease acquisition.

        """
        scope = u.Infra.git_mutation_scope(
            m.Infra.GitRepoRequest(repo_root=root),
        ).unwrap()
        physical = files.physical_directory_identity(scope.root).unwrap()
        lease_directory = (
            scope.git_dir
            if scope.git_dir is not None
            else scope.root / c.Infra.TRANSACTION_STATE_DIRNAME
        )
        if lease_directory.is_symlink() or lease_directory.exists():
            files.physical_directory_identity(lease_directory).unwrap()
        journal = lease_directory / c.Infra.JOURNAL_NAME
        u.Cli.atomic_read_binary_file_state(
            journal.with_name(f"{journal.name}.lock"),
            required=False,
        ).unwrap()
        with u.Infra.codegen_transaction_lease(journal):
            files.physical_directory_identity(lease_directory).unwrap()
            if files.physical_directory_identity(scope.root).unwrap() != physical:
                msg = f"mutation root changed before lease acquisition: {scope.root}"
                raise ValueError(msg)
            if (
                u.Infra.git_mutation_scope(
                    m.Infra.GitRepoRequest(repo_root=scope.root),
                ).unwrap()
                != scope
            ):
                msg = (
                    f"mutation Git ownership changed before lease "
                    f"acquisition: {scope.root}"
                )
                raise ValueError(msg)
            yield

    def __init__(self) -> None:
        """Start without borrowed destination capabilities."""
        self._file_leases: MutableMapping[Path, m.Infra.CodegenFileParticipant] = {}

    @contextmanager
    def _lease_file_participants(
        self,
        participants: t.VariadicTuple[m.Infra.CodegenFileParticipant],
        *,
        held_roots: frozenset[Path] = frozenset(),
    ) -> Generator[None]:
        """Serialize destinations not already covered by the outer root lease.

        Raises:
            ValueError: If file publication root changed before lease; or if file
                publication root changed during lease.

        """
        for participant in participants:
            physical = files.physical_directory_identity(participant.root).unwrap()
            if physical != (participant.device, participant.inode):
                msg = f"file publication root changed before lease: {participant.root}"
                raise ValueError(msg)
        acquired: set[Path] = set()
        try:
            with ExitStack() as stack:
                for participant in sorted(
                    participants,
                    key=lambda item: str(item.root),
                ):
                    if participant.root in self._file_leases:
                        continue
                    if participant.root.resolve() in held_roots:
                        acquired.add(participant.root)
                        self._file_leases[participant.root] = participant
                        continue
                    lease_directory = (
                        participant.root / c.Infra.TRANSACTION_STATE_DIRNAME
                    )
                    if lease_directory.is_symlink() or lease_directory.exists():
                        files.physical_directory_identity(lease_directory).unwrap()
                    lease_path = lease_directory / c.Infra.JOURNAL_NAME
                    u.Cli.atomic_read_binary_file_state(
                        lease_path.with_name(f"{lease_path.name}.lock"),
                        required=False,
                    ).unwrap()
                    stack.enter_context(u.Infra.codegen_transaction_lease(lease_path))
                    files.physical_directory_identity(lease_directory).unwrap()
                    acquired.add(participant.root)
                    self._file_leases[participant.root] = participant
                    physical = files.physical_directory_identity(
                        participant.root,
                    ).unwrap()
                    if physical != (participant.device, participant.inode):
                        msg = (
                            f"file publication root changed during lease: "
                            f"{participant.root}"
                        )
                        raise ValueError(msg)
                yield
        finally:
            for root in acquired:
                self._file_leases.pop(root)


__all__: list[str] = ["FlextInfraCodegenFileLeases"]
