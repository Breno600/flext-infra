from __future__ import annotations

from flext_tests import tm

from tests import u


class TestsFlextInfraUtilitiesformatting:
    def test_generate_module_skeleton_is_static_on_public_instance(self) -> None:
        # flext-i6nq.10: Guard the public instance binding lost during consolidation.
        source = u.Infra().generate_module_skeleton(
            class_name="FlextDemoModels",
            base_class="FlextModels",
            base_module="flext_core",
            docstring="Models for demo.",
        )

        compile(source, "models.py", "exec")
        tm.that(source, has="class FlextDemoModels(FlextModels):")
        tm.that(source, has="from flext_core import FlextModels")
