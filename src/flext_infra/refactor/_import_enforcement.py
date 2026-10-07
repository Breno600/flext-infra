"""Rewrite one module's imports into the canonical FLEXT forms.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from flext_infra.refactor._import_enforcement_ast import (
    FlextInfraImportNormalizationAstMixin,
)
from flext_infra.refactor._import_enforcement_demotion import (
    FlextInfraImportNormalizationDemotionMixin,
)
from flext_infra.refactor._import_enforcement_edits import (
    FlextInfraImportNormalizationEditsMixin,
)


class FlextInfraImportNormalization(
    FlextInfraImportNormalizationEditsMixin,
    FlextInfraImportNormalizationDemotionMixin,
    FlextInfraImportNormalizationAstMixin,
):
    """Rewrite one module's imports into the canonical FLEXT forms.

    The four operator rules this engine owns, in one idempotent pass:

    1. Concrete objects (classes/functions) import lazily, inside the
       outermost function that uses them. Class bases, Pydantic annotations,
       decorators and signature defaults are structural module-definition
       uses and stay eager.
    2. Facade letters follow the layer order (settings, config, c, t, p, m,
       u, siblings, base, services, api, cli): a module-level letter binding
       at or after the module's own layer is demoted to the point of use when
       every use sits inside a function body.
    3. Letters of one package bind in ONE root-combined statement
       (``from pkg import c, m, p, t, u``); facade-file, alias-split and
       relative letter forms rewrite into it.
    4. Objects import through the family ``__init__``
       (``from pkg._models import X``); leaf-module paths flatten when the
       family init publishes the name (its ``TYPE_CHECKING`` imports, lazy
       export map and ``__all__`` are the export SSOT); internal family
       wiring the init does not publish stays leaf.

    ``try/except ImportError`` import guards are removed and their names
    re-bound at the point of use; no half-initialized ``= None`` fallback
    survives. A guarded name the module still uses at definition time falls
    back to a plain module-level import, never to a silent ``None``.

    The layer-order ranking lives in the constants family (``c.Infra.*``):
    ``LETTER_ORDER``, ``LETTER_RENDER_ORDER``, ``FAMILY_LETTER``,
    ``FAMILY_RANK``, ``FACADE_RANK``, ``MAX_PASSES``, ``FAMILY_PATH_DEPTH``,
    ``LEAF_PATH_DEPTH`` and ``DEFAULT_LAYER_RANK``.
    """


__all__: list[str] = ["FlextInfraImportNormalization"]
