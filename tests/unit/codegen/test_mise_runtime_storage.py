"""Public contracts for persistent release-addressed Mise runtime storage."""

from __future__ import annotations

import os
from pathlib import Path

from flext_tests import tm

from flext_infra import c, u


class TestsFlextInfraMiseRuntimeStorage:
    """Validate storage behavior only through the public utility facade."""

    def test_runtime_storage_is_persistent_and_release_addressed(self) -> None:
        contract = u.Infra.mise_bootstrap_environment()
        storage = u.Infra.prepare_mise_runtime_storage(Path.cwd(), os.environ, contract)
        tm.ok(storage)
        components = tuple(
            component + 1 for component in range(c.Infra.MISE_RELEASE_COMPONENT_COUNT)
        )
        release = ".".join(str(component) for component in components)
        other_release = ".".join(
            str(component + (index == len(components) - 1))
            for index, component in enumerate(components)
        )

        first = u.Infra.mise_runtime_install_path(storage.value, release)
        repeated = u.Infra.mise_runtime_install_path(storage.value, release)
        other = u.Infra.mise_runtime_install_path(storage.value, other_release)
        invalid = u.Infra.mise_runtime_install_path(storage.value, f"{release}.0")

        tm.ok(first)
        tm.ok(repeated)
        tm.ok(other)
        tm.that(first.value, eq=repeated.value)
        tm.that(first.value, ne=other.value)
        tm.fail(invalid, has="invalid Mise runtime release")
        tm.that(first.value.is_relative_to(storage.value), eq=True)
        tm.that(storage.value.is_relative_to(Path.cwd()), eq=False)

    def test_checkout_storage_is_rejected_before_creation(self, tmp_path: Path) -> None:
        contract = u.Infra.mise_bootstrap_environment()
        candidate = tmp_path / contract.storage_root_variable.lower()

        result = u.Infra.prepare_mise_runtime_storage(
            tmp_path, {contract.storage_root_variable: str(candidate)}, contract
        )

        tm.fail(result)
        tm.that(candidate.exists(), eq=False)
