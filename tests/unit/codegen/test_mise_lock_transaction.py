# Copyright 2026 FLEXT
"""The projected Mise publisher restores a usable lock after interrupted work.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import pytest
from flext_tests import tm

from flext_infra.bootstrap import FlextInfraBootstrap
from tests import c, u


class TestsMiseLockTransaction:
    """Exercise the consumer script through its generated CLI boundary."""

    @staticmethod
    def _stage(root: Path, suffix: str, *, crlf: bool = False) -> Path:
        stage = root.parent / f".{root.name}.mise-lock-stage.{suffix}"
        stage.mkdir()
        annotations: list[str] = []
        for package in ("alpha", "beta"):
            relative = f".mise/locks/npm-{package}/1.0"
            sidecar = stage / relative / "aube-lock.yaml"
            sidecar.parent.mkdir(parents=True)
            content = f"name: {package}\n".encode()
            sidecar.write_bytes(content.replace(b"\n", b"\r\n") if crlf else content)
            digest = hashlib.sha256(content).hexdigest()
            annotations.append(
                f'[[tools."npm:{package}"]]\n'
                'version = "1.0"\n'
                f'aube = {{ path = "{relative}", digest = "sha256:{digest}" }}\n',
            )
        (stage / "mise.lock").write_text("\n".join(annotations), encoding="utf-8")
        return stage

    @staticmethod
    def _publish(root: Path, stage: Path) -> tuple[bool, str]:
        outcome = tm.ok(
            u.Cli.run_raw(
                [
                    sys.executable,
                    str(root / "bin/mise-lock-transaction.py"),
                    "publish",
                    str(root),
                    str(stage),
                ],
                cwd=root,
            ),
        )
        return u.Cli.process_succeeded(outcome.outcome), outcome.stderr

    @staticmethod
    def test_release_change_publishes_pin_when_lock_bytes_are_unchanged(
        tmp_path: Path,
    ) -> None:
        """A new Mise release reaches the pin even when the bumped lock is identical.

        ``make upg`` may resolve a different Mise release (the rolling cooldown
        can select an older one) while ``mise lock --bump`` reproduces the
        committed lock byte for byte. The pin and launchers must still move to
        the resolved release, or every later Mise call rejects the lifecycle's
        ``MISE_VERSION`` against the stale pin. The publisher runs isolated
        from every installed package (``-I -S``), exactly as the bootstrap runs
        it before any project environment exists.
        """
        root, _ = u.Tests.render_make_environment(
            tmp_path,
            c.Infra.MakeProfile.STANDALONE,
        )
        lock_bytes = b"lockfile_version = 3\n[tools]\n"
        (root / "mise.lock").write_bytes(lock_bytes)
        stage = root.parent / f".{root.name}.mise-lock-stage.release"
        stage.mkdir()
        (stage / "mise.lock").write_bytes(lock_bytes)
        bootstrap = u.Infra.mise_bootstrap_environment()
        for relative, _mode in bootstrap.artifact_specs:
            staged = stage / "artifacts" / relative
            staged.parent.mkdir(parents=True, exist_ok=True)
            staged.write_bytes(f"resolved {relative}\n".encode())

        outcome = tm.ok(
            u.Cli.run_raw(
                [
                    sys.executable,
                    "-I",
                    "-S",
                    str(root / "bin/mise-lock-transaction.py"),
                    "publish",
                    str(root),
                    str(stage),
                ],
                cwd=root,
            ),
        )

        tm.that(u.Cli.process_succeeded(outcome.outcome), eq=True, msg=outcome.stderr)
        tm.that((root / "mise.lock").read_bytes(), eq=lock_bytes)
        tm.that(stage.exists(), eq=False)
        for relative, _mode in bootstrap.artifact_specs:
            tm.that(
                (root / relative).read_bytes(),
                eq=f"resolved {relative}\n".encode(),
            )

    def test_interrupted_sidecar_publication_recovers_then_commits(
        self,
        tmp_path: Path,
    ) -> None:
        """A real filesystem conflict after one rename leaves the old graph usable."""
        root, _ = u.Tests.render_make_environment(
            tmp_path,
            c.Infra.MakeProfile.STANDALONE,
        )
        old = b"lockfile_version = 3\n[tools]\n"
        lock = root / "mise.lock"
        lock.write_bytes(old)
        first = self._stage(root, "first")
        conflict = root / ".mise/locks/npm-beta"
        conflict.parent.mkdir(parents=True, exist_ok=True)
        conflict.write_text("not a directory", encoding="utf-8")

        passed, error = self._publish(root, first)

        tm.that(passed, eq=False)
        tm.that(error, has="transaction directory is not physical")
        tm.that(lock.read_bytes(), eq=old)
        tm.that((first / "transaction.json").is_file(), eq=True)
        tm.that((root / ".mise/locks/npm-alpha/1.0/aube-lock.yaml").is_file(), eq=True)

        conflict.unlink()
        second = self._stage(root, "second")
        expected = (second / "mise.lock").read_bytes()
        passed, error = self._publish(root, second)

        tm.that(passed, eq=True, msg=error)
        tm.that(lock.read_bytes(), eq=expected)
        tm.that(first.exists(), eq=False)
        tm.that(second.exists(), eq=False)
        for package in ("alpha", "beta"):
            tm.that(
                (root / f".mise/locks/npm-{package}/1.0/aube-lock.yaml").is_file(),
                eq=True,
            )

    def test_native_sidecar_digest_accepts_crlf_checkout(self, tmp_path: Path) -> None:
        """Mise records a normalized graph digest across checkout line endings."""
        root, _ = u.Tests.render_make_environment(
            tmp_path,
            c.Infra.MakeProfile.STANDALONE,
        )
        stage = self._stage(root, "crlf", crlf=True)

        passed, error = self._publish(root, stage)

        tm.that(passed, eq=True, msg=error)
        for package in ("alpha", "beta"):
            tm.that(
                (root / f".mise/locks/npm-{package}/1.0/aube-lock.yaml").read_bytes(),
                eq=f"name: {package}\r\n".encode(),
            )

    def test_publish_regenerates_an_unmerged_generated_lock(
        self,
        tmp_path: Path,
    ) -> None:
        """The public publisher consumes Git's prior lock without editing a projection."""
        root, _ = u.Tests.render_make_environment(
            tmp_path,
            c.Infra.MakeProfile.STANDALONE,
        )

        def git(*arguments: str, succeeds: bool = True) -> None:
            outcome = tm.ok(u.Cli.run_raw(["git", *arguments], cwd=root))
            tm.that(u.Cli.process_succeeded(outcome.outcome), eq=succeeds)

        lock = root / "mise.lock"
        git("init", "-b", "main")
        git("config", "user.name", "FLEXT Test")
        git("config", "user.email", "test@flext.invalid")
        lock.write_text('version = "base"\n[tools]\n', encoding="utf-8")
        git("add", "mise.lock")
        git("commit", "-m", "base lock")
        git("switch", "-c", "incoming")
        lock.write_text('version = "incoming"\n[tools]\n', encoding="utf-8")
        git("commit", "-am", "incoming lock")
        git("switch", "main")
        lock.write_text('version = "current"\n[tools]\n', encoding="utf-8")
        git("commit", "-am", "current lock")
        git("merge", "--no-ff", "incoming", succeeds=False)
        tm.that(lock.read_bytes(), has=b"<<<<<<< ")

        stage = self._stage(root, "merge")
        expected = (stage / "mise.lock").read_bytes()
        passed, error = self._publish(root, stage)

        tm.that(passed, eq=True, msg=error)
        tm.that(lock.read_bytes(), eq=expected)
        tm.that(stage.exists(), eq=False)

    def test_publish_preserves_another_stage_without_a_journal(
        self,
        tmp_path: Path,
    ) -> None:
        """A matching directory name alone never authorizes deletion."""
        root, _ = u.Tests.render_make_environment(
            tmp_path,
            c.Infra.MakeProfile.STANDALONE,
        )
        active = root.parent / f".{root.name}.mise-lock-stage.active"
        active.mkdir()
        (active / "in-progress").write_bytes(b"another resolver\n")
        unrelated = root.parent / f".{root.name}.mise-lock-cleanup.unrelated"
        unrelated.mkdir()
        (unrelated / "owned-by-another-process").write_bytes(b"preserve\n")
        stage = self._stage(root, "publish")

        passed, error = self._publish(root, stage)

        tm.that(passed, eq=False)
        tm.that(error, has="uncommitted Mise stage has no recovery journal")
        tm.that((active / "in-progress").read_bytes(), eq=b"another resolver\n")
        tm.that(
            (unrelated / "owned-by-another-process").read_bytes(),
            eq=b"preserve\n",
        )

    def test_unowned_sidecar_is_preserved_when_new_lock_claims_its_path(
        self,
        tmp_path: Path,
    ) -> None:
        """A new lock declaration cannot overwrite an unrelated physical tree."""
        root, _ = u.Tests.render_make_environment(
            tmp_path,
            c.Infra.MakeProfile.STANDALONE,
        )
        lock = root / "mise.lock"
        old = b"lockfile_version = 3\n[tools]\n"
        lock.write_bytes(old)
        stage = self._stage(root, "unowned")
        bootstrap = u.Infra.mise_bootstrap_environment()
        old_artifacts = {
            relative: (root / relative).read_bytes()
            for relative, _mode in bootstrap.artifact_specs
        }
        for relative, _mode in bootstrap.artifact_specs:
            staged = stage / "artifacts" / relative
            staged.parent.mkdir(parents=True, exist_ok=True)
            staged.write_bytes(f"new {relative}\n".encode())
        orphan = root / ".mise/locks/npm-alpha/1.0"
        orphan.mkdir(parents=True)
        owned_bytes = b"external data\n"
        (orphan / "aube-lock.yaml").write_bytes(owned_bytes)

        passed, error = self._publish(root, stage)

        tm.that(passed, eq=False)
        tm.that(error, has="unowned Mise sidecar occupies target")
        tm.that(lock.read_bytes(), eq=old)
        tm.that((orphan / "aube-lock.yaml").read_bytes(), eq=owned_bytes)
        tm.that((stage / "transaction.json").exists(), eq=False)
        for relative, _mode in bootstrap.artifact_specs:
            tm.that((root / relative).read_bytes(), eq=old_artifacts[relative])

    @staticmethod
    def test_setup_recovers_committed_lock_before_selecting_mise_runtime(
        tmp_path: Path,
    ) -> None:
        """A killed publication finishes its pin and launchers on next setup."""
        root, _ = u.Tests.render_make_environment(
            tmp_path,
            c.Infra.MakeProfile.STANDALONE,
        )
        stage = root.parent / f".{root.name}.mise-lock-stage.interrupted"
        stage.mkdir()
        old_lock = b"lockfile_version = 3\n[tools]\n"
        new_lock = b"lockfile_version = 2\n[tools]\n"
        (root / "mise.lock").write_bytes(new_lock)
        (stage / "old.lock").write_bytes(old_lock)
        (stage / "new.lock").write_bytes(new_lock)
        (stage / "python-path").write_text(f"{sys.executable}\n", encoding="utf-8")
        old_artifacts: dict[str, str] = {}
        new_artifacts: dict[str, str] = {}
        bootstrap = u.Infra.mise_bootstrap_environment()
        for relative, _mode in bootstrap.artifact_specs:
            destination = root / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            original = f"old {relative}\n".encode()
            destination.write_bytes(original)
            old_artifacts[relative] = hashlib.sha256(original).hexdigest()
            replacement = f"new {relative}\n".encode()
            staged = stage / "new-artifacts" / relative
            staged.parent.mkdir(parents=True, exist_ok=True)
            staged.write_bytes(replacement)
            new_artifacts[relative] = hashlib.sha256(replacement).hexdigest()
        (stage / "transaction.json").write_text(
            json.dumps(
                {
                    "project": str(root),
                    "old": hashlib.sha256(old_lock).hexdigest(),
                    "new": hashlib.sha256(new_lock).hexdigest(),
                    "old_refs": "{}",
                    "new_refs": "{}",
                    "old_artifacts": json.dumps(old_artifacts, sort_keys=True),
                    "new_artifacts": json.dumps(new_artifacts, sort_keys=True),
                },
                sort_keys=True,
            ),
            encoding="utf-8",
        )

        process = tm.ok(u.Tests.run_isolated_make(["setup"], cwd=root))

        # The deliberately non-executable launcher stops setup only after the
        # public consumer has recovered the committed transaction.
        tm.that(u.Cli.process_succeeded(process.outcome), eq=False)
        tm.that(stage.exists(), eq=False)
        for relative, _mode in bootstrap.artifact_specs:
            tm.that((root / relative).read_bytes(), eq=f"new {relative}\n".encode())


class TestsMiseHoldConvergence:
    """Broken releases are held per tool so upgrade never blocks on them."""

    @staticmethod
    def test_failing_install_tools_parses_mise_diagnostics() -> None:
        """Test failing install tools parses mise diagnostics."""
        parsed = FlextInfraBootstrap._failing_install_tools(
            "mise ERROR Failed to install tools:"
            " github:kucherenko/jscpd@5.3.3, github:qltysh/qlty@0.645.0\n",
        )
        tm.that(
            parsed
            == [
                ("github:kucherenko/jscpd", "5.3.3"),
                ("github:qltysh/qlty", "0.645.0"),
            ],
        )

    @staticmethod
    def test_failing_install_tools_refuses_unparsable_diagnostics() -> None:
        """Test failing install tools refuses unparsable diagnostics."""
        with pytest.raises(ValueError, match="named no failing tool"):
            FlextInfraBootstrap._failing_install_tools("boom")

    @staticmethod
    def test_hold_manifest_version_rewrites_only_the_named_section(
        tmp_path: Path,
    ) -> None:
        """Test hold manifest version rewrites only the named section."""
        manifest = tmp_path / ".mise.toml"
        manifest.write_text(
            '[tools]\npython = "3.13"\n'
            '[tools."github:kucherenko/jscpd"]\nversion = "5.3.3"\n'
            '[tools."github:microsoft/waza"]\nversion = "latest"\n'
            'version_prefix = "v"\n',
            encoding="utf-8",
        )
        FlextInfraBootstrap._hold_manifest_version(
            manifest,
            "github:kucherenko/jscpd",
            "5.3.2",
        )
        content = manifest.read_text(encoding="utf-8")
        tm.that('version = "5.3.2"' in content)
        tm.that('version = "latest"' in content)
        tm.that('version = "5.3.3"' not in content)

    @staticmethod
    def test_remote_release_candidates_walk_below_the_failed_release(
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Test remote release candidates walk below the failed release."""

        def fake_ls_remote(
            runtime: Path,
            arguments: list[str],
            environment: dict[str, str],
        ) -> str:
            tm.that(arguments[:1] == ["ls-remote"])
            return "v5.4.0\n5.3.3\nv5.3.2\n5.2.0\nnot-a-version\n"

        monkeypatch.setattr(
            FlextInfraBootstrap,
            "_run",
            staticmethod(fake_ls_remote),
        )
        candidates = FlextInfraBootstrap._remote_release_candidates(
            Path("/runtime"),
            {},
            "github:kucherenko/jscpd",
            "5.3.3",
        )
        tm.that(candidates == ["5.3.2", "5.2.0"])
