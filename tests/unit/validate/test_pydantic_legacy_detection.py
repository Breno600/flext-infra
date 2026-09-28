"""Tests for Pydantic v1/v2 legacy detection in namespace validator."""

from __future__ import annotations

from pathlib import Path

import pytest
from flext_tests import tm

from tests import u


class TestsFlextInfraPydanticLegacyDetection:
    """Test suite for Pydantic legacy decorator/method detection."""

    @pytest.mark.parametrize(
        ("imports", "body", "legacy"),
        [
            (
                "from collections.abc import Callable\n",
                (
                    "    def execute(self, validator: Callable[[], None]) -> None:\n"
                    "        validator()\n"
                ),
                False,
            ),
            (
                (
                    "from collections.abc import Callable\n"
                    "from pydantic import validator\n"
                ),
                (
                    "    def execute(self, validator: Callable[[], None]) -> None:\n"
                    "        validator()\n"
                ),
                False,
            ),
            (
                (
                    "from collections.abc import Callable\n"
                    "from pydantic import root_validator as validate\n"
                ),
                (
                    "    def execute(self, validate: Callable[[], None]) -> None:\n"
                    "        validate()\n"
                ),
                False,
            ),
            (
                (
                    "from collections.abc import Callable\n"
                    "from pydantic import validator\n"
                ),
                (
                    "    def execute(self, callback: Callable[[], None]) -> None:\n"
                    "        validator = callback\n"
                    "        validator()\n"
                ),
                False,
            ),
            (
                "from pydantic import validator\n",
                (
                    "    def execute(self) -> None:\n"
                    "        def validator() -> None:\n"
                    "            pass\n"
                    "        validator()\n"
                ),
                False,
            ),
            (
                "from unrelated import validator\n",
                (
                    "    @validator('value')\n"
                    "    def validate(cls, value: str) -> str:\n"
                    "        return value\n"
                ),
                False,
            ),
            (
                "import unrelated as pd\n",
                (
                    "    @pd.root_validator()\n"
                    "    def validate(cls, value: str) -> str:\n"
                    "        return value\n"
                ),
                False,
            ),
            (
                "from pydantic import validator\n",
                (
                    "    @validator('value')\n"
                    "    def validate(cls, value: str) -> str:\n"
                    "        return value\n"
                ),
                True,
            ),
            (
                "from pydantic import validator as validate_field\n",
                (
                    "    @validate_field('value')\n"
                    "    def validate(cls, value: str) -> str:\n"
                    "        return value\n"
                ),
                True,
            ),
            (
                "from pydantic.v1 import root_validator as validate_root\n",
                (
                    "    @validate_root()\n"
                    "    def validate(cls, value: str) -> str:\n"
                    "        return value\n"
                ),
                True,
            ),
            (
                "from pydantic import root_validator as validate_root\n",
                (
                    "    @validate_root\n"
                    "    def validate(cls, value: str) -> str:\n"
                    "        return value\n"
                ),
                True,
            ),
            (
                "import pydantic as pd\n",
                (
                    "    @pd.validator('value')\n"
                    "    def validate(cls, value: str) -> str:\n"
                    "        return value\n"
                ),
                True,
            ),
            (
                "import pydantic.v1 as pd\n",
                (
                    "    @pd.root_validator()\n"
                    "    def validate(cls, value: str) -> str:\n"
                    "        return value\n"
                ),
                True,
            ),
            (
                "",
                (
                    "    def execute(self) -> None:\n"
                    "        from pydantic.v1 import validator as validate\n"
                    "        validate('value')\n"
                ),
                True,
            ),
            (
                "from pydantic import validator as validate\n",
                (
                    "    def execute(self) -> None:\n"
                    "        label = 'caf\u00e9'; validate('value')\n"
                ),
                True,
            ),
            (
                "from pydantic import field_validator as validator\n",
                (
                    "    @validator('value')\n"
                    "    def validate(cls, value: str) -> str:\n"
                    "        return value\n"
                ),
                False,
            ),
        ],
    )
    def test_pydantic_decorator_binding_provenance(
        self, tmp_path: Path, imports: str, body: str, *, legacy: bool
    ) -> None:
        root = u.Tests.namespace_project(
            tmp_path,
            module_source=(
                "from __future__ import annotations\n"
                + imports
                + "\nclass FlextTestValidation:\n"
                + body
            ),
            module_name="validation.py",
        )

        report = u.Tests.validate_namespace_project(root)

        tm.that(report.passed, eq=not legacy, msg=str(report.violations))
        tm.that(
            sum("legacy Pydantic member" in item for item in report.violations),
            eq=int(legacy),
        )

    @pytest.mark.parametrize(
        ("call", "legacy"),
        [
            ("response.json()", False),
            ("response.dict()", False),
            ("model.parse_obj({})", True),
            ("model.parse_raw(b'{}')", True),
        ],
    )
    def test_pydantic_method_detection_requires_unambiguous_member(
        self, tmp_path: Path, call: str, *, legacy: bool
    ) -> None:
        root = u.Tests.namespace_project(
            tmp_path,
            module_source=(
                "from __future__ import annotations\n\n"
                "class FlextTestClient:\n"
                "    def execute(self, response, model) -> None:\n"
                f"        {call}\n"
            ),
            module_name="client.py",
        )

        report = u.Tests.validate_namespace_project(root)

        tm.that(
            sum("legacy Pydantic member" in item for item in report.violations),
            eq=int(legacy),
        )
