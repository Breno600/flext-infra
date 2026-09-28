"""Service base for flext-infra tests."""

from __future__ import annotations

from flext_tests import FlextTestsServiceBase


class TestsFlextInfraServiceBase(FlextTestsServiceBase):
    """Infra test service base composed directly from flext-tests."""

    # NOTE (multi-agent, flext-wkii.17.14): flext-tests is the sole owner of
    # settings bootstrap behavior; this project adds no forwarding override.


s = TestsFlextInfraServiceBase

__all__: list[str] = ["TestsFlextInfraServiceBase", "s"]
