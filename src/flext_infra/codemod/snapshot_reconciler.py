"""Reconcile ast-grep snapshots with the active inherited rule hierarchy."""

from __future__ import annotations

import stat
from collections.abc import Mapping, MutableMapping, Sequence
from pathlib import Path

from .. import c, m, t, u


class FlextInfraCodemodSnapshotReconciler:
    """Remove generated snapshots whose canonical rule ID no longer exists."""

    @staticmethod
    def config_root(rule: Path) -> Path:
        """Resolve the nearest ast-grep configuration that owns a rule."""
        for ancestor in rule.resolve().parents:
            if (ancestor / c.Infra.CODEMOD_CONFIG_FILENAME).is_file():
                return ancestor
        msg = f"ast-grep rule has no owning sgconfig.yml: {rule}"
        raise ValueError(msg)

    @staticmethod
    def fixture_directories(config_root: Path) -> m.Infra.ModFixtureDirectories:
        """Resolve only declared fixture directories without crossing symlinks."""
        config_path = config_root / c.Infra.CODEMOD_CONFIG_FILENAME
        if not stat.S_ISREG(config_path.lstat().st_mode):
            msg = f"ast-grep config must be a regular file: {config_path}"
            raise ValueError(msg)
        payload = u.Cli.yaml_safe_load(config_path).unwrap()
        declared: MutableMapping[str, Sequence[t.JsonValue]] = {}
        for key in (c.Infra.CODEMOD_RULE_DIRS_KEY, c.Infra.CODEMOD_UTIL_DIRS_KEY):
            raw_value = payload.get(
                key, () if key == c.Infra.CODEMOD_UTIL_DIRS_KEY else None
            )
            if not isinstance(raw_value, Sequence) or isinstance(raw_value, str):
                msg = f"invalid ast-grep {key} contract: {config_path}"
                raise TypeError(msg)
            declared[key] = raw_value
        raw_test_configs = payload.get(c.Infra.CODEMOD_TEST_CONFIGS_KEY)
        if not isinstance(raw_test_configs, Sequence) or isinstance(
            raw_test_configs, str
        ):
            msg = f"invalid ast-grep testConfigs contract: {config_path}"
            raise TypeError(msg)
        test_dirs: list[t.JsonValue] = []
        for raw_test_config in raw_test_configs:
            if not isinstance(raw_test_config, Mapping):
                msg = f"ast-grep testConfig must be a mapping: {config_path}"
                raise TypeError(msg)
            test_dirs.append(raw_test_config.get(c.Infra.CODEMOD_TEST_DIR_KEY))
        declared[c.Infra.CODEMOD_TEST_DIR_KEY] = test_dirs
        resolved: MutableMapping[str, t.VariadicTuple[Path]] = {}
        for key, declared_paths in declared.items():
            directories: list[Path] = []
            for raw_dir in declared_paths:
                if not isinstance(raw_dir, str) or not raw_dir.strip():
                    msg = f"invalid ast-grep {key} entry: {config_path}"
                    raise ValueError(msg)
                relative = Path(raw_dir)
                if (
                    relative.is_absolute()
                    or ".." in relative.parts
                    or not relative.parts
                ):
                    msg = f"ast-grep {key} escapes or selects its owner: {raw_dir}"
                    raise ValueError(msg)
                directory = config_root
                for part in relative.parts:
                    directory /= part
                    if directory.is_symlink():
                        msg = (
                            f"ast-grep fixture path must not be a symlink: {directory}"
                        )
                        raise ValueError(msg)
                if not directory.is_dir():
                    msg = f"ast-grep {key} directory is missing: {directory}"
                    raise ValueError(msg)
                directories.append(directory)
            resolved[key] = tuple(dict.fromkeys(directories))
        return m.Infra.ModFixtureDirectories(
            rule_dirs=resolved[c.Infra.CODEMOD_RULE_DIRS_KEY],
            util_dirs=resolved[c.Infra.CODEMOD_UTIL_DIRS_KEY],
            test_dirs=resolved[c.Infra.CODEMOD_TEST_DIR_KEY],
        )

    @classmethod
    def reconcile(cls, config_root: Path, active_rule_ids: frozenset[str]) -> int:
        """Delete only stale generated snapshot projections for one owner."""
        directories = cls.fixture_directories(config_root)
        removed = 0
        for test_dir in directories.test_dirs:
            snapshot_dir = test_dir / c.Infra.CODEMOD_SNAPSHOT_DIRNAME
            if not snapshot_dir.is_dir():
                continue
            for snapshot in sorted(
                snapshot_dir.glob(f"*{c.Infra.CODEMOD_SNAPSHOT_SUFFIX}")
            ):
                rule_id = snapshot.name.removesuffix(c.Infra.CODEMOD_SNAPSHOT_SUFFIX)
                if rule_id in active_rule_ids:
                    continue
                snapshot.unlink()
                removed += 1
                u.Cli.info(f"mod: removed stale snapshot {snapshot}")
        return removed


__all__: t.StrSequence = ("FlextInfraCodemodSnapshotReconciler",)
