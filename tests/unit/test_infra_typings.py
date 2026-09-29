"""Behavior tests for the public ``t`` typing facade."""

from __future__ import annotations

from pathlib import Path

import pytest
from flext_tests import tm

from flext_infra import config
from tests import c, t


class TestsFlextInfraInfraTypings:
    """Validate public adapters exposed by ``t``."""

    def test_json_mapping_adapter_validates_nested_cli_payload(self) -> None:
        payload = t.Cli.JSON_MAPPING_ADAPTER.validate_python({
            "tool": {"name": "infra"},
            "enabled": True,
        })

        tm.that(payload["enabled"], eq=True)
        tm.that(payload["tool"], eq={"name": "infra"})

    def test_json_list_adapter_validates_mixed_cli_values(self) -> None:
        items = t.Cli.JSON_LIST_ADAPTER.validate_python(["infra", 1, True])

        expected: t.JsonList = ["infra", 1, True]
        tm.that(list(items), eq=expected)

    def test_infra_mapping_adapter_validates_real_workspace_payload(self) -> None:
        python_version = config.Infra.codegen.toolchain.python_version
        payload = t.Infra.INFRA_MAPPING_ADAPTER.validate_python({
            "python": {"version": python_version},
            "paths": ["src", "tests"],
            "enabled": True,
        })

        tm.that(payload["python"], eq={"version": python_version})
        tm.that(payload["paths"], eq=["src", "tests"])
        tm.that(payload["enabled"], eq=True)

    def test_str_seq_adapter_validates_project_name_sequences(self) -> None:
        values = t.Infra.STR_SEQ_ADAPTER.validate_python(("flext-core", "flext-infra"))

        tm.that(list(values), eq=["flext-core", "flext-infra"])

    def test_container_mapping_adapter_accepts_paths_and_scalars(self) -> None:
        payload = t.Infra.CONTAINER_MAPPING_ADAPTER.validate_python({
            "root": Path("/var/lib/flext"),
            "enabled": True,
            "retries": 3,
        })

        tm.that(payload["root"], eq=Path("/var/lib/flext"))
        tm.that(payload["enabled"], eq=True)
        tm.that(payload["retries"], eq=3)

    def test_container_mapping_adapter_rejects_nested_mapping(self) -> None:
        with pytest.raises(c.ValidationError):
            t.Infra.CONTAINER_MAPPING_ADAPTER.validate_python({
                "root": Path("/var/lib/flext"),
                "settings": {"enabled": True},
            })
