"""A re-export aggregator's ``__all__`` never claims single ownership.

Regression coverage: a generated TYPE_CHECKING re-export sidecar (e.g.
``tests/_exports_typing_facades.py`` in flext-core) imports many facades and
relists their class/alias names in its own ``__all__``. ``_resolve_family``
used to derive that module's ``expected_alias``/``expected_family`` from the
FIRST class/alias pair appearing in its ``__all__`` -- exactly as if the
aggregator itself declared that class. When a two-base root ``constants.py``
module (``class X(ExternalConstants, OwnProjectConstants)``) happened to be
the alphabetically-first re-export in the aggregator's list, the aggregator
tied the real owner's collision score and won the tie-break, dropping the
real ``constants.py``-owned class and alias entirely from the generated root
``__init__.py``.
"""

from __future__ import annotations

from pathlib import Path

from flext_tests import tm

from tests import c, u


class TestsFlextInfraLazyInitFamilyAggregator:
    """A multi-name aggregator module never wins family/alias ownership."""

    def test_aggregator_sidecar_never_shadows_real_constants_owner(
        self, tmp_path: Path
    ) -> None:
        """The real ``constants.py`` owner survives a re-export aggregator."""
        repository_root, package_root = u.Tests.create_lazy_init_workspace(
            tmp_path, project_name="flext-test-agg", package_name="flext_test_agg"
        )
        package_root.joinpath("base.py").write_text(
            "from __future__ import annotations\n\n"
            "class FlextTestAggServiceBase:\n"
            "    pass\n\n"
            "s = FlextTestAggServiceBase\n\n"
            '__all__: list[str] = ["FlextTestAggServiceBase", "s"]\n',
            encoding=c.Infra.ENCODING_DEFAULT,
        )
        package_root.joinpath(c.Infra.CONSTANTS_PY).write_text(
            "from __future__ import annotations\n\n"
            "class FlextTestAggConstants:\n"
            "    pass\n\n"
            "c = FlextTestAggConstants\n\n"
            '__all__: list[str] = ["FlextTestAggConstants", "c"]\n',
            encoding=c.Infra.ENCODING_DEFAULT,
        )
        # The aggregator sidecar: a generated-style TYPE_CHECKING re-export
        # module that forwards MANY facades' class/alias pairs through its
        # own __all__ without defining any of them itself. Its __all__ lists
        # "FlextTestAggConstants"/"c" FIRST -- the exact ordering that used
        # to make _resolve_family mistake it for the declared owner.
        package_root.joinpath("_exports_typing_aggregate.py").write_text(
            "from __future__ import annotations\n\n"
            "from .base import FlextTestAggServiceBase, s\n"
            "from .constants import FlextTestAggConstants, c\n\n"
            "__all__: list[str] = [\n"
            '    "FlextTestAggConstants",\n'
            '    "FlextTestAggServiceBase",\n'
            '    "c",\n'
            '    "s",\n'
            "]\n",
            encoding=c.Infra.ENCODING_DEFAULT,
        )

        tm.that(u.Tests.run_lazy_init(repository_root), eq=0)
        generated = package_root.joinpath(c.Infra.INIT_PY).read_text(
            encoding=c.Infra.ENCODING_DEFAULT
        )

        tm.that(
            generated,
            has="from .constants import FlextTestAggConstants, FlextTestAggConstants as c",
        )
        tm.that(generated, has='".constants": ("FlextTestAggConstants", "c")')
        tm.that(generated, lacks="_exports_typing_aggregate")
