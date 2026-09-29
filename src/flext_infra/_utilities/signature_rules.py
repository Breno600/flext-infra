"""Declarative signature-migration catalogue for call-site propagation.

A signature change is not one edit: renaming a parameter means rewriting every
call site that passes it by keyword. Done by hand it is a sweep over the whole
fleet, repeated in every branch that has not merged yet. The transformer that
performs it already exists; what was missing is the declared catalogue it reads,
so the capability was unreachable.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING

from flext_cli import p, r, u

from flext_infra import c, m, t

if TYPE_CHECKING:
    from pathlib import Path


class FlextInfraUtilitiesSignatureRules:
    """Load and validate the declared signature migrations of one repository."""

    @classmethod
    def load(cls, root: Path) -> p.Result[t.VariadicTuple[m.Infra.SignatureMigration]]:
        """Return every enabled migration the repository declares.

        Absence of the catalogue is the empty declaration, never a failure: a
        repository that declares no migration simply has none. A catalogue that
        exists but is malformed fails loudly, because a migration silently
        dropped would leave call sites half-rewritten.
        """
        source = root / c.Infra.REFACTOR_SIGNATURE_RULES_RELPATH
        if not source.is_file():
            return r[tuple[m.Infra.SignatureMigration, ...]].ok(())
        text = u.Cli.files_read_text(source)
        if text.failure:
            return r[tuple[m.Infra.SignatureMigration, ...]].from_failure(text)
        parsed = u.Cli.yaml_parse(text.value)
        if parsed.failure:
            return r[tuple[m.Infra.SignatureMigration, ...]].from_failure(parsed)
        listing = parsed.value.get(c.Infra.REFACTOR_SIGNATURE_RULES_KEY)
        if listing is None:
            return r[tuple[m.Infra.SignatureMigration, ...]].fail(
                f"signature catalogue declares no migrations list: {source}"
            )
        if not isinstance(listing, list):
            return r[tuple[m.Infra.SignatureMigration, ...]].fail(
                f"signature catalogue migrations must be a list: {source}"
            )
        migrations: list[m.Infra.SignatureMigration] = []
        seen: set[str] = set()
        for raw in listing:
            built = cls._build(raw, source)
            if built.failure:
                return r[tuple[m.Infra.SignatureMigration, ...]].from_failure(built)
            migration = built.value
            if migration.id in seen:
                return r[tuple[m.Infra.SignatureMigration, ...]].fail(
                    f"signature migration id is declared twice: {migration.id}"
                )
            seen.add(migration.id)
            if migration.enabled:
                migrations.append(migration)
        return r[tuple[m.Infra.SignatureMigration, ...]].ok(tuple(migrations))

    @staticmethod
    def _build(
        raw: p.AttributeProbe, source: Path
    ) -> p.Result[m.Infra.SignatureMigration]:
        """Validate one declared migration into its typed owner."""
        if not isinstance(raw, Mapping):
            return r[m.Infra.SignatureMigration].fail(
                f"signature migration entry must be a mapping: {source}"
            )
        try:
            migration = m.Infra.SignatureMigration.model_validate(dict(raw))
        except c.ValidationError as error:
            return r[m.Infra.SignatureMigration].fail_op(
                f"validate signature migration in {source}", error
            )
        if not migration.target_qualified_names and not migration.target_simple_names:
            return r[m.Infra.SignatureMigration].fail(
                f"signature migration {migration.id} targets no callable: {source}"
            )
        if (
            not migration.keyword_renames
            and not migration.remove_keywords
            and not migration.add_keywords
        ):
            return r[m.Infra.SignatureMigration].fail(
                f"signature migration {migration.id} declares no rewrite: {source}"
            )
        return r[m.Infra.SignatureMigration].ok(migration)


__all__: list[str] = ["FlextInfraUtilitiesSignatureRules"]
