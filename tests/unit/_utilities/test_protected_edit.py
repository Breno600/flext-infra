"""Test protected edit module.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from flext_tests import tm

from tests import c, m, u

if TYPE_CHECKING:
    from pathlib import Path


@pytest.mark.usefixtures("provisioned_workspace")
class TestsFlextInfraUtilitiesProtectedEdit:
    @staticmethod
    @pytest.fixture
    def provisioned_workspace(tmp_path: Path) -> None:
        """The edited workspace is a checkout whose environment owns the tools."""
        u.Tests.provision_checkout(tmp_path)

    @staticmethod
    @pytest.mark.parametrize("batch", [False, True])
    def test_invalid_ruff_configuration_propagates_and_restores_source(
        tmp_path: Path,
        *,
        batch: bool,
    ) -> None:
        """A configuration failure is not a remaining-findings receipt."""
        project_config = (
            "[project]\nname = 'sample'\n[tool.ruff.lint]\nselect = ['F401']\n"
        )
        package = u.Tests.src_package(tmp_path, "sample", pyproject=project_config)
        py_file = package / "sample.py"
        original = "VALUE = 1\n"
        updated = "VALUE = 2\n"
        py_file.write_text(original, encoding=c.Cli.ENCODING_DEFAULT)

        def invalidate_configuration() -> None:
            """Introduce a real invalid Ruff setting after the valid baseline."""
            (tmp_path / "pyproject.toml").write_text(
                project_config + "[tool.ruff]\nline-length = 'invalid'\n",
                encoding=c.Cli.ENCODING_DEFAULT,
            )

        def edit() -> None:
            py_file.write_text(updated, encoding=c.Cli.ENCODING_DEFAULT)
            invalidate_configuration()

        def protected_write() -> None:
            """Run the protected edit through the selected batch or file form."""
            if batch:
                u.Infra.protected_source_writes(
                    {py_file: updated},
                    request=m.Infra.ProtectedSourceWritesRequest(
                        workspace=tmp_path,
                        gates=("lint",),
                        expected_sources={py_file: original},
                        post_write=invalidate_configuration,
                    ),
                )
            else:
                u.Infra.protected_file_edit(
                    py_file,
                    request=m.Infra.ProtectedFileEditRequest(
                        workspace=tmp_path,
                        before_source=original,
                        edit_fn=edit,
                        gates=("lint",),
                    ),
                )

        with pytest.raises(RuntimeError, match="ruff normalization failed"):
            protected_write()
        tm.that(py_file.read_text(encoding=c.Cli.ENCODING_DEFAULT), eq=original)

    @staticmethod
    @pytest.mark.parametrize("batch", [False, True])
    @pytest.mark.parametrize(
        ("introduced", "nonfixable"),
        [(False, False), (True, False), (True, True)],
    )
    def test_normalization_repairs_only_files_with_new_findings(
        tmp_path: Path,
        *,
        batch: bool,
        introduced: bool,
        nonfixable: bool,
    ) -> None:
        """A real lint delta selects repair; pre-existing findings alone do not."""
        package = u.Tests.src_package(
            tmp_path,
            "sample",
            pyproject=(
                "[project]\nname = 'sample'\n"
                "[tool.ruff.lint]\nselect = ['F401', 'F821']\n"
            ),
        )
        py_file = package / "sample.py"
        previous = "VALUE = 1\n"
        updated = "VALUE = 2\n"
        unused = "import os\n"
        original = previous if introduced else unused + previous
        requested = updated + unused if introduced else unused + updated
        expected = updated if introduced else requested
        if nonfixable:
            requested = "VALUE = missing_value\n"
            expected = original
        py_file.write_text(original, encoding=c.Cli.ENCODING_DEFAULT)
        if batch:
            peer = package / "peer.py"
            peer_before = unused + previous
            peer_requested = unused + updated
            peer.write_text(peer_before, encoding=c.Cli.ENCODING_DEFAULT)
            result = u.Infra.protected_source_writes(
                {py_file: requested, peer: peer_requested},
                request=m.Infra.ProtectedSourceWritesRequest(
                    workspace=tmp_path,
                    gates=("lint",),
                    expected_sources={py_file: original, peer: peer_before},
                ),
            )
            tm.that(
                peer.read_text(encoding=c.Cli.ENCODING_DEFAULT),
                eq=peer_before if nonfixable else peer_requested,
            )
        else:
            result = u.Infra.protected_source_write(
                py_file,
                request=m.Infra.ProtectedSourceWriteRequest(
                    workspace=tmp_path,
                    updated_source=requested,
                    gates=("lint",),
                ),
            )
        tm.that(result[0], eq=not nonfixable)
        tm.that(result[1], empty=not nonfixable)
        tm.that(py_file.read_text(encoding=c.Cli.ENCODING_DEFAULT), eq=expected)

    @staticmethod
    def _assert_protected_source_write(py_file: Path, workspace: Path) -> None:
        original_source = "def helper() -> int:\n    return 1\n"
        updated_source = "def helper() -> int:\n    return 2\n"
        py_file.write_text(original_source, encoding=c.Cli.ENCODING_DEFAULT)

        result = u.Infra.protected_source_write(
            py_file,
            request=m.Infra.ProtectedSourceWriteRequest(
                workspace=workspace,
                updated_source=updated_source,
                gates=("lint",),
            ),
        )

        tm.that(result, eq=(True, []))
        tm.that(
            py_file.read_text(encoding=c.Cli.ENCODING_DEFAULT).rstrip("\n"),
            eq=updated_source.rstrip("\n"),
        )

    @staticmethod
    def test_pyrefly_snapshot_uses_the_edited_projects_config(
        tmp_path: Path,
    ) -> None:
        """Protected validation never inherits the orchestrator's Pyrefly config."""
        project = tmp_path / "project"
        source = project / "src" / "sample"
        source.mkdir(parents=True)
        config_path = project / "pyproject.toml"
        config_path.write_text("[project]\nname = 'sample'\n", encoding="utf-8")
        py_file = source / "module.py"
        py_file.write_text("VALUE = 1\n", encoding="utf-8")
        commands = dict(u.Infra.lint_commands(py_file, tmp_path, gates=("pyrefly",)))

        tm.that(commands["pyrefly"], has="--config")
        tm.that(commands["pyrefly"], has=str(config_path))

    @staticmethod
    def test_preview_source_writes_restores_original_sources_after_preview(
        tmp_path: Path,
    ) -> None:
        py_file = tmp_path / "sample.py"
        original_source = "def value() -> int:\n    return 1\n"
        updated_source = "def value() -> int:\n    return 2\n"
        py_file.write_text(original_source, encoding=c.Cli.ENCODING_DEFAULT)

        result = u.Infra.preview_source_writes(
            {py_file: updated_source},
            workspace=tmp_path,
            gates=("lint",),
        )

        tm.that(result, eq=(True, []))
        tm.that(py_file.read_text(encoding=c.Cli.ENCODING_DEFAULT), eq=original_source)

    def test_protected_source_write_skips_pytest_for_non_test_file(
        self,
        tmp_path: Path,
    ) -> None:
        self._assert_protected_source_write(tmp_path / "sample.py", tmp_path)

    def test_protected_source_write_treats_no_tests_collected_as_success(
        self,
        tmp_path: Path,
    ) -> None:
        tests_dir = tmp_path / "tests"
        tests_dir.mkdir()
        self._assert_protected_source_write(tests_dir / "test_placeholder.py", tmp_path)

    @staticmethod
    def test_protected_source_writes_applies_request_options(
        tmp_path: Path,
    ) -> None:
        left_file = tmp_path / "left.py"
        right_file = tmp_path / "right.py"
        left_file.write_text("VALUE = 1\n", encoding=c.Cli.ENCODING_DEFAULT)
        right_file.write_text("VALUE = 10\n", encoding=c.Cli.ENCODING_DEFAULT)

        result = u.Infra.protected_source_writes(
            {left_file: "VALUE = 2\n", right_file: "VALUE = 20\n"},
            request=m.Infra.ProtectedSourceWritesRequest(
                workspace=tmp_path,
                expected_sources={left_file: "VALUE = 1\n", right_file: "VALUE = 10\n"},
                gates=("lint",),
                skip_pytest=True,
            ),
        )

        tm.that(result, eq=(True, []))
        tm.that(
            (
                left_file.read_text(encoding=c.Cli.ENCODING_DEFAULT).rstrip("\n")
                == "VALUE = 2"
            ),
            eq=True,
        )
        tm.that(
            (
                right_file.read_text(encoding=c.Cli.ENCODING_DEFAULT).rstrip("\n")
                == "VALUE = 20"
            ),
            eq=True,
        )
