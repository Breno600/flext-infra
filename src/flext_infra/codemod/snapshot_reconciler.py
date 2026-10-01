"""Resolve ast-grep fixture owners and detect snapshot residue.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

import stat
from collections.abc import Mapping, MutableMapping, Sequence
from pathlib import Path

from flext_infra import c, m, t, u


class FlextInfraCodemodSnapshotReconciler:
    """Resolve fixture owners and report snapshots no rule or test produces."""

    @staticmethod
    def config_root(rule: Path) -> Path:
        """Resolve the nearest ast-grep configuration that owns a rule.

        Returns:
            The resulting ``Path``.

        Raises:
            ValueError: If ast-grep rule has no owning sgconfig.yml.

        """
        for ancestor in rule.resolve().parents:
            if (ancestor / c.Infra.CODEMOD_CONFIG_FILENAME).is_file():
                return ancestor
        msg = f"ast-grep rule has no owning sgconfig.yml: {rule}"
        raise ValueError(msg)

    @staticmethod
    def fixture_directories(config_root: Path) -> m.Infra.ModFixtureDirectories:
        """Resolve only declared fixture directories without crossing symlinks.

        Returns:
            The resulting ``m.Infra.ModFixtureDirectories``.

        Raises:
            TypeError: If invalid ast-grep testConfigs contract; or if invalid ast-grep;
                or if ast-grep testConfig must be a mapping.
            ValueError: If ast-grep config must be a regular file; or if invalid
                ast-grep; or if ast-grep; or if ast-grep fixture path must not be a
                symlink.

        """
        config_path = config_root / c.Infra.CODEMOD_CONFIG_FILENAME
        if not stat.S_ISREG(config_path.lstat().st_mode):
            msg = f"ast-grep config must be a regular file: {config_path}"
            raise ValueError(msg)
        payload = u.Cli.yaml_safe_load(config_path).unwrap()
        declared: MutableMapping[str, Sequence[t.JsonValue]] = {}
        for key in (c.Infra.CODEMOD_RULE_DIRS_KEY, c.Infra.CODEMOD_UTIL_DIRS_KEY):
            raw_value = payload.get(
                key,
                () if key == c.Infra.CODEMOD_UTIL_DIRS_KEY else None,
            )
            if not isinstance(raw_value, Sequence) or isinstance(raw_value, str):
                msg = f"invalid ast-grep {key} contract: {config_path}"
                raise TypeError(msg)
            declared[key] = raw_value
        raw_test_configs = payload.get(c.Infra.CODEMOD_TEST_CONFIGS_KEY)
        if not isinstance(raw_test_configs, Sequence) or isinstance(
            raw_test_configs,
            str,
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
    def stale_snapshots(
        cls,
        config_root: Path,
        active_rule_ids: frozenset[str],
    ) -> t.StrSequence:
        """Describe every committed snapshot projection no current test produces.

        ``ast-grep test`` rejects a drifted or missing snapshot but accepts the
        snapshot file of a removed rule and the entry of a deleted test case.
        Both are residue of an unreviewed change, so they are reported, never
        deleted in place: ``make mod-snapshots`` regenerates the owner's
        projections for a reviewed commit.

        Returns:
            The resulting ``t.StrSequence``.

        """
        stale: list[str] = []
        for test_dir in cls.fixture_directories(config_root).test_dirs:
            snapshot_dir = test_dir / c.Infra.CODEMOD_SNAPSHOT_DIRNAME
            if not snapshot_dir.is_dir():
                continue
            invalid_cases = cls._invalid_cases(test_dir)
            for snapshot in sorted(
                snapshot_dir.glob(f"*{c.Infra.CODEMOD_SNAPSHOT_SUFFIX}"),
            ):
                rule_id = snapshot.name.removesuffix(c.Infra.CODEMOD_SNAPSHOT_SUFFIX)
                if rule_id not in active_rule_ids:
                    stale.append(f"{snapshot}: rule {rule_id} is not declared")
                    continue
                declared = invalid_cases.get(rule_id, frozenset())
                stale.extend(
                    f"{snapshot}: no invalid test case produces {case!r}"
                    for case in cls._snapshot_cases(snapshot)
                    if case not in declared
                )
        return tuple(stale)

    @staticmethod
    def _invalid_cases(test_dir: Path) -> t.MappingKV[str, frozenset[str]]:
        """Map every rule test in one test directory to its invalid cases.

        Returns:
            The resulting ``t.MappingKV[str, frozenset[str]]``.

        Raises:
            TypeError: If invalid ast-grep rule-test contract.

        """
        cases: MutableMapping[str, frozenset[str]] = {}
        for test_file in sorted(test_dir.glob(f"*{c.Infra.CODEMOD_RULE_SUFFIX}")):
            payload = u.Cli.yaml_safe_load(test_file).unwrap()
            rule_id = payload.get(c.Infra.CODEMOD_RULE_TEST_ID_KEY)
            invalid = payload.get(c.Infra.CODEMOD_RULE_TEST_INVALID_KEY, ())
            if (
                not isinstance(rule_id, str)
                or not isinstance(invalid, Sequence)
                or isinstance(invalid, str)
                or not all(isinstance(case, str) for case in invalid)
            ):
                msg = f"invalid ast-grep rule-test contract: {test_file}"
                raise TypeError(msg)
            cases[rule_id] = frozenset(str(case) for case in invalid)
        return cases

    @staticmethod
    def _snapshot_cases(snapshot: Path) -> t.StrSequence:
        """Return the test cases one committed snapshot file projects.

        Returns:
            The test cases one committed snapshot file projects.

        Raises:
            TypeError: If invalid ast-grep snapshot contract.

        """
        payload = u.Cli.yaml_safe_load(snapshot).unwrap()
        projections = payload.get(c.Infra.CODEMOD_SNAPSHOTS_KEY, {})
        if not isinstance(projections, Mapping):
            msg = f"invalid ast-grep snapshot contract: {snapshot}"
            raise TypeError(msg)
        return tuple(projections)


__all__: t.StrSequence = ("FlextInfraCodemodSnapshotReconciler",)
