"""Gate contract script discovery."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from flext_core import r
from flext_infra import u

if TYPE_CHECKING:
    from flext_infra import p, t


class FlextInfraGateContractScanMixin:
    """Discover tracked workspace scripts."""

    @staticmethod
    def _tracked_scripts(root: Path) -> p.Result[t.SequenceOf[Path]]:
        scripts_root = root / "scripts"
        if not scripts_root.exists() or not scripts_root.is_dir():
            return r[t.SequenceOf[Path]].ok(())
        scripts = u.Infra.git_tracked_scope_paths(scripts_root)
        if scripts is None:
            return r[t.SequenceOf[Path]].fail(
                f"tracked script discovery requires a Git worktree: {root}"
            )
        return r[t.SequenceOf[Path]].ok(
            tuple(
                path.relative_to(root)
                for path in scripts
                if path.name != "__init__.py" and path.suffix in {".py", ".sh"}
            )
        )


__all__: list[str] = ["FlextInfraGateContractScanMixin"]
